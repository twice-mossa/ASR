from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from threading import Thread
from typing import Any

from sqlalchemy import select

from app.ai_runtime.providers import chat_model_for_qa_planner
from app.ai_runtime.schemas import MeetingKnowledgePackStructuredOutput, SemanticChunk, SummaryContext, TopicNode
from app.ai_runtime.vectorstore import (
    delete_meeting_semantic_chunks,
    schedule_meeting_semantic_chunk_upsert,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingKnowledgePack, MeetingSummary, TranscriptSegment

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 280
_MAX_TOPIC_COUNT = 8


def _get_session():
    return SessionLocal()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


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


def _load_meeting_materials(meeting_id: int) -> tuple[Meeting | None, list[TranscriptSegment], MeetingSummary | None]:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return None, [], None
        segments = db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
            .order_by(TranscriptSegment.start.asc(), TranscriptSegment.id.asc())
        ).scalars().all()
        summary = db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)).scalar_one_or_none()
        return meeting, segments, summary


def _build_summary_context(summary: MeetingSummary | None) -> SummaryContext:
    if summary is None:
        return SummaryContext()

    try:
        keywords = [str(item) for item in json.loads(summary.keywords_json or "[]")]
    except json.JSONDecodeError:
        keywords = []
    try:
        todos = [str(item) for item in json.loads(summary.todos_json or "[]")]
    except json.JSONDecodeError:
        todos = []

    return SummaryContext(summary=summary.summary or "", keywords=keywords, todos=todos)


def _should_split(current_text: str, next_text: str, current_end: float | None, next_start: float) -> bool:
    if not current_text:
        return False
    if len(current_text) >= _MAX_CHUNK_CHARS:
        return True
    if current_end is not None and next_start - current_end > 12:
        return True
    return bool(re.search(r"[。！？；.!?;]\s*$", current_text))


def build_semantic_chunks(segments: list[TranscriptSegment]) -> list[dict[str, Any]]:
    chunks: list[SemanticChunk] = []
    buffer_segments: list[TranscriptSegment] = []

    def flush() -> None:
        nonlocal buffer_segments
        if not buffer_segments:
            return
        text = "\n".join(_normalize_text(segment.text or "") for segment in buffer_segments if _normalize_text(segment.text or ""))
        if not text:
            buffer_segments = []
            return
        chunk_index = len(chunks) + 1
        first = buffer_segments[0]
        last = buffer_segments[-1]
        title = _normalize_text(text[:28]).rstrip("，,。;；:：")
        chunks.append(
            SemanticChunk(
                chunk_id=f"chunk-{chunk_index}",
                start=float(first.start),
                end=float(last.end),
                text=text,
                segment_ids=[int(segment.id) for segment in buffer_segments],
                title=title or f"片段 {chunk_index}",
            )
        )
        buffer_segments = []

    for segment in segments:
        if not _normalize_text(segment.text or ""):
            continue
        if buffer_segments:
            current_text = "\n".join(_normalize_text(item.text or "") for item in buffer_segments)
            if _should_split(current_text, segment.text or "", float(buffer_segments[-1].end), float(segment.start)):
                flush()
        buffer_segments.append(segment)
    flush()
    return [chunk.model_dump() for chunk in chunks]


async def _extract_topics_with_model(
    transcript_excerpt: str,
    summary_context: SummaryContext,
    chunk_summaries: list[dict[str, Any]],
) -> MeetingKnowledgePackStructuredOutput:
    prompt = [
        (
            "system",
            "你是中文会议主题整理器。请根据会议转写和已有摘要，提炼会议主题和讨论要点。"
            "只输出一个 JSON 对象，不要输出解释，不要 markdown。"
            'JSON 结构必须是：{"topic_map":[{"title":"...","summary":"...","keywords":["..."],"supporting_chunk_ids":["chunk-1"]}],"discussion_points":["..."]}',
        ),
        (
            "human",
            (
                f"会议摘要：{summary_context.summary or '无'}\n"
                f"关键词：{', '.join(summary_context.keywords) or '无'}\n"
                f"待办：{', '.join(summary_context.todos) or '无'}\n\n"
                "语义块：\n"
                + "\n\n".join(
                    f"{item['chunk_id']} {item['start']:.1f}-{item['end']:.1f}s\n{item['text']}"
                    for item in chunk_summaries[:18]
                )
                + f"\n\n转写摘要片段：\n{transcript_excerpt}"
            ),
        ),
    ]
    llm = chat_model_for_qa_planner()
    raw = await llm.ainvoke(prompt)
    return _parse_structured_text(MeetingKnowledgePackStructuredOutput, _message_content_to_text(raw))


