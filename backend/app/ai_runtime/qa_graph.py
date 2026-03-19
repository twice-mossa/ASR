from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.ai_runtime.providers import chat_model_for_qa, embedding_model
from app.ai_runtime.schemas import (
    EvidenceWindow,
    GroundedAnswerCheck,
    GroundedAnswerStructuredOutput,
    QuestionIntent,
    RerankedEvidenceWindows,
    RetrievalCandidate,
)
from app.ai_runtime.vectorstore import ensure_meeting_index, retrieve_meeting_segments
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import MeetingQARecord, MeetingSummary, TranscriptSegment
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingAskResponse, MeetingCitation
from app.services.meeting_service import _get_owned_meeting
from app.services.qa_legacy_service import build_recent_history, fallback_answer, pick_segment_indexes

logger = logging.getLogger(__name__)

_SUMMARY_QUESTION_HINTS = ("总结", "概括", "核心", "重点", "风险", "争议", "结论", "主要", "整体", "梳理")
_FOLLOW_UP_HINTS = ("那", "这个", "那个", "这个事情", "那这", "然后", "还有", "为什么", "怎么说", "具体呢")
_LOW_INFO_TEXTS = {"嗯", "嗯嗯", "对", "对对", "好的", "好", "会的", "是的", "行", "可以", "收到"}
_MAX_CONTEXT_CHARS = 8000


class QAState(TypedDict, total=False):
    meeting_id: int
    current_user: UserProfile
    user_question: str
    question_type: str
    question_intent: dict[str, Any]
    rewritten_question: str
    retrieval_query: str
    retrieval_terms: list[str]
    meeting_summary: str
    recent_history: str
    all_segments: list[dict[str, Any]]
    retrieved_segments: list[dict[str, Any]]
    evidence_windows: list[dict[str, Any]]
    selected_windows: list[dict[str, Any]]
    assembled_context: str
    transcript_excerpt: str
    answer: str
    reasoning_summary: str
    generated_citation_window_ids: list[int]
    citations_payloads: list[dict[str, Any]]
    errors: list[str]


def _get_session():
    return SessionLocal()


def _segment_payload(segment: TranscriptSegment) -> dict[str, Any]:
    return {
        "id": int(segment.id),
        "start": float(segment.start),
        "end": float(segment.end),
        "text": str(segment.text or ""),
    }


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_retrieval_terms(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    features: list[str] = []
    chunks = re.findall(r"[\u4e00-\u9fff]{2,16}|[A-Za-z0-9_-]{2,}", normalized)
    for chunk in chunks:
        if chunk not in features:
            features.append(chunk)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,16}", chunk):
            for size in (2, 3, 4):
                if len(chunk) < size:
                    continue
                for index in range(len(chunk) - size + 1):
                    gram = chunk[index : index + size]
                    if gram not in features:
                        features.append(gram)
    return features[:16]


def _is_follow_up_question(question: str) -> bool:
    normalized = _normalize_text(question)
    return any(normalized.startswith(prefix) for prefix in _FOLLOW_UP_HINTS)


def _classify_question(state: QAState) -> QAState:
    question = _normalize_text(state.get("user_question") or "")
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能为空")

    lowered = question.lower()
    if _is_follow_up_question(question) or len(question) <= 8:
        question_type = "follow_up"
    elif any(hint in lowered for hint in _SUMMARY_QUESTION_HINTS):
        question_type = "summary"
    else:
        question_type = "fact"

    return {"question_type": question_type}


def _ensure_qa_runtime_ready() -> None:
    try:
        embedding_model(require_real=settings.qa_require_real_embeddings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "会议问答缺少可用的语义检索模型，请先配置真实 embedding provider。"
            ),
        ) from exc


