from fastapi import APIRouter, File, Header, UploadFile

from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile
from app.schemas.meeting import (
    MeetingSummaryResponse,
    SummaryRequest,
    TranscriptJobCreateResponse,
    TranscriptJobStatusResponse,
    TranscriptResponse,
)
from app.services.auth_service import get_current_user, login_user, logout_user, register_user
from app.services.minimax_service import build_summary
from app.services.transcription_service import get_transcription_job, start_transcription_job, transcribe_audio

router = APIRouter(prefix="/api")


@router.get("/ping")
def ping() -> dict[str, str]:
    """
    Health check endpoint.
    """
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
    """
    Upload an audio file and get the transcription.
    
    - **file**: Audio file (wav, mp3, etc.)
    """
    return await transcribe_audio(file)


@router.post("/transcribe/jobs", response_model=TranscriptJobCreateResponse)
async def create_transcription_job(file: UploadFile = File(...)) -> TranscriptJobCreateResponse:
    return await start_transcription_job(file)


@router.get("/transcribe/jobs/{job_id}", response_model=TranscriptJobStatusResponse)
async def read_transcription_job(job_id: str) -> TranscriptJobStatusResponse:
    return await get_transcription_job(job_id)


@router.post("/summary", response_model=MeetingSummaryResponse)
async def create_summary(payload: SummaryRequest) -> MeetingSummaryResponse:
    """
    Generate a meeting summary from the transcribed text.
    
    - **transcribed_text**: The full text of the meeting transcription.
    """
    return await build_summary(payload.transcribed_text)