def _fallback_topic_map(chunks: list[dict[str, Any]], summary_context: SummaryContext) -> MeetingKnowledgePackStructuredOutput:
    topics: list[TopicNode] = []
    discussion_points: list[str] = []
    keywords = list(summary_context.keywords)
    if summary_context.summary:
        discussion_points.append(summary_context.summary)
    discussion_points.extend(summary_context.todos[:3])

    for index, chunk in enumerate(chunks[: min(_MAX_TOPIC_COUNT, len(chunks))], start=1):
        local_keywords = []
        for keyword in keywords:
            if keyword and keyword in str(chunk.get("text") or ""):
                local_keywords.append(keyword)
        if not local_keywords:
            local_keywords = _guess_keywords(str(chunk.get("text") or ""))
        topics.append(
            TopicNode(
                title=str(chunk.get("title") or f"主题 {index}"),
                summary=_normalize_text(str(chunk.get("text") or ""))[:120],
                keywords=local_keywords[:6],
                supporting_chunk_ids=[str(chunk.get("chunk_id") or "")],
            )
        )

    return MeetingKnowledgePackStructuredOutput(topic_map=topics, discussion_points=discussion_points[:8])


def _guess_keywords(text: str) -> list[str]:
    matches = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z0-9_-]{2,}", _normalize_text(text))
    keywords: list[str] = []
    for match in matches:
        if match not in keywords:
            keywords.append(match)
        if len(keywords) >= 6:
            break
    return keywords


