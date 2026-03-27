from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, or_, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    Meeting,
    MeetingKnowledgePack,
    MeetingQARecord,
    MeetingSummary,
    MeetingSummaryEmailDelivery,
    TranscriptSegment,
)
from app.schemas.auth import UserProfile
from app.schemas.meeting import (
    MeetingCitation,
    MeetingCreateRequest,
    MeetingDetailResponse,
    MeetingEvidenceBlock,
    MeetingListItem,
    MeetingUpdateRequest,
    MeetingQARecordResponse,
    MeetingSummaryEmailStatusResponse,
    MeetingSummaryResponse,
    TranscriptResponse,
    TranscriptSegment as TranscriptSegmentSchema,
)


def _get_session():
    return SessionLocal()


def _to_iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _build_audio_url(meeting: Meeting) -> str:
    return f"/media/{meeting.stored_filename}" if meeting.stored_filename else ""


def _build_transcript(meeting: Meeting, segments: list[TranscriptSegment]) -> TranscriptResponse | None:
    if not meeting.transcript_text and not segments:
        return None

    return TranscriptResponse(
        filename=meeting.filename,
        language=meeting.language or "zh",
        text=meeting.transcript_text or "",
        segments=[
            TranscriptSegmentSchema(
                start=float(segment.start),
                end=float(segment.end),
                text=str(segment.text),
                speaker_label=str(segment.speaker_label) if segment.speaker_label else None,
                speaker_confidence=(
                    float(segment.speaker_confidence) if segment.speaker_confidence is not None else None
                ),
            )
            for segment in segments
        ],
        speaker_diarization_status=meeting.diarization_status or "not_requested",
        speaker_diarization_message=meeting.diarization_error_message or None,
    )


def _build_summary(summary: MeetingSummary | None) -> MeetingSummaryResponse | None:
    if summary is None:
        return None

    try:
        keywords = json.loads(summary.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []

    try:
        todos = json.loads(summary.todos_json or "[]")
    except json.JSONDecodeError:
        todos = []

    return MeetingSummaryResponse(
        summary=summary.summary or "",
        keywords=[str(item) for item in keywords],
        todos=[str(item) for item in todos],
    )


def _build_transcription_job(meeting_id: int):
    try:
        from app.services.transcription_service import get_active_meeting_transcription_job

        return get_active_meeting_transcription_job(meeting_id)
    except Exception:
        return None


def _smtp_enabled() -> bool:
    return bool(
        settings.smtp_host
        and settings.smtp_port
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from_email
    )


def _build_summary_email_status(
    delivery: MeetingSummaryEmailDelivery | None,
    current_user: UserProfile,
) -> MeetingSummaryEmailStatusResponse:
    return MeetingSummaryEmailStatusResponse(
        enabled=_smtp_enabled(),
        recipient_email=str(delivery.recipient_email) if delivery else current_user.email,
        last_status=str(delivery.status) if delivery else "idle",
        last_delivery_type=str(delivery.delivery_type) if delivery else None,
        last_sent_at=_to_iso(delivery.created_at) if delivery and delivery.status == "sent" else None,
        last_error=str(delivery.error_message or "") if delivery and delivery.status == "failed" else None,
    )


def _build_qa_records(records: list[MeetingQARecord]) -> list[MeetingQARecordResponse]:
    items: list[MeetingQARecordResponse] = []
    for record in records:
        try:
            citations = json.loads(record.citations_json or "[]")
        except json.JSONDecodeError:
            citations = []
        try:
            topic_labels = json.loads(record.topic_labels_json or "[]")
        except json.JSONDecodeError:
            topic_labels = []
        try:
            evidence_blocks = json.loads(record.evidence_blocks_json or "[]")
        except json.JSONDecodeError:
            evidence_blocks = []

        items.append(
            MeetingQARecordResponse(
                id=int(record.id),
                question=record.question or "",
                answer=record.answer or "",
                citations=[
                    MeetingCitation(
                        text=str(item.get("text") or ""),
                        start=float(item.get("start") or 0.0),
                        end=float(item.get("end") or 0.0),
                        segment_id=int(item["segment_id"]) if item.get("segment_id") is not None else None,
                    )
                    for item in citations
                    if isinstance(item, dict)
                ],
                reasoning_summary=record.reasoning_summary or None,
                answer_type=record.answer_type or "fact",
                topic_labels=[str(item) for item in topic_labels if item is not None],
                evidence_blocks=[
                    MeetingEvidenceBlock(
                        title=str(block.get("title") or "证据块"),
                        start=float(block.get("start") or 0.0),
                        end=float(block.get("end") or 0.0),
                        summary=str(block.get("summary") or ""),
                        citations=[
                            MeetingCitation(
                                text=str(item.get("text") or ""),
                                start=float(item.get("start") or 0.0),
                                end=float(item.get("end") or 0.0),
                                segment_id=int(item["segment_id"]) if item.get("segment_id") is not None else None,
                            )
                            for item in (block.get("citations") or [])
                            if isinstance(item, dict)
                        ],
                    )
                    for block in evidence_blocks
                    if isinstance(block, dict)
                ],
                created_at=_to_iso(record.created_at),
            )
        )
    return items


def _meeting_preview(meeting: Meeting, summary: MeetingSummary | None) -> str:
    if summary and summary.summary:
        return "已生成摘要，可继续追问会议细节。"
    if meeting.status == "transcribing":
        return "正在转录，已识别内容会持续刷新。"
    if meeting.status == "stopped":
        return "已停止转录，保留了当前已识别内容。"
    if meeting.transcript_text:
        return "已完成转录，可继续追问会议内容。"
    if meeting.status == "failed" and meeting.error_message:
        return meeting.error_message[:34]
    return "已上传音频，等待转录。"


def _meeting_title(meeting: Meeting) -> str:
    return meeting.title or meeting.filename or f"会议 {meeting.id}"


def _get_owned_meeting(db, meeting_id: int, user_id: int) -> Meeting:
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user_id)
    ).scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议记录不存在")
    return meeting


