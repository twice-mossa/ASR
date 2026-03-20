from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.ai_runtime.knowledge_pack import ensure_meeting_knowledge_pack
from app.ai_runtime.providers import chat_model_for_qa_answer, chat_model_for_qa_planner, embedding_model
from app.ai_runtime.schemas import EvidenceWindow, GroundedAnswerStructuredOutput, QuestionIntent
from app.ai_runtime.vectorstore import retrieve_meeting_semantic_chunks
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import MeetingQARecord, MeetingSummary, TranscriptSegment
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingAskResponse, MeetingCitation, MeetingEvidenceBlock
from app.services.meeting_service import _get_owned_meeting
from app.services.qa_legacy_service import build_recent_history, fallback_answer

logger = logging.getLogger(__name__)

_SUMMARY_HINTS = ("总结", "概括", "核心", "重点", "风险", "争议", "结论", "整体", "梳理", "推荐")
_COMPARE_HINTS = ("区别", "差别", "相比", "对比", "高低", "优劣", "分别")
_STANCE_HINTS = ("建议", "倾向", "推荐", "态度", "看法", "要不要", "是否建议")
_FOLLOW_UP_HINTS = ("那", "这个", "那个", "那这个", "然后", "还有", "为什么", "具体呢", "怎么说")
_LOW_INFO_TEXTS = {"嗯", "嗯嗯", "对", "对对", "好的", "好", "会的", "是的", "行", "可以", "收到", "我觉得也可以"}


class QAState(TypedDict, total=False):
    meeting_id: int
    current_user: UserProfile
    user_question: str
    question_type: str
    question_intent: dict[str, Any]
    rewritten_question: str
    retrieval_query: str
    retrieval_terms: list[str]
    focus_topics: list[str]
    meeting_summary: str
    recent_history: str
    all_segments: list[dict[str, Any]]
    knowledge_pack: dict[str, Any]
    topic_candidates: list[dict[str, Any]]
    evidence_windows: list[dict[str, Any]]
    selected_windows: list[dict[str, Any]]
    assembled_context: str
    answer: str
    answer_type: str
    topic_labels: list[str]
    reasoning_summary: str
    generated_citation_window_ids: list[int]
    citations_payloads: list[dict[str, Any]]
    evidence_blocks_payloads: list[dict[str, Any]]
    errors: list[str]


def _get_session():
    return SessionLocal()


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
    return features[:18]


def _segment_payload(segment: TranscriptSegment) -> dict[str, Any]:
    return {
        "id": int(segment.id),
        "start": float(segment.start),
        "end": float(segment.end),
        "text": str(segment.text or ""),
    }


def _message_content_to_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
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
            return schema.model_validate_json(cleaned[start : end + 1])
        raise


async def _invoke_structured(schema, prompt, *, planner: bool = False):
    llm = chat_model_for_qa_planner() if planner else chat_model_for_qa_answer()
    raw = await llm.ainvoke(prompt)
    return _parse_structured_text(schema, _message_content_to_text(raw))


def _heuristic_question_type(question: str) -> str:
    normalized = _normalize_text(question)
    if any(token in normalized for token in _COMPARE_HINTS):
        return "compare"
    if any(token in normalized for token in _STANCE_HINTS):
        return "stance_or_suggestion"
    if any(token in normalized for token in _SUMMARY_HINTS):
        return "theme_summary"
    if any(normalized.startswith(prefix) for prefix in _FOLLOW_UP_HINTS) or len(normalized) <= 8:
        return "follow_up"
    return "fact"


def _classify_question(state: QAState) -> QAState:
    question = _normalize_text(state.get("user_question") or "")
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能为空")
    return {"question_type": _heuristic_question_type(question)}


def _ensure_qa_runtime_ready() -> None:
    try:
        embedding_model(require_real=settings.qa_require_real_embeddings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会议问答缺少可用的语义检索模型，请先配置真实 embedding provider。",
        ) from exc


def _ensure_meeting_knowledge_pack_node(state: QAState) -> QAState:
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

    knowledge_pack = ensure_meeting_knowledge_pack(meeting_id, settings.qa_knowledge_pack_wait_seconds) or {
        "status": "failed",
        "semantic_chunks": [],
        "topic_map": [],
        "discussion_points": [],
        "summary_context": {},
    }
    summary_context = knowledge_pack.get("summary_context") or {}
    summary_text = str(summary_context.get("summary") or (summary.summary if summary else "") or "")
    return {
        "all_segments": [_segment_payload(segment) for segment in segments],
        "knowledge_pack": knowledge_pack,
        "meeting_summary": summary_text,
        "recent_history": build_recent_history(recent_records),
    }