def _apply_topic_labels(chunks: list[dict[str, Any]], topic_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels_by_chunk: dict[str, list[str]] = {}
    for topic in topic_map:
        title = str(topic.get("title") or "").strip()
        for chunk_id in topic.get("supporting_chunk_ids") or []:
            normalized_chunk_id = str(chunk_id)
            if not normalized_chunk_id:
                continue
            labels_by_chunk.setdefault(normalized_chunk_id, [])
            if title and title not in labels_by_chunk[normalized_chunk_id]:
                labels_by_chunk[normalized_chunk_id].append(title)

    next_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        updated = dict(chunk)
        updated["topic_labels"] = labels_by_chunk.get(str(chunk.get("chunk_id") or ""), [])
        next_chunks.append(updated)
    return next_chunks


async def refresh_meeting_knowledge_pack(meeting_id: int) -> None:
    meeting, segments, summary = _load_meeting_materials(meeting_id)
    if meeting is None:
        return

    if not segments or not (meeting.transcript_text or "").strip():
        with _get_session() as db:
            record = db.execute(select(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id)).scalar_one_or_none()
            if record is None:
                record = MeetingKnowledgePack(meeting_id=meeting_id)
                db.add(record)
            record.status = "failed"
            record.semantic_chunks_json = "[]"
            record.topic_map_json = "[]"
            record.discussion_points_json = "[]"
            record.summary_context_json = "{}"
            db.commit()
        delete_meeting_semantic_chunks(meeting_id)
        return

    with _get_session() as db:
        record = db.execute(select(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id)).scalar_one_or_none()
        if record is None:
            record = MeetingKnowledgePack(meeting_id=meeting_id)
            db.add(record)
        record.status = "processing"
        db.commit()

    summary_context = _build_summary_context(summary)
    semantic_chunks = build_semantic_chunks(segments)
    transcript_excerpt = _normalize_text(meeting.transcript_text or "")[:2400]

    try:
        structured = await _extract_topics_with_model(transcript_excerpt, summary_context, semantic_chunks)
    except Exception as exc:
        logger.warning("Knowledge pack planner failed for meeting %s, using fallback topics: %s", meeting_id, exc)
        structured = _fallback_topic_map(semantic_chunks, summary_context)

    topic_map = [topic.model_dump() for topic in structured.topic_map[:_MAX_TOPIC_COUNT]]
    semantic_chunks = _apply_topic_labels(semantic_chunks, topic_map)
    summary_context_payload = summary_context.model_dump()
    discussion_points = [str(item) for item in structured.discussion_points[:12]]

    with _get_session() as db:
        record = db.execute(select(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id)).scalar_one_or_none()
        if record is None:
            record = MeetingKnowledgePack(meeting_id=meeting_id)
            db.add(record)
        record.status = "ready"
        record.semantic_chunks_json = json.dumps(semantic_chunks, ensure_ascii=False)
        record.topic_map_json = json.dumps(topic_map, ensure_ascii=False)
        record.discussion_points_json = json.dumps(discussion_points, ensure_ascii=False)
        record.summary_context_json = json.dumps(summary_context_payload, ensure_ascii=False)
        record.version = 1
        db.commit()

    schedule_meeting_semantic_chunk_upsert(meeting_id, semantic_chunks)


def schedule_meeting_knowledge_pack_refresh(meeting_id: int) -> None:
    def _run() -> None:
        import asyncio

        try:
            asyncio.run(refresh_meeting_knowledge_pack(meeting_id))
        except Exception:
            logger.exception("Failed to refresh knowledge pack for meeting %s", meeting_id)

    Thread(target=_run, name=f"meeting-knowledge-pack-{meeting_id}", daemon=True).start()


def get_meeting_knowledge_pack(meeting_id: int) -> dict[str, Any] | None:
    with _get_session() as db:
        record = db.execute(select(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id)).scalar_one_or_none()
        if record is None:
            return None
        try:
            semantic_chunks = json.loads(record.semantic_chunks_json or "[]")
        except json.JSONDecodeError:
            semantic_chunks = []
        try:
            topic_map = json.loads(record.topic_map_json or "[]")
        except json.JSONDecodeError:
            topic_map = []
        try:
            discussion_points = json.loads(record.discussion_points_json or "[]")
        except json.JSONDecodeError:
            discussion_points = []
        try:
            summary_context = json.loads(record.summary_context_json or "{}")
        except json.JSONDecodeError:
            summary_context = {}
        return {
            "meeting_id": int(record.meeting_id),
            "status": str(record.status or "pending"),
            "semantic_chunks": semantic_chunks,
            "topic_map": topic_map,
            "discussion_points": discussion_points,
            "summary_context": summary_context,
            "version": int(record.version or 1),
        }


def ensure_meeting_knowledge_pack(meeting_id: int, wait_seconds: int | None = None) -> dict[str, Any] | None:
    wait_limit = max(0, int(wait_seconds if wait_seconds is not None else settings.qa_knowledge_pack_wait_seconds))
    pack = get_meeting_knowledge_pack(meeting_id)
    if pack and pack["status"] == "ready":
        return pack

    if pack is None or pack["status"] in {"failed", "pending"}:
        schedule_meeting_knowledge_pack_refresh(meeting_id)

    deadline = time.time() + wait_limit
    while time.time() < deadline:
        pack = get_meeting_knowledge_pack(meeting_id)
        if pack and pack["status"] == "ready":
            return pack
        time.sleep(0.4)

    return get_meeting_knowledge_pack(meeting_id)


def delete_meeting_knowledge_pack(meeting_id: int) -> None:
    with _get_session() as db:
        db.execute(
            MeetingKnowledgePack.__table__.delete().where(MeetingKnowledgePack.meeting_id == meeting_id)
        )
        db.commit()
    try:
        delete_meeting_semantic_chunks(meeting_id)
    except Exception:
        logger.exception("Failed to delete semantic chunk index for meeting %s", meeting_id)