def _ensure_meeting_index(state: QAState) -> QAState:
    meeting_id = int(state["meeting_id"])
    current_user = state["current_user"]
    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        if meeting.status not in {"transcribed", "summarized"} or not (meeting.transcript_text or "").strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会议尚未完成转录，暂时无法提问")

        segments = db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting.id)
            .order_by(TranscriptSegment.start.asc(), TranscriptSegment.id.asc())
        ).scalars().all()
        summary = db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)).scalar_one_or_none()
        recent_records = db.execute(
            select(MeetingQARecord)
            .where(MeetingQARecord.meeting_id == meeting.id)
            .order_by(MeetingQARecord.created_at.asc(), MeetingQARecord.id.asc())
        ).scalars().all()

    ensure_meeting_index(meeting_id)
    return {
        "all_segments": [_segment_payload(segment) for segment in segments],
        "meeting_summary": summary.summary if summary and summary.summary else "",
        "recent_history": build_recent_history(recent_records),
    }


def _heuristic_question_intent(state: QAState) -> QuestionIntent:
    question = _normalize_text(state.get("user_question") or "")
    features = _extract_retrieval_terms(question)
    entities: list[str] = []
    for feature in features:
        if feature not in entities:
            entities.append(feature)
    anchors = [item for item in entities if any(char.isdigit() for char in item)][:4]
    return QuestionIntent(
        question_type=state.get("question_type") or "fact",
        rewritten_question=question,
        entities=entities[:8],
        anchors=anchors,
        use_recent_history=state.get("question_type") == "follow_up",
    )


def _message_content_to_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _parse_structured_text(schema, raw_text: str):
    cleaned = str(raw_text or "").strip()
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return schema.model_validate_json(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            return schema.model_validate_json(snippet)
        raise


async def _invoke_structured_qa(schema, prompt):
    llm = chat_model_for_qa()
    provider = (settings.chat_provider or "").strip().lower()
    if provider != "minimax":
        try:
            return await llm.with_structured_output(schema).ainvoke(prompt)
        except Exception:
            raw = await llm.ainvoke(prompt)
            return _parse_structured_text(schema, _message_content_to_text(raw))

    raw = await llm.ainvoke(prompt)
    return _parse_structured_text(schema, _message_content_to_text(raw))


async def _rewrite_query(state: QAState) -> QAState:
    fallback = _heuristic_question_intent(state)
    prompt = [
        (
            "system",
            "你是会议检索查询改写器。请把用户问题改写成适合检索会议转写的独立查询。"
            "如果问题依赖上一轮上下文，use_recent_history 设为 true。"
            "只输出一个 JSON 对象，不要输出解释、不要输出 markdown。"
            'JSON 结构必须是：{"question_type":"fact|summary|follow_up","rewritten_question":"...","entities":["..."],"anchors":["..."],"use_recent_history":true}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('user_question') or ''}\n\n"
                f"当前初步分类：{state.get('question_type') or 'fact'}\n\n"
                f"会议摘要：\n{state.get('meeting_summary') or '无'}\n\n"
                f"最近问答历史：\n{state.get('recent_history') or '无'}"
            ),
        ),
    ]
    try:
        result = await _invoke_structured_qa(QuestionIntent, prompt)
    except Exception as exc:
        logger.warning("QA rewrite generation failed, using heuristic intent: %s", exc)
        result = fallback

    rewritten_question = _normalize_text(result.rewritten_question) or _normalize_text(state.get("user_question") or "")
    retrieval_terms: list[str] = []
    for bucket in (
        _extract_retrieval_terms(state.get("user_question") or ""),
        result.entities,
        result.anchors,
        _extract_retrieval_terms(rewritten_question),
        [rewritten_question],
    ):
        for item in bucket:
            normalized = _normalize_text(item)
            if normalized and normalized not in retrieval_terms:
                retrieval_terms.append(normalized)

    return {
        "question_intent": result.model_dump(),
        "question_type": result.question_type or state.get("question_type") or "fact",
        "rewritten_question": rewritten_question,
        "retrieval_query": rewritten_question,
        "retrieval_terms": retrieval_terms[:12],
    }