def _heuristic_question_intent(state: QAState) -> QuestionIntent:
    question = _normalize_text(state.get("user_question") or "")
    question_type = state.get("question_type") or "fact"
    terms = _extract_retrieval_terms(question)
    return QuestionIntent(
        question_type=question_type,
        rewritten_question=question,
        entities=terms[:8],
        anchors=[item for item in terms if any(char.isdigit() for char in item)][:4],
        use_recent_history=question_type == "follow_up",
        focus_topics=terms[:4],
        summary_signals=terms[:4],
    )


async def _classify_and_rewrite_question(state: QAState) -> QAState:
    fallback = _heuristic_question_intent(state)
    summary_context = (state.get("knowledge_pack") or {}).get("summary_context") or {}
    prompt = [
        (
            "system",
            "你是会议问答的查询规划器。请把问题归类并改写成适合检索会议知识包的独立问题。"
            "问题类型只能是 fact、theme_summary、compare、stance_or_suggestion、follow_up。"
            "只输出一个 JSON 对象，不要解释。"
            'JSON 结构必须是：{"question_type":"fact|theme_summary|compare|stance_or_suggestion|follow_up","rewritten_question":"...","entities":["..."],"anchors":["..."],"use_recent_history":true,"focus_topics":["..."],"summary_signals":["..."]}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('user_question') or ''}\n\n"
                f"当前初步分类：{state.get('question_type') or 'fact'}\n\n"
                f"会议摘要：{summary_context.get('summary') or '无'}\n"
                f"关键词：{', '.join(summary_context.get('keywords') or []) or '无'}\n"
                f"待办：{', '.join(summary_context.get('todos') or []) or '无'}\n\n"
                f"最近问答历史：\n{state.get('recent_history') or '无'}"
            ),
        ),
    ]
    try:
        result = await _invoke_structured(QuestionIntent, prompt, planner=True)
    except Exception as exc:
        logger.warning("QA planner rewrite failed, using heuristic intent: %s", exc)
        result = fallback

    rewritten_question = _normalize_text(result.rewritten_question) or _normalize_text(state.get("user_question") or "")
    retrieval_terms: list[str] = []
    for bucket in (
        _extract_retrieval_terms(state.get("user_question") or ""),
        result.entities,
        result.anchors,
        result.focus_topics,
        result.summary_signals,
        _extract_retrieval_terms(rewritten_question),
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
        "retrieval_terms": retrieval_terms[:16],
        "focus_topics": [str(item) for item in result.focus_topics[:6]],
    }


def _score_topic(topic: dict[str, Any], state: QAState) -> float:
    text = " ".join(
        [
            str(topic.get("title") or ""),
            str(topic.get("summary") or ""),
            " ".join(str(item) for item in topic.get("keywords") or []),
        ]
    ).lower()
    if not text.strip():
        return 0.0
    score = 0.0
    for term in state.get("retrieval_terms") or []:
        lowered = term.lower()
        if lowered and lowered in text:
            score += 3.0 if len(lowered) >= 3 else 1.0
    for label in state.get("focus_topics") or []:
        lowered = label.lower()
        if lowered and lowered in text:
            score += 2.0
    for keyword in ((state.get("knowledge_pack") or {}).get("summary_context") or {}).get("keywords") or []:
        keyword_text = str(keyword).lower()
        if keyword_text and keyword_text in text:
            score += 0.5
    return score


def _retrieve_topic_candidates(state: QAState) -> QAState:
    knowledge_pack = state.get("knowledge_pack") or {}
    topic_map = list(knowledge_pack.get("topic_map") or [])
    if not topic_map:
        summary_context = knowledge_pack.get("summary_context") or {}
        if summary_context.get("summary"):
            topic_map = [
                {
                    "title": "会议主线",
                    "summary": summary_context.get("summary") or "",
                    "keywords": list(summary_context.get("keywords") or []),
                    "supporting_chunk_ids": [],
                }
            ]
    ranked = []
    for topic in topic_map:
        candidate = dict(topic)
        candidate["score"] = _score_topic(topic, state)
        ranked.append(candidate)
    ranked.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("title") or "")))
    if state.get("question_type") == "compare":
        selected = [item for item in ranked if float(item.get("score") or 0.0) > 0][:2] or ranked[:2]
    else:
        selected = ranked[:2]
    return {"topic_candidates": selected}


