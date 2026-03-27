import asyncio

from fastapi import APIRouter, File, Form, Header, Query, UploadFile

from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile
from app.schemas.meeting import (
    MeetingAskRequest,
    MeetingAskResponse,
    MeetingCreateRequest,
    MeetingDetailResponse,
    MeetingListItem,
    MeetingSummaryEmailSendResponse,
    MeetingSummaryResponse,
    MeetingUpdateRequest,
    SummaryRequest,
    TranscriptJobCreateResponse,
    TranscriptJobStatusResponse,
    TranscriptResponse,
)
from app.services.auth_service import get_current_user, login_user, logout_user, register_user
from app.services.email_service import send_summary_email_for_meeting
from app.services.meeting_service import (
    create_meeting,
    delete_all_meeting_records,
    delete_meeting_record,
    finalize_upload_session,
    get_meeting_detail,
    list_meetings,
    require_user_from_authorization,
    start_upload_session,
    update_meeting_record,
    upload_meeting_chunk,
)
from app.services.minimax_service import build_summary, build_summary_for_meeting
from app.services.qa_service import ask_meeting_question
from app.services.transcription_service import (
    get_transcription_job,
    stop_transcription_job,
    start_transcription_job,
    start_transcription_job_for_meeting,
    transcribe_audio,
)

router = APIRouter(prefix="/api")


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.post("/auth/register", response_model=AuthResponse)
def create_account(payload: RegisterRequest) -> AuthResponse:
    return register_user(payload)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    return login_user(payload)


@router.get("/auth/me", response_model=UserProfile)
def read_current_user(authorization: str | None = Header(default=None)) -> UserProfile:
    return get_current_user(authorization)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(authorization: str | None = Header(default=None)) -> LogoutResponse:
    return logout_user(authorization)


@router.post("/transcribe", response_model=TranscriptResponse)
async def create_transcript(file: UploadFile = File(...)) -> TranscriptResponse:
    return await transcribe_audio(file)


@router.post("/transcribe/jobs", response_model=TranscriptJobCreateResponse)
async def create_transcription_job(file: UploadFile = File(...)) -> TranscriptJobCreateResponse:
    return await start_transcription_job(file)


@router.post("/meetings/{meeting_id}/transcribe", response_model=TranscriptJobCreateResponse)
async def create_meeting_transcription_job(
    meeting_id: int,
    authorization: str | None = Header(default=None),
) -> TranscriptJobCreateResponse:
    current_user = require_user_from_authorization(authorization)
    return await start_transcription_job_for_meeting(meeting_id, current_user)


@router.get("/transcribe/jobs/{job_id}", response_model=TranscriptJobStatusResponse)
async def read_transcription_job(job_id: str) -> TranscriptJobStatusResponse:
    return await get_transcription_job(job_id)


@router.post("/transcribe/jobs/{job_id}/stop", response_model=TranscriptJobStatusResponse)
async def stop_transcription_job_route(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> TranscriptJobStatusResponse:
    current_user = require_user_from_authorization(authorization)
    return await stop_transcription_job(job_id, current_user)


@router.post("/summary", response_model=MeetingSummaryResponse)
async def create_summary(
    payload: SummaryRequest,
    authorization: str | None = Header(default=None),
) -> MeetingSummaryResponse:
    if payload.meeting_id is not None:
        current_user = require_user_from_authorization(authorization)
        return await build_summary_for_meeting(payload.meeting_id, current_user)
    return await build_summary(payload.transcribed_text)


@router.post("/meetings", response_model=MeetingDetailResponse)
async def create_meeting_record(
    filename: str = Form(...),
    duration_label: str = Form(default="--:--"),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> MeetingDetailResponse:
    current_user = require_user_from_authorization(authorization)
    return create_meeting(
        payload=MeetingCreateRequest(filename=filename, duration_label=duration_label),
        file=file,
        current_user=current_user,
    )


@router.post("/meetings/upload-sessions")
def create_meeting_upload_session(
    filename: str = Form(...),
    duration_label: str = Form(default="--:--"),
    content_type: str = Form(default="application/octet-stream"),
    authorization: str | None = Header(default=None),
) -> dict[str, str | int]:
    current_user = require_user_from_authorization(authorization)
    return start_upload_session(
        filename=filename,
        duration_label=duration_label,
        content_type=content_type,
        current_user=current_user,
    )


@router.post("/meetings/upload-sessions/{upload_id}/chunks")
def upload_meeting_file_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict[str, str | int | bool]:
    current_user = require_user_from_authorization(authorization)
    return upload_meeting_chunk(
        upload_id=upload_id,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        file=file,
        current_user=current_user,
    )


@router.post("/meetings/upload-sessions/{upload_id}/complete", response_model=MeetingDetailResponse)
def complete_meeting_upload_session(
    upload_id: str,
    authorization: str | None = Header(default=None),
) -> MeetingDetailResponse:
    current_user = require_user_from_authorization(authorization)
    return finalize_upload_session(upload_id=upload_id, current_user=current_user)


@router.get("/meetings", response_model=list[MeetingListItem])
def read_meeting_records(
    authorization: str | None = Header(default=None),
    query: str = Query(default=""),
) -> list[MeetingListItem]:
    current_user = require_user_from_authorization(authorization)
    return list_meetings(current_user, query=query)


@router.get("/meetings/{meeting_id}", response_model=MeetingDetailResponse)
def read_meeting_record(meeting_id: int, authorization: str | None = Header(default=None)) -> MeetingDetailResponse:
    current_user = require_user_from_authorization(authorization)
    return get_meeting_detail(meeting_id, current_user)


@router.patch("/meetings/{meeting_id}", response_model=MeetingDetailResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdateRequest,
    authorization: str | None = Header(default=None),
) -> MeetingDetailResponse:
    current_user = require_user_from_authorization(authorization)
    return update_meeting_record(meeting_id, payload, current_user)


@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    authorization: str | None = Header(default=None),
) -> dict[str, int | str]:
    current_user = require_user_from_authorization(authorization)
    return delete_meeting_record(meeting_id, current_user)


@router.delete("/meetings")
def delete_all_meetings(authorization: str | None = Header(default=None)) -> dict[str, int | str]:
    current_user = require_user_from_authorization(authorization)
    return delete_all_meeting_records(current_user)


@router.post("/meetings/{meeting_id}/send-summary-email", response_model=MeetingSummaryEmailSendResponse)
async def send_meeting_summary_email(
    meeting_id: int,
    authorization: str | None = Header(default=None),
) -> MeetingSummaryEmailSendResponse:
    current_user = require_user_from_authorization(authorization)
    return await asyncio.to_thread(send_summary_email_for_meeting, meeting_id, current_user)


@router.post("/meetings/{meeting_id}/ask", response_model=MeetingAskResponse)
async def ask_meeting(
    meeting_id: int,
    payload: MeetingAskRequest,
    authorization: str | None = Header(default=None),
) -> MeetingAskResponse:
    current_user = require_user_from_authorization(authorization)
    return await ask_meeting_question(meeting_id, payload.question, current_user)