def _segment_match_bonus(text: str, terms: list[str]) -> float:
    normalized = _normalize_text(text).lower()
    score = 0.0
    for term in terms:
        lowered = term.lower()
        if lowered and lowered in normalized:
            score += 2.5 if len(lowered) >= 3 else 1.0
    return score


def _retrieve_candidates(state: QAState) -> QAState:
    meeting_id = int(state["meeting_id"])
    query = state.get("retrieval_query") or state.get("user_question") or ""
    retrieval_terms = state.get("retrieval_terms") or []
    segment_lookup = {int(segment["id"]): segment for segment in state.get("all_segments") or []}
    score_map: dict[int, float] = {}
    source_map: dict[int, set[str]] = {}

    vector_docs = retrieve_meeting_segments(meeting_id, query, k=max(4, settings.qa_retrieval_top_k))
    for rank, doc in enumerate(vector_docs, start=1):
        segment_id = doc.metadata.get("segment_id")
        if segment_id is None:
            continue
        normalized_id = int(segment_id)
        if normalized_id not in segment_lookup:
            continue
        score_map[normalized_id] = score_map.get(normalized_id, 0.0) + (10.0 / (rank + 1))
        score_map[normalized_id] += _segment_match_bonus(segment_lookup[normalized_id]["text"], retrieval_terms)
        source_map.setdefault(normalized_id, set()).add("vector")

    all_segments = state.get("all_segments") or []
    keyword_indexes = pick_segment_indexes(
        [type("Segment", (), segment) for segment in all_segments],
        query,
        limit=max(4, settings.qa_keyword_top_k),
    )
    for rank, index in enumerate(keyword_indexes, start=1):
        if 0 <= index < len(all_segments):
            segment_id = int(all_segments[index]["id"])
            score_map[segment_id] = score_map.get(segment_id, 0.0) + (7.0 / (rank + 1))
            score_map[segment_id] += _segment_match_bonus(all_segments[index]["text"], retrieval_terms)
            source_map.setdefault(segment_id, set()).add("keyword")

    if not score_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前会议里没有检索到可用于回答的有效片段")

    candidates = [
        RetrievalCandidate(
            segment_id=segment_id,
            score=score,
            source="+".join(sorted(source_map.get(segment_id) or {"keyword"})),
            reason="命中语义检索与关键词召回" if len(source_map.get(segment_id) or []) > 1 else "命中候选片段",
        )
        for segment_id, score in score_map.items()
        if segment_id in segment_lookup
    ]
    candidates.sort(key=lambda item: (-item.score, segment_lookup[item.segment_id]["start"], item.segment_id))

    retrieved_segments = []
    for candidate in candidates[: max(settings.qa_retrieval_top_k, settings.qa_keyword_top_k)]:
        payload = dict(segment_lookup[candidate.segment_id])
        payload["retrieval_score"] = float(candidate.score)
        payload["retrieval_source"] = candidate.source
        retrieved_segments.append(payload)

    return {"retrieved_segments": retrieved_segments}