def ensure_owned_meeting(meeting_id: int, current_user: UserProfile) -> Meeting:
    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        db.expunge(meeting)
        return meeting


def _create_meeting_record_from_saved_file(
    *,
    payload: MeetingCreateRequest,
    filename: str,
    stored_filename: str,
    audio_path: Path,
    content_type: str,
    current_user: UserProfile,
) -> MeetingDetailResponse:
    normalized_filename = (payload.filename or filename or "").strip()
    if not normalized_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少音频文件名")

    if not audio_path.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音频文件不存在")

    return _create_meeting_from_saved_audio(
        filename=filename,
        saved_path=saved_path,
        stored_filename=unique_name,
        content_type=file.content_type or "application/octet-stream",
        duration_label=payload.duration_label or "--:--",
        current_user=current_user,
    )


def _create_meeting_from_saved_audio(
    *,
    filename: str,
    saved_path: Path,
    stored_filename: str,
    content_type: str,
    duration_label: str,
    current_user: UserProfile,
) -> MeetingDetailResponse:
    with _get_session() as db:
        meeting = Meeting(
            user_id=current_user.id,
            title=Path(normalized_filename).stem or normalized_filename,
            filename=normalized_filename,
            stored_filename=stored_filename,
            audio_path=str(audio_path),
            content_type=content_type or "application/octet-stream",
            duration_label=payload.duration_label or "--:--",
            language="zh",
            status="draft",
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return MeetingDetailResponse(
            id=int(meeting.id),
            title=_meeting_title(meeting),
            filename=meeting.filename,
            duration_label=meeting.duration_label,
            language=meeting.language,
            status=meeting.status,
            audio_url=_build_audio_url(meeting),
            created_at=_to_iso(meeting.created_at),
            updated_at=_to_iso(meeting.updated_at),
            error=None,
            transcript=None,
            transcription_job=None,
            summary=None,
            summary_email=_build_summary_email_status(None, current_user),
            knowledge_status="idle",
        )


def create_meeting(payload: MeetingCreateRequest, file: UploadFile, current_user: UserProfile) -> MeetingDetailResponse:
    filename = (payload.filename or file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少音频文件名")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    saved_path = upload_dir / unique_name

    try:
        with saved_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存音频文件失败") from exc

    return _create_meeting_record_from_saved_file(
        payload=payload,
        filename=filename,
        stored_filename=unique_name,
        audio_path=saved_path,
        content_type=file.content_type or "application/octet-stream",
        current_user=current_user,
    )


def list_meetings(current_user: UserProfile, query: str = "") -> list[MeetingListItem]:
    normalized_query = query.strip()
    with _get_session() as db:
        statement = select(Meeting).where(Meeting.user_id == current_user.id)
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.where(
                or_(
                    Meeting.title.ilike(like_query),
                    Meeting.filename.ilike(like_query),
                    Meeting.transcript_text.ilike(like_query),
                )
            )
        meetings = db.execute(
            statement.order_by(Meeting.updated_at.desc(), Meeting.id.desc())
        ).scalars().all()

        summary_map = {}
        if meetings:
            summary_map = {
                summary.meeting_id: summary
                for summary in db.execute(
                    select(MeetingSummary).where(MeetingSummary.meeting_id.in_([meeting.id for meeting in meetings]))
                )
                .scalars()
                .all()
            }

        return [
            MeetingListItem(
                id=int(meeting.id),
                title=_meeting_title(meeting),
                filename=meeting.filename,
                duration_label=meeting.duration_label,
                language=meeting.language or "zh",
                status=meeting.status,
                preview=_meeting_preview(meeting, summary_map.get(meeting.id)),
                created_at=_to_iso(meeting.created_at),
                updated_at=_to_iso(meeting.updated_at),
                has_summary=meeting.id in summary_map,
            )
            for meeting in meetings
        ]


def get_meeting_detail(meeting_id: int, current_user: UserProfile) -> MeetingDetailResponse:
    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        segments = db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting.id)
            .order_by(TranscriptSegment.start.asc(), TranscriptSegment.id.asc())
        ).scalars().all()
        summary = db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
        ).scalar_one_or_none()
        summary_email = db.execute(
            select(MeetingSummaryEmailDelivery)
            .where(MeetingSummaryEmailDelivery.meeting_id == meeting.id)
            .order_by(MeetingSummaryEmailDelivery.created_at.desc(), MeetingSummaryEmailDelivery.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        qa_records = db.execute(
            select(MeetingQARecord)
            .where(MeetingQARecord.meeting_id == meeting.id)
            .order_by(MeetingQARecord.created_at.asc(), MeetingQARecord.id.asc())
        ).scalars().all()
        knowledge_pack = db.execute(
            select(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting.id)
        ).scalar_one_or_none()
        transcription_job = _build_transcription_job(int(meeting.id))

        return MeetingDetailResponse(
            id=int(meeting.id),
            title=_meeting_title(meeting),
            filename=meeting.filename,
            duration_label=meeting.duration_label,
            language=meeting.language or "zh",
            status=meeting.status,
            audio_url=_build_audio_url(meeting),
            created_at=_to_iso(meeting.created_at),
            updated_at=_to_iso(meeting.updated_at),
            error=meeting.error_message or None,
            transcript=_build_transcript(meeting, segments),
            transcription_job=transcription_job,
            summary=_build_summary(summary),
            summary_email=_build_summary_email_status(summary_email, current_user),
            qa_records=_build_qa_records(qa_records),
            knowledge_status=str(knowledge_pack.status) if knowledge_pack else "idle",
        )


def update_meeting_record(
    meeting_id: int,
    payload: MeetingUpdateRequest,
    current_user: UserProfile,
) -> MeetingDetailResponse:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会议标题不能为空")

    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        meeting.title = title
        db.commit()

    return get_meeting_detail(meeting_id, current_user)


def get_meeting_audio_payload(meeting_id: int, current_user: UserProfile) -> tuple[Meeting, bytes, str]:
    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        audio_path = Path(meeting.audio_path)
        if not audio_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议音频文件不存在")

        try:
            raw = audio_path.read_bytes()
        except OSError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="读取会议音频失败") from exc

        return meeting, raw, meeting.content_type or "application/octet-stream"


def update_meeting_status(
    meeting_id: int,
    *,
    status_value: str,
    language: str | None = None,
    error_message: str | None = None,
) -> None:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return

        meeting.status = status_value
        if language:
            meeting.language = language
        if error_message is not None:
            meeting.error_message = error_message
        db.commit()


def reset_meeting_transcript(meeting_id: int, status_value: str = "transcribing") -> None:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return

        meeting.transcript_text = ""
        meeting.status = status_value
        meeting.diarization_status = "pending" if settings.diarization_api_key else "not_requested"
        meeting.diarization_error_message = ""
        meeting.error_message = ""
        db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id))
        db.execute(delete(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id))
        db.commit()

    try:
        from app.ai_runtime.vectorstore import delete_meeting_index, delete_meeting_semantic_chunks

        delete_meeting_index(meeting_id)
        delete_meeting_semantic_chunks(meeting_id)
    except Exception:
        pass


