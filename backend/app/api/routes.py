from fastapi import APIRouter, File, Form, Header, UploadFile

from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile
from app.schemas.meeting import (
    MeetingCreateRequest,
    MeetingDetailResponse,
    MeetingListItem,
    MeetingSummaryResponse,
    SummaryRequest,
    TranscriptJobCreateResponse,
    TranscriptJobStatusResponse,
    TranscriptResponse,
)
from app.services.auth_service import get_current_user, login_user, logout_user, register_user
from app.services.meeting_service import create_meeting, get_meeting_detail, list_meetings, require_user_from_authorization
from app.services.minimax_service import build_summary, build_summary_for_meeting
from app.services.transcription_service import (
    get_transcription_job,
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


@router.get("/meetings", response_model=list[MeetingListItem])
def read_meeting_records(authorization: str | None = Header(default=None)) -> list[MeetingListItem]:
    current_user = require_user_from_authorization(authorization)
    return list_meetings(current_user)


@router.get("/meetings/{meeting_id}", response_model=MeetingDetailResponse)
def read_meeting_record(meeting_id: int, authorization: str | None = Header(default=None)) -> MeetingDetailResponse:
    current_user = require_user_from_authorization(authorization)
    return get_meeting_detail(meeting_id, current_user)