def _expand_neighbor_windows(state: QAState) -> QAState:
    all_segments = state.get("all_segments") or []
    retrieved_segments = state.get("retrieved_segments") or []
    if not all_segments or not retrieved_segments:
        return {"evidence_windows": []}

    index_lookup = {int(segment["id"]): index for index, segment in enumerate(all_segments)}
    score_lookup = {int(segment["id"]): float(segment.get("retrieval_score") or 0.0) for segment in retrieved_segments}
    expanded_indexes: set[int] = set()

    for segment in retrieved_segments:
        base_index = index_lookup.get(int(segment["id"]))
        if base_index is None:
            continue
        start = max(0, base_index - max(0, settings.qa_neighbor_window))
        end = min(len(all_segments), base_index + max(0, settings.qa_neighbor_window) + 1)
        for neighbor in range(start, end):
            expanded_indexes.add(neighbor)

    groups: list[list[int]] = []
    current_group: list[int] = []
    for index in sorted(expanded_indexes):
        if not current_group or index == current_group[-1] + 1:
            current_group.append(index)
        else:
            groups.append(current_group)
            current_group = [index]
    if current_group:
        groups.append(current_group)

    windows: list[EvidenceWindow] = []
    for window_id, group in enumerate(groups, start=1):
        segments = [all_segments[index] for index in group]
        window_score = sum(score_lookup.get(int(segment["id"]), 0.0) for segment in segments)
        window_score += sum(len((segment["text"] or "").strip()) for segment in segments) / 300.0
        windows.append(
            EvidenceWindow(
                window_id=window_id,
                segment_ids=[int(segment["id"]) for segment in segments],
                start=float(segments[0]["start"]),
                end=float(segments[-1]["end"]),
                text="\n".join((segment["text"] or "").strip() for segment in segments if (segment["text"] or "").strip()),
                score=window_score,
            )
        )

    windows.sort(key=lambda item: (-item.score, item.start, item.window_id))
    return {"evidence_windows": [window.model_dump() for window in windows[: max(4, settings.qa_retrieval_top_k)]]}


async def _rerank_candidates(state: QAState) -> QAState:
    windows = state.get("evidence_windows") or []
    if not windows:
        return {"selected_windows": []}

    heuristic = sorted(windows, key=lambda item: (-float(item.get("score") or 0.0), float(item.get("start") or 0.0)))
    fallback_ids = [int(item["window_id"]) for item in heuristic[: max(1, settings.qa_rerank_top_n)]]

    prompt = [
        (
            "system",
            "你是会议问答检索重排器。请从候选证据窗口中挑出最能回答问题的窗口，优先保留信息密度高、"
            "语义直接相关、不是口头禅的内容。只输出一个 JSON 对象，不要解释。"
            'JSON 结构必须是：{"ordered_window_ids":[1,2],"reasoning_summary":"..."}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('rewritten_question') or state.get('user_question') or ''}\n\n"
                f"问题类型：{state.get('question_type') or 'fact'}\n\n"
                "候选证据窗口：\n"
                + "\n\n".join(
                    (
                        f"window_id={int(window['window_id'])}\n"
                        f"time={float(window['start']):.1f}s-{float(window['end']):.1f}s\n"
                        f"text={window['text']}"
                    )
                    for window in heuristic[:8]
                )
            ),
        ),
    ]
    try:
        result = await _invoke_structured_qa(RerankedEvidenceWindows, prompt)
        ordered_ids = [int(item) for item in result.ordered_window_ids if int(item) in {int(w['window_id']) for w in heuristic}]
    except Exception as exc:
        logger.warning("QA rerank generation failed, using heuristic order: %s", exc)
        ordered_ids = fallback_ids

    if not ordered_ids:
        ordered_ids = fallback_ids

    lookup = {int(window["window_id"]): window for window in heuristic}
    selected = [lookup[window_id] for window_id in ordered_ids[: max(1, settings.qa_rerank_top_n)] if window_id in lookup]
    return {"selected_windows": selected}