def _chunk_score(chunk: dict[str, Any], state: QAState, vector_rank: int | None = None) -> float:
    text = _normalize_text(str(chunk.get("text") or "")).lower()
    if not text:
        return 0.0
    score = 0.0
    if vector_rank is not None:
        score += 10.0 / (vector_rank + 1)
    for term in state.get("retrieval_terms") or []:
        lowered = term.lower()
        if lowered and lowered in text:
            score += 2.2 if len(lowered) >= 3 else 0.8
    for label in chunk.get("topic_labels") or []:
        if any(_normalize_text(label).lower() == _normalize_text(topic.get("title") or "").lower() for topic in state.get("topic_candidates") or []):
            score += 2.5
    score += min(len(text), 160) / 90.0
    return score


def _merge_chunk_group(group: list[dict[str, Any]], window_id: int) -> dict[str, Any]:
    text = "\n".join(str(item.get("text") or "").strip() for item in group if str(item.get("text") or "").strip())
    summary = _normalize_text(text).replace("\n", " ")
    topic_labels: list[str] = []
    segment_ids: list[int] = []
    chunk_ids: list[str] = []
    for item in group:
        for label in item.get("topic_labels") or []:
            if label not in topic_labels:
                topic_labels.append(label)
        for segment_id in item.get("segment_ids") or []:
            normalized_id = int(segment_id)
            if normalized_id not in segment_ids:
                segment_ids.append(normalized_id)
        chunk_id = str(item.get("chunk_id") or "")
        if chunk_id and chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)
    return EvidenceWindow(
        window_id=window_id,
        segment_ids=segment_ids,
        chunk_ids=chunk_ids,
        start=float(group[0].get("start") or 0.0),
        end=float(group[-1].get("end") or 0.0),
        text=text,
        score=sum(float(item.get("retrieval_score") or 0.0) for item in group),
        title=str(group[0].get("title") or (topic_labels[0] if topic_labels else "相关证据")),
        summary=summary[:120],
        topic_labels=topic_labels,
    ).model_dump()


def _retrieve_evidence_blocks(state: QAState) -> QAState:
    knowledge_pack = state.get("knowledge_pack") or {}
    chunks = list(knowledge_pack.get("semantic_chunks") or [])
    if not chunks:
        chunks = [
            {
                "chunk_id": f"segment-{segment['id']}",
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "segment_ids": [segment["id"]],
                "title": f"片段 {index + 1}",
                "topic_labels": [],
            }
            for index, segment in enumerate(state.get("all_segments") or [])
        ]

    chunk_lookup = {str(chunk.get("chunk_id") or ""): dict(chunk) for chunk in chunks if str(chunk.get("chunk_id") or "")}
    vector_docs = retrieve_meeting_semantic_chunks(
        int(state["meeting_id"]),
        state.get("retrieval_query") or state.get("user_question") or "",
        k=max(4, settings.qa_retrieval_top_k),
    )
    for rank, doc in enumerate(vector_docs, start=1):
        chunk_id = str(doc.metadata.get("chunk_id") or "")
        if chunk_id not in chunk_lookup:
            continue
        chunk_lookup[chunk_id]["retrieval_score"] = _chunk_score(chunk_lookup[chunk_id], state, rank)

    for chunk in chunk_lookup.values():
        chunk["retrieval_score"] = max(float(chunk.get("retrieval_score") or 0.0), _chunk_score(chunk, state))

    ranked_chunks = sorted(
        [chunk for chunk in chunk_lookup.values() if float(chunk.get("retrieval_score") or 0.0) > 0],
        key=lambda item: (-float(item.get("retrieval_score") or 0.0), float(item.get("start") or 0.0)),
    )
    if not ranked_chunks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前会议里没有检索到可用于回答的有效片段")

    chosen_chunks = ranked_chunks[: max(settings.qa_retrieval_top_k, settings.qa_keyword_top_k)]
    selected_ids = {str(chunk.get("chunk_id") or "") for chunk in chosen_chunks}
    all_chunks_sorted = sorted(chunks, key=lambda item: float(item.get("start") or 0.0))
    expanded_indexes: set[int] = set()
    for index, chunk in enumerate(all_chunks_sorted):
        if str(chunk.get("chunk_id") or "") not in selected_ids:
            continue
        start = max(0, index - max(1, settings.qa_neighbor_window))
        end = min(len(all_chunks_sorted), index + max(1, settings.qa_neighbor_window) + 1)
        for neighbor in range(start, end):
            expanded_indexes.add(neighbor)

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    last_index = None
    for index in sorted(expanded_indexes):
        chunk = dict(all_chunks_sorted[index])
        chunk["retrieval_score"] = float(chunk_lookup.get(str(chunk.get("chunk_id") or ""), {}).get("retrieval_score") or _chunk_score(chunk, state) * 0.6)
        if last_index is None or index == last_index + 1:
            current_group.append(chunk)
        else:
            groups.append(current_group)
            current_group = [chunk]
        last_index = index
    if current_group:
        groups.append(current_group)

    windows = [_merge_chunk_group(group, window_id) for window_id, group in enumerate(groups, start=1)]
    windows.sort(key=lambda item: (-float(item.get("score") or 0.0), float(item.get("start") or 0.0)))
    return {"evidence_windows": windows}


