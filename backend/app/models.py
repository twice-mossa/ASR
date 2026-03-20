from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_salt = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    audio_path = Column(String(1024), nullable=False)
    content_type = Column(String(128), nullable=False, default="application/octet-stream")
    duration_label = Column(String(32), nullable=False, default="--:--")
    language = Column(String(16), nullable=False, default="zh")
    status = Column(String(32), nullable=False, default="draft", index=True)
    transcript_text = Column(Text, nullable=False, default="")
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    start = Column(Float, nullable=False, default=0.0)
    end = Column(Float, nullable=False, default=0.0)
    text = Column(Text, nullable=False)


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    summary = Column(Text, nullable=False, default="")
    keywords_json = Column(Text, nullable=False, default="[]")
    todos_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MeetingSummaryEmailDelivery(Base):
    __tablename__ = "meeting_summary_email_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_email = Column(String(255), nullable=False)
    delivery_type = Column(String(16), nullable=False, default="manual")
    status = Column(String(16), nullable=False, default="failed")
    subject = Column(String(255), nullable=False, default="")
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MeetingQARecord(Base):
    __tablename__ = "meeting_qa_records"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False, default="")
    answer = Column(Text, nullable=False, default="")
    citations_json = Column(Text, nullable=False, default="[]")
    reasoning_summary = Column(Text, nullable=False, default="")
    answer_type = Column(String(32), nullable=False, default="fact")
    topic_labels_json = Column(Text, nullable=False, default="[]")
    evidence_blocks_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MeetingKnowledgePack(Base):
    __tablename__ = "meeting_knowledge_packs"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    semantic_chunks_json = Column(Text, nullable=False, default="[]")
    topic_map_json = Column(Text, nullable=False, default="[]")
    discussion_points_json = Column(Text, nullable=False, default="[]")
    summary_context_json = Column(Text, nullable=False, default="{}")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