def _assemble_grounded_context(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    if not selected_windows:
        return {"assembled_context": "", "transcript_excerpt": ""}

    blocks: list[str] = []
    transcript_lines: list[str] = []
    for window in selected_windows:
        blocks.append(
            (
                f"[window_id={int(window['window_id'])}] "
                f"{float(window['start']):.1f}s - {float(window['end']):.1f}s\n"
                f"{window['text']}"
            )
        )
        transcript_lines.append(
            f"{float(window['start']):.1f}s - {float(window['end']):.1f}s: {window['text']}"
        )

    transcript_excerpt = "\n\n".join(transcript_lines).strip()
    if len(transcript_excerpt) > _MAX_CONTEXT_CHARS:
        transcript_excerpt = transcript_excerpt[:_MAX_CONTEXT_CHARS].rstrip() + "..."

    return {
        "assembled_context": "\n\n".join(blocks),
        "transcript_excerpt": transcript_excerpt,
    }


def _build_window_citations(windows: list[dict[str, Any]]) -> list[MeetingCitation]:
    citations: list[MeetingCitation] = []
    for window in windows[:4]:
        citations.append(
            MeetingCitation(
                text=str(window.get("text") or ""),
                start=float(window.get("start") or 0.0),
                end=float(window.get("end") or 0.0),
                segment_id=int(window["segment_ids"][0]) if window.get("segment_ids") else None,
            )
        )
    return citations


def _sanitize_answer_text(answer: str) -> str:
    cleaned = _normalize_text(answer)
    prefixes = (
        "我先根据当前会议里检索到的相关片段回答",
        "根据当前会议里检索到的相关片段",
        "我根据当前会议",
        "从当前会议内容看，",
    )
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip("：:，,。 ")
    return cleaned


async def _generate_grounded_answer(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    fallback_citations = _build_window_citations(selected_windows)

    prompt = [
        (
            "system",
            "你是中文会议问答助手。必须只依据提供的会议转写证据窗口回答。"
            "先给直接结论，禁止输出任何检索过程说明。"
            "如果信息不足，只能说明缺了什么，并补充会议里最接近但不足以证明的内容。"
            "摘要和最近问答只用于帮助理解问题，不得覆盖原始转写证据。"
            "只输出一个 JSON 对象，不要解释、不要 markdown。"
            'JSON 结构必须是：{"answer":"...","reasoning_summary":"...","citation_window_ids":[1,2]}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('rewritten_question') or state.get('user_question') or ''}\n\n"
                f"问题类型：{state.get('question_type') or 'fact'}\n\n"
                f"会议摘要（辅助理解）：\n{state.get('meeting_summary') or '无'}\n\n"
                f"最近问答历史（辅助理解）：\n{state.get('recent_history') or '无'}\n\n"
                f"证据窗口：\n{state.get('assembled_context') or '无'}\n\n"
                "请输出 answer、reasoning_summary 和 citation_window_ids。"
                "answer 必须先给结论，再补必要说明；不要说“我根据检索到的片段回答”。"
            ),
        ),
    ]

    try:
        result = await _invoke_structured_qa(GroundedAnswerStructuredOutput, prompt)
        return {
            "answer": _sanitize_answer_text(result.answer),
            "reasoning_summary": _normalize_text(result.reasoning_summary),
            "generated_citation_window_ids": [int(item) for item in result.citation_window_ids if item is not None],
        }
    except Exception as exc:
        logger.exception("LangGraph QA answer generation failed: %s", exc)
        result = fallback_answer(state.get("user_question") or "", fallback_citations)
        return {
            "answer": result.answer,
            "reasoning_summary": result.reasoning_summary or "",
            "generated_citation_window_ids": [int(window["window_id"]) for window in selected_windows[:2]],
        }


async def _validate_answer_groundedness(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    if not selected_windows:
        fallback = fallback_answer(state.get("user_question") or "", [])
        return {
            "answer": fallback.answer,
            "reasoning_summary": fallback.reasoning_summary or "",
            "generated_citation_window_ids": [],
        }

    valid_window_ids = {int(window["window_id"]) for window in selected_windows}
    cited_window_ids = [
        int(window_id)
        for window_id in state.get("generated_citation_window_ids") or []
        if int(window_id) in valid_window_ids
    ]
    if not cited_window_ids:
        cited_window_ids = [int(window["window_id"]) for window in selected_windows[:2]]

    answer = _sanitize_answer_text(state.get("answer") or "")
    if not answer:
        answer = "会议中暂时没有足够依据回答这个问题。"

    prompt = [
        (
            "system",
            "你是会议问答的事实校验器。检查草稿回答是否完全由证据窗口支持。"
            "如果不完全支持，就把回答改写成仅包含可证实的内容，或明确说明会议中证据不足。"
            "不要输出检索过程，不要虚构任何新事实。"
            "只输出一个 JSON 对象，不要解释。"
            'JSON 结构必须是：{"grounded":true,"answer":"...","reasoning_summary":"...","citation_window_ids":[1],"insufficiency_reason":""}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('rewritten_question') or state.get('user_question') or ''}\n\n"
                f"草稿回答：{answer}\n\n"
                f"当前依据说明：{state.get('reasoning_summary') or '无'}\n\n"
                f"证据窗口：\n{state.get('assembled_context') or '无'}\n\n"
                f"当前引用窗口：{cited_window_ids}"
            ),
        ),
    ]
    try:
        result = await _invoke_structured_qa(GroundedAnswerCheck, prompt)
    except Exception as exc:
        logger.warning("QA groundedness validation failed, keeping draft answer: %s", exc)
        return {
            "answer": answer,
            "reasoning_summary": _normalize_text(state.get("reasoning_summary") or ""),
            "generated_citation_window_ids": cited_window_ids,
        }

    validated_answer = _sanitize_answer_text(result.answer) or answer
    validated_reasoning = _normalize_text(result.reasoning_summary) or _normalize_text(state.get("reasoning_summary") or "")
    validated_ids = [int(item) for item in result.citation_window_ids if int(item) in valid_window_ids] or cited_window_ids

    if not result.grounded and result.insufficiency_reason:
        validated_reasoning = _normalize_text(result.insufficiency_reason)

    return {
        "answer": validated_answer,
        "reasoning_summary": validated_reasoning,
        "generated_citation_window_ids": validated_ids,
    }


def _segment_information_score(segment: dict[str, Any], query_terms: list[str]) -> float:
    text = _normalize_text(str(segment.get("text") or ""))
    if not text:
        return 0.0
    if text in _LOW_INFO_TEXTS:
        return 0.0
    score = min(len(text), 120) / 12.0
    score += _segment_match_bonus(text, query_terms)
    if len(text) <= 4:
        score *= 0.5
    return score


def _validate_citations(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    retrieval_terms = state.get("retrieval_terms") or []
    window_lookup = {int(window["window_id"]): window for window in selected_windows}
    cited_window_ids = [
        int(window_id)
        for window_id in state.get("generated_citation_window_ids") or []
        if int(window_id) in window_lookup
    ]
    if not cited_window_ids:
        cited_window_ids = [int(window["window_id"]) for window in selected_windows[:2]]

    segment_lookup = {int(segment["id"]): segment for segment in state.get("all_segments") or []}
    citations_payloads: list[dict[str, Any]] = []
    seen_segment_ids: set[int] = set()

    for window_id in cited_window_ids:
        window = window_lookup.get(window_id)
        if not window:
            continue
        ranked_segments = sorted(
            (
                segment_lookup.get(int(segment_id))
                for segment_id in window.get("segment_ids") or []
                if int(segment_id) in segment_lookup
            ),
            key=lambda item: -_segment_information_score(item, retrieval_terms) if item else 0.0,
        )
        for segment in ranked_segments:
            if not segment:
                continue
            segment_id = int(segment["id"])
            if segment_id in seen_segment_ids:
                continue
            if _segment_information_score(segment, retrieval_terms) <= 0:
                continue
            citations_payloads.append(
                {
                    "text": str(segment["text"]),
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "segment_id": segment_id,
                }
            )
            seen_segment_ids.add(segment_id)
            if len(citations_payloads) >= 4:
                break
        if len(citations_payloads) >= 4:
            break

    if not citations_payloads:
        for window in selected_windows[:2]:
            citations_payloads.append(
                {
                    "text": str(window.get("text") or ""),
                    "start": float(window.get("start") or 0.0),
                    "end": float(window.get("end") or 0.0),
                    "segment_id": int(window["segment_ids"][0]) if window.get("segment_ids") else None,
                }
            )

    answer = _sanitize_answer_text(state.get("answer") or "")
    reasoning = _normalize_text(state.get("reasoning_summary") or "")
    if not answer:
        fallback_result = fallback_answer(
            state.get("user_question") or "",
            [
                MeetingCitation(
                    text=item["text"],
                    start=item["start"],
                    end=item["end"],
                    segment_id=item["segment_id"],
                )
                for item in citations_payloads
            ],
        )
        answer = fallback_result.answer
        reasoning = fallback_result.reasoning_summary or ""

    return {
        "answer": answer,
        "reasoning_summary": reasoning,
        "citations_payloads": citations_payloads,
    }


def _persist_qa_record(state: QAState) -> QAState:
    with _get_session() as db:
        db.add(
            MeetingQARecord(
                meeting_id=int(state["meeting_id"]),
                question=(state.get("user_question") or "").strip(),
                answer=state.get("answer") or "",
                citations_json=json.dumps(state.get("citations_payloads") or [], ensure_ascii=False),
                reasoning_summary=state.get("reasoning_summary") or "",
            )
        )
        db.commit()
    return {}


@lru_cache(maxsize=1)
def get_qa_graph():
    builder = StateGraph(QAState)
    builder.add_node("classify_question", _classify_question)
    builder.add_node("ensure_meeting_index", _ensure_meeting_index)
    builder.add_node("rewrite_query", _rewrite_query)
    builder.add_node("retrieve_candidates", _retrieve_candidates)
    builder.add_node("expand_neighbor_windows", _expand_neighbor_windows)
    builder.add_node("rerank_candidates", _rerank_candidates)
    builder.add_node("assemble_grounded_context", _assemble_grounded_context)
    builder.add_node("generate_grounded_answer", _generate_grounded_answer)
    builder.add_node("validate_answer_groundedness", _validate_answer_groundedness)
    builder.add_node("validate_citations", _validate_citations)
    builder.add_node("persist_qa_record", _persist_qa_record)
    builder.add_edge(START, "classify_question")
    builder.add_edge("classify_question", "ensure_meeting_index")
    builder.add_edge("ensure_meeting_index", "rewrite_query")
    builder.add_edge("rewrite_query", "retrieve_candidates")
    builder.add_edge("retrieve_candidates", "expand_neighbor_windows")
    builder.add_edge("expand_neighbor_windows", "rerank_candidates")
    builder.add_edge("rerank_candidates", "assemble_grounded_context")
    builder.add_edge("assemble_grounded_context", "generate_grounded_answer")
    builder.add_edge("generate_grounded_answer", "validate_answer_groundedness")
    builder.add_edge("validate_answer_groundedness", "validate_citations")
    builder.add_edge("validate_citations", "persist_qa_record")
    builder.add_edge("persist_qa_record", END)
    return builder.compile()


async def ask_meeting_question_with_graph(
    meeting_id: int,
    question: str,
    current_user: UserProfile,
) -> MeetingAskResponse:
    _ensure_qa_runtime_ready()
    graph = get_qa_graph()
    state = await graph.ainvoke(
        {
            "meeting_id": int(meeting_id),
            "current_user": current_user,
            "user_question": question,
            "errors": [],
        }
    )
    citations = [
        MeetingCitation(
            text=str(item["text"]),
            start=float(item["start"]),
            end=float(item["end"]),
            segment_id=int(item["segment_id"]) if item.get("segment_id") is not None else None,
        )
        for item in state.get("citations_payloads") or []
    ]
    return MeetingAskResponse(
        answer=state.get("answer") or "",
        citations=citations,
        reasoning_summary=(state.get("reasoning_summary") or "").strip() or None,
    )