def save_transcript_result(meeting_id: int, transcript: TranscriptResponse, status_value: str = "transcribed") -> None:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return

        meeting.filename = transcript.filename or meeting.filename
        meeting.title = Path(meeting.filename).stem or meeting.filename
        meeting.language = transcript.language or meeting.language or "zh"
        meeting.transcript_text = transcript.text or ""
        meeting.status = status_value
        meeting.diarization_status = transcript.speaker_diarization_status or "not_requested"
        meeting.diarization_error_message = transcript.speaker_diarization_message or ""
        meeting.error_message = ""

        db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id))
        for segment in transcript.segments:
            db.add(
                TranscriptSegment(
                    meeting_id=meeting_id,
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                    speaker_label=segment.speaker_label,
                    speaker_confidence=segment.speaker_confidence,
                )
            )

        db.commit()

    try:
        from app.ai_runtime.knowledge_pack import schedule_meeting_knowledge_pack_refresh
        from app.ai_runtime.vectorstore import schedule_meeting_index_upsert

        schedule_meeting_index_upsert(meeting_id)
        schedule_meeting_knowledge_pack_refresh(meeting_id)
    except Exception:
        # Vector indexing should never block the primary transcription flow.
        pass


def save_partial_transcript_result(
    meeting_id: int,
    transcript: TranscriptResponse,
    status_value: str = "transcribing",
) -> None:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return

        meeting.filename = transcript.filename or meeting.filename
        meeting.title = Path(meeting.filename).stem or meeting.filename
        meeting.language = transcript.language or meeting.language or "zh"
        meeting.transcript_text = transcript.text or ""
        meeting.status = status_value
        meeting.diarization_status = transcript.speaker_diarization_status or "not_requested"
        meeting.diarization_error_message = transcript.speaker_diarization_message or ""
        meeting.error_message = ""

        db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id))
        for segment in transcript.segments:
            db.add(
                TranscriptSegment(
                    meeting_id=meeting_id,
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                    speaker_label=segment.speaker_label,
                    speaker_confidence=segment.speaker_confidence,
                )
            )

        db.commit()


