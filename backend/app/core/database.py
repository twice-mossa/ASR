from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _engine_kwargs() -> dict:
    if settings.database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, future=True, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def init_database() -> None:
    from app.models import (
        Meeting,
        MeetingKnowledgePack,
        MeetingQARecord,
        MeetingSummary,
        MeetingSummaryEmailDelivery,
        TranscriptSegment,
        User,
    )

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_optional_columns()


def _ensure_optional_columns() -> None:
    inspector = inspect(engine)
    statements: list[str] = []
    post_update_statements: list[str] = []
    if inspector.has_table("meeting_qa_records"):
        qa_columns = {column["name"] for column in inspector.get_columns("meeting_qa_records")}
        if "answer_type" not in qa_columns:
            statements.append("ALTER TABLE meeting_qa_records ADD COLUMN answer_type VARCHAR(32) NOT NULL DEFAULT 'fact'")
        if "topic_labels_json" not in qa_columns:
            statements.append("ALTER TABLE meeting_qa_records ADD COLUMN topic_labels_json TEXT NULL")
            post_update_statements.append("UPDATE meeting_qa_records SET topic_labels_json='[]' WHERE topic_labels_json IS NULL")
        if "evidence_blocks_json" not in qa_columns:
            statements.append("ALTER TABLE meeting_qa_records ADD COLUMN evidence_blocks_json TEXT NULL")
            post_update_statements.append("UPDATE meeting_qa_records SET evidence_blocks_json='[]' WHERE evidence_blocks_json IS NULL")

    if inspector.has_table("transcript_segments"):
        transcript_columns = {column["name"] for column in inspector.get_columns("transcript_segments")}
        if "speaker_label" not in transcript_columns:
            statements.append("ALTER TABLE transcript_segments ADD COLUMN speaker_label VARCHAR(64) NULL")
        if "speaker_confidence" not in transcript_columns:
            statements.append("ALTER TABLE transcript_segments ADD COLUMN speaker_confidence FLOAT NULL")

    if inspector.has_table("meetings"):
        meeting_columns = {column["name"] for column in inspector.get_columns("meetings")}
        if "diarization_status" not in meeting_columns:
            statements.append("ALTER TABLE meetings ADD COLUMN diarization_status VARCHAR(16) NOT NULL DEFAULT 'not_requested'")
        if "diarization_error_message" not in meeting_columns:
            statements.append("ALTER TABLE meetings ADD COLUMN diarization_error_message TEXT NULL")
            post_update_statements.append(
                "UPDATE meetings SET diarization_error_message='' WHERE diarization_error_message IS NULL"
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        for statement in post_update_statements:
            connection.execute(text(statement))
