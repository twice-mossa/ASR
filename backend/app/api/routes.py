from fastapi import APIRouter, File, Form, Header, UploadFile

from app.agents.graph import run_meeting_agent
from app.schemas.agent import AgentRunResponse

from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile
from app.schemas.meeting import (
    EmailDeliveryRequest,
    EmailDeliveryResponse,
    MeetingSummaryResponse,
    SummaryRequest,
    TranscriptJobCreateResponse,
    TranscriptJobStatusResponse,
    TranscriptResponse,
)
from app.services.auth_service import get_current_user, login_user, logout_user, register_user
from app.services.email_service import send_summary_email
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


@router.post("/summary/email", response_model=EmailDeliveryResponse)
def email_summary(
    payload: EmailDeliveryRequest,
    authorization: str | None = Header(default=None),
) -> EmailDeliveryResponse:
    current_user = get_current_user(authorization)
    return send_summary_email(payload, current_user)


@router.post("/agent/run", response_model=AgentRunResponse)
async def run_agent_flow(
    file: UploadFile = File(...),
    summary_mode: str = Form(default="general"),
    scene: str = Form(default="general"),
) -> AgentRunResponse:
    filename = file.filename or "unknown.wav"
    raw = await file.read()
    content_type = file.content_type or "application/octet-stream"
    return await run_meeting_agent(
        filename=filename,
        raw=raw,
        content_type=content_type,
        summary_mode=summary_mode,
        scene=scene,
    )