def get_meeting_transcript_text(meeting_id: int, current_user: UserProfile) -> str:
    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        if meeting.status not in {"transcribed", "summarized"} or not meeting.transcript_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会议尚未完成转录")
        return meeting.transcript_text


def save_meeting_summary(meeting_id: int, summary: MeetingSummaryResponse) -> None:
    with _get_session() as db:
        meeting = db.execute(select(Meeting).where(Meeting.id == meeting_id)).scalar_one_or_none()
        if meeting is None:
            return

        record = db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
        ).scalar_one_or_none()
        if record is None:
            record = MeetingSummary(meeting_id=meeting_id)
            db.add(record)

        record.summary = summary.summary
        record.keywords_json = json.dumps(summary.keywords, ensure_ascii=False)
        record.todos_json = json.dumps(summary.todos, ensure_ascii=False)
        meeting.status = "summarized"
        meeting.error_message = ""
        db.commit()

    try:
        from app.ai_runtime.knowledge_pack import schedule_meeting_knowledge_pack_refresh

        schedule_meeting_knowledge_pack_refresh(meeting_id)
    except Exception:
        pass


def _delete_meeting_related_rows(db, meeting_id: int) -> None:
    db.execute(delete(MeetingQARecord).where(MeetingQARecord.meeting_id == meeting_id))
    db.execute(delete(MeetingKnowledgePack).where(MeetingKnowledgePack.meeting_id == meeting_id))
    db.execute(delete(MeetingSummaryEmailDelivery).where(MeetingSummaryEmailDelivery.meeting_id == meeting_id))
    db.execute(delete(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id))
    db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id))


def _delete_meeting_index(meeting_id: int) -> None:
    try:
        from app.ai_runtime.vectorstore import delete_meeting_index, delete_meeting_semantic_chunks

        delete_meeting_index(meeting_id)
        delete_meeting_semantic_chunks(meeting_id)
    except Exception:
        pass


def _delete_meeting_audio_file(audio_path: str) -> None:
    if not audio_path:
        return
    try:
        path = Path(audio_path)
        if path.exists():
            path.unlink()
    except OSError:
        pass


def delete_meeting_record(meeting_id: int, current_user: UserProfile) -> dict[str, int | str]:
    from app.services.transcription_service import stop_transcription_jobs_for_meeting

    stop_transcription_jobs_for_meeting(meeting_id)

    with _get_session() as db:
        meeting = _get_owned_meeting(db, meeting_id, current_user.id)
        audio_path = str(meeting.audio_path or "")
        _delete_meeting_related_rows(db, meeting_id)
        db.execute(delete(Meeting).where(Meeting.id == meeting_id))
        db.commit()

    _delete_meeting_index(meeting_id)
    _delete_meeting_audio_file(audio_path)
    return {"message": "会议记录已删除", "deleted_id": meeting_id}


def delete_all_meeting_records(current_user: UserProfile) -> dict[str, int | str]:
    with _get_session() as db:
        meetings = db.execute(select(Meeting).where(Meeting.user_id == current_user.id)).scalars().all()
        meeting_ids = [int(meeting.id) for meeting in meetings]
        audio_paths = [str(meeting.audio_path or "") for meeting in meetings]

        for meeting_id in meeting_ids:
            _delete_meeting_related_rows(db, meeting_id)
        db.execute(delete(Meeting).where(Meeting.user_id == current_user.id))
        db.commit()

    if meeting_ids:
        from app.services.transcription_service import stop_transcription_jobs_for_meeting

        for meeting_id in meeting_ids:
            stop_transcription_jobs_for_meeting(meeting_id)
            _delete_meeting_index(meeting_id)
        for audio_path in audio_paths:
            _delete_meeting_audio_file(audio_path)

    return {"message": "历史会议已清空", "deleted_count": len(meeting_ids)}


def require_user_from_authorization(authorization: str | None) -> UserProfile:
    from app.services.auth_service import get_current_user

    return get_current_user(authorization)
