from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import MeetingQARecord, MeetingSummary, TranscriptSegment
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingAskResponse, MeetingCitation
from app.services.meeting_service import _get_owned_meeting

logger = logging.getLogger(__name__)

_QUESTION_STOPWORDS = {
    "的",
    "了",
    "吗",
    "呢",
    "啊",
    "呀",
    "和",
    "与",
    "及",
    "是",
    "在",
    "把",
    "就",
    "都",
    "还",
    "要",
    "请",
    "一下",
    "这个",
    "那个",
    "哪些",
    "什么",
    "如何",
    "怎么",
    "有没有",
    "会议",
    "内容",
    "根据",
    "结合",
    "一下子",
}

_MAX_TRANSCRIPT_CONTEXT = 6000


def _get_session():
    return SessionLocal()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_query_features(question: str) -> list[str]:
    normalized = _normalize_text(question)
    features: list[str] = []

    zh_chunks = re.findall(r"[\u4e00-\u9fff]{2,16}", normalized)
    en_terms = re.findall(r"[a-z0-9_-]{2,}", normalized)

    for chunk in zh_chunks:
        if chunk in _QUESTION_STOPWORDS:
            continue
        if chunk not in features:
            features.append(chunk)
        for size in (2, 3):
            if len(chunk) <= size:
                continue
            for index in range(len(chunk) - size + 1):
                gram = chunk[index : index + size]
                if gram not in _QUESTION_STOPWORDS and gram not in features:
                    features.append(gram)

    for term in en_terms:
        if term not in _QUESTION_STOPWORDS and term not in features:
            features.append(term)

    return features


def _segment_score(text: str, features: list[str], question: str) -> float:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return 0.0

    score = 0.0
    for feature in features:
        if feature in normalized_text:
            score += 3.0 if len(feature) >= 3 else 1.5

    shared_chars = {char for char in question if "\u4e00" <= char <= "\u9fff" and char in normalized_text}
    score += len(shared_chars) * 0.5

    if normalized_text in question or question in normalized_text:
        score += 2.0

    score += min(len(normalized_text), 120) / 300.0
    return score


def pick_segment_indexes(segments: list[TranscriptSegment], question: str, limit: int = 4) -> list[int]:
    features = _extract_query_features(question)
    ranked = sorted(
        ((_segment_score(segment.text, features, question), index) for index, segment in enumerate(segments)),
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )

    chosen = [index for score, index in ranked if score > 0][:limit]
    if not chosen:
        chosen = [index for _, index in ranked[:limit]]

    expanded: list[int] = []
    for index in chosen:
        start = max(0, index - 1)
        end = min(len(segments), index + 2)
        for neighbor in range(start, end):
            if neighbor not in expanded:
                expanded.append(neighbor)

    return sorted(expanded)


def build_citations_from_indexes(
    segments: list[TranscriptSegment],
    indexes: list[int],
    limit: int = 4,
) -> list[MeetingCitation]:
    selected_indexes = indexes[:limit]
    return [
        MeetingCitation(
            text=segments[index].text,
            start=float(segments[index].start),
            end=float(segments[index].end),
            segment_id=int(segments[index].id) if getattr(segments[index], "id", None) is not None else None,
        )
        for index in selected_indexes
    ]


def build_context_segments(segments: list[TranscriptSegment], indexes: list[int]) -> str:
    lines = []
    for offset, index in enumerate(indexes, start=1):
        segment = segments[index]
        lines.append(f"[{offset}] {segment.start:.1f}s - {segment.end:.1f}s: {segment.text}")
    return "\n".join(lines)


def build_recent_history(records: list[MeetingQARecord]) -> str:
    if not records:
        return "无"

    lines = []
    for index, record in enumerate(records[-4:], start=1):
        lines.append(f"{index}. Q: {record.question}")
        lines.append(f"   A: {record.answer}")
    return "\n".join(lines)


def build_transcript_excerpt(segments: list[TranscriptSegment], indexes: list[int]) -> str:
    if not segments:
        return ""

    excerpt_lines = []
    for index in indexes:
        segment = segments[index]
        excerpt_lines.append(f"{segment.start:.1f}s - {segment.end:.1f}s: {segment.text}")

    excerpt = "\n".join(excerpt_lines).strip()
    if len(excerpt) <= _MAX_TRANSCRIPT_CONTEXT:
        return excerpt
    return excerpt[:_MAX_TRANSCRIPT_CONTEXT].rstrip() + "..."


