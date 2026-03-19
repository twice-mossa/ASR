from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from threading import Thread
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from sqlalchemy import select

from app.ai_runtime.providers import embedding_model
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, TranscriptSegment

logger = logging.getLogger(__name__)


def _get_session():
    return SessionLocal()


def _sanitize_collection_suffix(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "-" for char in (value or "").lower())
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact[:48] or "default"


def _collection_name() -> str:
    provider = _sanitize_collection_suffix(settings.embedding_provider or "local")
    model = _sanitize_collection_suffix(settings.embedding_model or "default")
    return f"meeting-segments-{provider}-{model}"


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    persist_dir = Path(settings.vector_store_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=_collection_name(),
        persist_directory=str(persist_dir),
        embedding_function=embedding_model(require_real=settings.qa_require_real_embeddings),
    )


def _segment_doc_id(meeting_id: int, segment_id: int) -> str:
    return f"meeting:{meeting_id}:segment:{segment_id}"


def _fetch_meeting_segments(meeting_id: int) -> tuple[Meeting | None, list[TranscriptSegment]]:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return None, []
        segments = db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
            .order_by(TranscriptSegment.start.asc(), TranscriptSegment.id.asc())
        ).scalars().all()
        return meeting, segments


def _segment_to_document(meeting: Meeting, segment: TranscriptSegment) -> Document:
    return Document(
        page_content=segment.text or "",
        metadata={
            "meeting_id": int(meeting.id),
            "segment_id": int(segment.id),
            "start": float(segment.start),
            "end": float(segment.end),
            "filename": str(meeting.filename or ""),
        },
    )


def _meeting_doc_ids(store: Chroma, meeting_id: int) -> list[str]:
    try:
        payload = store.get(where={"meeting_id": int(meeting_id)}, include=[])
        return [str(item) for item in payload.get("ids") or []]
    except Exception:
        return []


def has_meeting_index(meeting_id: int) -> bool:
    store = get_vector_store()
    return bool(_meeting_doc_ids(store, meeting_id))


def delete_meeting_index(meeting_id: int) -> int:
    store = get_vector_store()
    existing_ids = _meeting_doc_ids(store, meeting_id)
    if not existing_ids:
        return 0
    store.delete(ids=existing_ids)
    return len(existing_ids)


def upsert_meeting_index(meeting_id: int) -> int:
    meeting, segments = _fetch_meeting_segments(meeting_id)
    if meeting is None or not segments:
        return 0

    store = get_vector_store()
    existing_ids = _meeting_doc_ids(store, meeting_id)
    if existing_ids:
        try:
            delete_meeting_index(meeting_id)
        except Exception:
            logger.exception("Failed to delete previous vector docs for meeting %s", meeting_id)

    documents = [_segment_to_document(meeting, segment) for segment in segments if (segment.text or "").strip()]
    ids = [_segment_doc_id(int(meeting.id), int(segment.id)) for segment in segments if (segment.text or "").strip()]
    if not documents:
        return 0

    store.add_documents(documents=documents, ids=ids)
    return len(documents)


def schedule_meeting_index_upsert(meeting_id: int) -> None:
    def _run() -> None:
        try:
            upsert_meeting_index(meeting_id)
        except Exception:
            logger.exception("Failed to update vector index for meeting %s", meeting_id)

    Thread(target=_run, name=f"meeting-index-{meeting_id}", daemon=True).start()


def ensure_meeting_index(meeting_id: int) -> None:
    if has_meeting_index(meeting_id):
        return
    upsert_meeting_index(meeting_id)


def retrieve_meeting_segments(meeting_id: int, query: str, *, k: int = 6) -> list[Document]:
    store = get_vector_store()
    docs = store.similarity_search(query=query, k=k, filter={"meeting_id": int(meeting_id)})
    return list(docs or [])


def fetch_meeting_segment_payloads(meeting_id: int) -> list[dict[str, Any]]:
    _, segments = _fetch_meeting_segments(meeting_id)
    return [
        {
            "id": int(segment.id),
            "start": float(segment.start),
            "end": float(segment.end),
            "text": str(segment.text or ""),
        }
        for segment in segments
    ]