def _rerank_evidence_blocks(state: QAState) -> QAState:
    windows = list(state.get("evidence_windows") or [])
    if not windows:
        return {"selected_windows": []}
    if state.get("question_type") == "compare":
        selected: list[dict[str, Any]] = []
        used_labels: set[str] = set()
        for window in windows:
            labels = [str(label) for label in window.get("topic_labels") or []]
            fresh = next((label for label in labels if label not in used_labels), None)
            if fresh or not selected:
                selected.append(window)
                if fresh:
                    used_labels.add(fresh)
            if len(selected) >= 2:
                break
        return {"selected_windows": selected[: max(1, settings.qa_rerank_top_n)] or windows[:2]}
    return {"selected_windows": windows[: max(1, settings.qa_rerank_top_n)]}


def _assemble_grounded_context(state: QAState) -> QAState:
    blocks = []
    for window in state.get("selected_windows") or []:
        blocks.append(
            (
                f"[window_id={int(window['window_id'])}] {float(window['start']):.1f}s - {float(window['end']):.1f}s\n"
                f"主题：{', '.join(window.get('topic_labels') or []) or window.get('title') or '相关证据'}\n"
                f"内容：{window.get('text') or ''}"
            )
        )
    return {"assembled_context": "\n\n".join(blocks)}


def _build_window_citations(windows: list[dict[str, Any]]) -> list[MeetingCitation]:
    citations: list[MeetingCitation] = []
    for window in windows[:4]:
        citations.append(
            MeetingCitation(
                text=str(window.get("summary") or window.get("text") or ""),
                start=float(window.get("start") or 0.0),
                end=float(window.get("end") or 0.0),
                segment_id=int(window["segment_ids"][0]) if window.get("segment_ids") else None,
            )
        )
    return citations