def fallback_answer(question: str, citations: list[MeetingCitation]) -> MeetingAskResponse:
    if not citations:
        return MeetingAskResponse(
            answer="当前会议里还没有足够的转写内容来回答这个问题。",
            citations=[],
            reasoning_summary="未找到可引用的会议片段。",
        )

    lead = citations[0]
    answer = f"会议里能直接找到的相关内容是：{lead.text}"
    if len(citations) > 1:
        answer += "\n\n补充依据：\n" + "\n".join(
            f"{citation.start:.1f}s - {citation.end:.1f}s：{citation.text}" for citation in citations[1:3]
        )

    return MeetingAskResponse(
        answer=answer,
        citations=citations,
        reasoning_summary=f"已围绕问题“{question}”检索会议原文，并保留最相关的引用片段。",
    )


async def _generate_answer_with_minimax(
    question: str,
    summary_text: str,
    transcript_excerpt: str,
    context_segments: str,
    recent_history: str,
    citations: list[MeetingCitation],
) -> MeetingAskResponse:
    if not settings.minimax_api_key:
        return fallback_answer(question, citations)

    base_url = getattr(settings, "minimax_base_url", "https://api.minimaxi.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": "MiniMax-M2.5",
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                "你是一个会议问答助手。必须优先依据提供的会议摘要、相关转写片段和最近问答历史回答。"
                "只有在这些内容确实不足时，才能说明信息不足；不要为了保守而轻易拒答。"
                '请严格输出 JSON：{"answer":"...","reasoning_summary":"..."}。'
                "answer 要直接回答问题，禁止解释自己在做检索；reasoning_summary 用一句话说明主要依据。"
            ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n\n"
                    f"会议摘要：\n{summary_text or '无'}\n\n"
                    f"最近问答历史：\n{recent_history}\n\n"
                    f"重点转写片段：\n{context_segments or '无'}\n\n"
                    f"扩展转写上下文：\n{transcript_excerpt or '无'}\n\n"
                    "请根据这些内容回答。如果能从现有内容中合理归纳，就直接回答；"
                    "只有完全找不到依据时才说信息不足。"
                ),
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
    except Exception as exc:
        logger.exception("Meeting QA call failed: %s", exc)
        return fallback_answer(question, citations)

    choices = body.get("choices")
    content = None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) or {}
        content = message.get("content")
    if not content and "output" in body:
        content = body["output"]
    if not content:
        return fallback_answer(question, citations)

    cleaned = str(content).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return fallback_answer(question, citations)

    answer = str(parsed.get("answer") or "").strip()
    reasoning_summary = str(parsed.get("reasoning_summary") or "").strip()
    if not answer:
        return fallback_answer(question, citations)

    return MeetingAskResponse(
        answer=answer,
        citations=citations,
        reasoning_summary=reasoning_summary or None,
    )


async def ask_meeting_question_legacy(meeting_id: int, question: str, current_user: UserProfile) -> MeetingAskResponse:
    normalized_question = question.strip()
    if not normalized_question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能为空")

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

        indexes = pick_segment_indexes(segments, normalized_question)
        citations = build_citations_from_indexes(segments, indexes)
        context_segments = build_context_segments(segments, indexes[:4])
        transcript_excerpt = build_transcript_excerpt(segments, indexes)
        recent_history = build_recent_history(recent_records)
        summary_text = summary.summary if summary and summary.summary else ""

        result = await _generate_answer_with_minimax(
            normalized_question,
            summary_text,
            transcript_excerpt,
            context_segments,
            recent_history,
            citations,
        )

        db.add(
            MeetingQARecord(
                meeting_id=meeting.id,
                question=normalized_question,
                answer=result.answer,
                citations_json=json.dumps([citation.model_dump() for citation in result.citations], ensure_ascii=False),
                reasoning_summary=result.reasoning_summary or "",
            )
        )
        db.commit()
        return result