async def _generate_topic_grounded_answer(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    summary_context = (state.get("knowledge_pack") or {}).get("summary_context") or {}
    discussion_points = (state.get("knowledge_pack") or {}).get("discussion_points") or []
    topic_candidates = state.get("topic_candidates") or []
    fallback_citations = _build_window_citations(selected_windows)
    if not selected_windows:
        fallback = fallback_answer(state.get("user_question") or "", fallback_citations)
        return {
            "answer": fallback.answer,
            "reasoning_summary": fallback.reasoning_summary or "",
            "answer_type": state.get("question_type") or "fact",
            "topic_labels": [],
            "generated_citation_window_ids": [],
        }

    prompt = [
        (
            "system",
            "你是中文会议问答助手。必须以会议转写证据块为事实锚点作答。"
            "可以借助摘要、关键词、待办帮助识别主题，但不能只复述摘要。"
            "先给直接结论，再给必要展开。compare 类问题必须按“对象 A / 对象 B / 核心区别”结构组织。"
            "如果摘要提到了某个结论但原文证据不足，要明确说“摘要提到了 X，但原文证据不足以完全确认”。"
            "只输出一个 JSON 对象，不要解释。"
            'JSON 结构必须是：{"answer":"...","reasoning_summary":"...","citation_window_ids":[1,2],"answer_type":"fact|theme_summary|compare|stance_or_suggestion|follow_up","topic_labels":["..."]}',
        ),
        (
            "human",
            (
                f"用户问题：{state.get('rewritten_question') or state.get('user_question') or ''}\n\n"
                f"问题类型：{state.get('question_type') or 'fact'}\n\n"
                f"会议摘要：{summary_context.get('summary') or '无'}\n"
                f"关键词：{', '.join(summary_context.get('keywords') or []) or '无'}\n"
                f"待办：{', '.join(summary_context.get('todos') or []) or '无'}\n\n"
                f"主题候选：{json.dumps(topic_candidates, ensure_ascii=False)}\n\n"
                f"讨论要点：{json.dumps(discussion_points, ensure_ascii=False)}\n\n"
                f"最近问答历史：{state.get('recent_history') or '无'}\n\n"
                f"证据块：\n{state.get('assembled_context') or '无'}"
            ),
        ),
    ]
    try:
        result = await _invoke_structured(GroundedAnswerStructuredOutput, prompt)
        answer = _normalize_text(result.answer)
        if not answer:
            raise ValueError("empty answer")
        return {
            "answer": answer,
            "reasoning_summary": _normalize_text(result.reasoning_summary),
            "answer_type": result.answer_type or state.get("question_type") or "fact",
            "topic_labels": [str(item) for item in result.topic_labels[:6]],
            "generated_citation_window_ids": [int(item) for item in result.citation_window_ids if item is not None],
        }
    except Exception as exc:
        logger.exception("QA answer generation failed, using fallback answer: %s", exc)
        fallback = fallback_answer(state.get("user_question") or "", fallback_citations)
        labels = []
        for window in selected_windows:
            for label in window.get("topic_labels") or []:
                if label not in labels:
                    labels.append(label)
        return {
            "answer": fallback.answer,
            "reasoning_summary": fallback.reasoning_summary or "",
            "answer_type": state.get("question_type") or "fact",
            "topic_labels": labels[:4],
            "generated_citation_window_ids": [int(window["window_id"]) for window in selected_windows[:2]],
        }


def _segment_information_score(segment: dict[str, Any], query_terms: list[str]) -> float:
    text = _normalize_text(str(segment.get("text") or ""))
    if not text or text in _LOW_INFO_TEXTS:
        return 0.0
    score = min(len(text), 120) / 10.0
    lowered = text.lower()
    for term in query_terms:
        needle = term.lower()
        if needle and needle in lowered:
            score += 2.4 if len(needle) >= 3 else 0.8
    if len(text) <= 4:
        score *= 0.5
    return score


def _validate_citations(state: QAState) -> QAState:
    selected_windows = state.get("selected_windows") or []
    if not selected_windows:
        fallback = fallback_answer(state.get("user_question") or "", [])
        return {
            "answer": fallback.answer,
            "reasoning_summary": fallback.reasoning_summary or "",
            "citations_payloads": [],
            "evidence_blocks_payloads": [],
        }

    window_lookup = {int(window["window_id"]): window for window in selected_windows}
    cited_window_ids = [
        int(window_id)
        for window_id in state.get("generated_citation_window_ids") or []
        if int(window_id) in window_lookup
    ]
    if not cited_window_ids:
        cited_window_ids = [int(window["window_id"]) for window in selected_windows[:2]]

    segment_lookup = {int(segment["id"]): segment for segment in state.get("all_segments") or []}
    retrieval_terms = state.get("retrieval_terms") or []
    citations_payloads: list[dict[str, Any]] = []
    evidence_blocks_payloads: list[dict[str, Any]] = []
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
        block_citations = []
        for segment in ranked_segments[:4]:
            if not segment:
                continue
            payload = {
                "text": str(segment["text"]),
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "segment_id": int(segment["id"]),
            }
            block_citations.append(payload)
            if payload["segment_id"] not in seen_segment_ids:
                citations_payloads.append(payload)
                seen_segment_ids.add(payload["segment_id"])
        if not block_citations:
            block_citations = [
                {
                    "text": str(window.get("summary") or window.get("text") or ""),
                    "start": float(window.get("start") or 0.0),
                    "end": float(window.get("end") or 0.0),
                    "segment_id": int(window["segment_ids"][0]) if window.get("segment_ids") else None,
                }
            ]
        evidence_blocks_payloads.append(
            {
                "title": str(window.get("title") or (window.get("topic_labels") or ["相关证据"])[0]),
                "start": float(window.get("start") or 0.0),
                "end": float(window.get("end") or 0.0),
                "summary": str(window.get("summary") or ""),
                "citations": block_citations,
            }
        )

    if not citations_payloads:
        citations_payloads = [item.model_dump() for item in _build_window_citations(selected_windows)]

    answer = _normalize_text(state.get("answer") or "")
    reasoning = _normalize_text(state.get("reasoning_summary") or "")
    if not answer:
        fallback = fallback_answer(
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
        answer = fallback.answer
        reasoning = fallback.reasoning_summary or ""

    return {
        "answer": answer,
        "reasoning_summary": reasoning,
        "citations_payloads": citations_payloads[:6],
        "evidence_blocks_payloads": evidence_blocks_payloads[:3],
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
                answer_type=state.get("answer_type") or "fact",
                topic_labels_json=json.dumps(state.get("topic_labels") or [], ensure_ascii=False),
                evidence_blocks_json=json.dumps(state.get("evidence_blocks_payloads") or [], ensure_ascii=False),
            )
        )
        db.commit()
    return {}


@lru_cache(maxsize=1)
def get_qa_graph():
    builder = StateGraph(QAState)
    builder.add_node("classify_question", _classify_question)
    builder.add_node("ensure_meeting_knowledge_pack", _ensure_meeting_knowledge_pack_node)
    builder.add_node("classify_and_rewrite_question", _classify_and_rewrite_question)
    builder.add_node("retrieve_topic_candidates", _retrieve_topic_candidates)
    builder.add_node("retrieve_evidence_blocks", _retrieve_evidence_blocks)
    builder.add_node("rerank_evidence_blocks", _rerank_evidence_blocks)
    builder.add_node("assemble_grounded_context", _assemble_grounded_context)
    builder.add_node("generate_topic_grounded_answer", _generate_topic_grounded_answer)
    builder.add_node("validate_citations", _validate_citations)
    builder.add_node("persist_qa_record", _persist_qa_record)
    builder.add_edge(START, "classify_question")
    builder.add_edge("classify_question", "ensure_meeting_knowledge_pack")
    builder.add_edge("ensure_meeting_knowledge_pack", "classify_and_rewrite_question")
    builder.add_edge("classify_and_rewrite_question", "retrieve_topic_candidates")
    builder.add_edge("retrieve_topic_candidates", "retrieve_evidence_blocks")
    builder.add_edge("retrieve_evidence_blocks", "rerank_evidence_blocks")
    builder.add_edge("rerank_evidence_blocks", "assemble_grounded_context")
    builder.add_edge("assemble_grounded_context", "generate_topic_grounded_answer")
    builder.add_edge("generate_topic_grounded_answer", "validate_citations")
    builder.add_edge("validate_citations", "persist_qa_record")
    builder.add_edge("persist_qa_record", END)
    return builder.compile()


async def ask_meeting_question_with_graph(meeting_id: int, question: str, current_user: UserProfile) -> MeetingAskResponse:
    _ensure_qa_runtime_ready()
    state = await get_qa_graph().ainvoke(
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
    evidence_blocks = [
        MeetingEvidenceBlock(
            title=str(item.get("title") or "证据块"),
            start=float(item.get("start") or 0.0),
            end=float(item.get("end") or 0.0),
            summary=str(item.get("summary") or ""),
            citations=[
                MeetingCitation(
                    text=str(citation["text"]),
                    start=float(citation["start"]),
                    end=float(citation["end"]),
                    segment_id=int(citation["segment_id"]) if citation.get("segment_id") is not None else None,
                )
                for citation in item.get("citations") or []
            ],
        )
        for item in state.get("evidence_blocks_payloads") or []
    ]
    return MeetingAskResponse(
        answer=state.get("answer") or "",
        citations=citations,
        reasoning_summary=(state.get("reasoning_summary") or "").strip() or None,
        answer_type=state.get("answer_type") or (state.get("question_type") or "fact"),
        topic_labels=[str(item) for item in state.get("topic_labels") or []],
        evidence_blocks=evidence_blocks,
    )
