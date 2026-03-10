from fastapi import APIRouter, File, UploadFile

from app.schemas.meeting import MeetingSummaryResponse, TranscriptResponse
from app.services.minimax_service import build_mock_summary
from app.services.transcription_service import transcribe_audio

router = APIRouter(prefix="/api")


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.post("/transcribe", response_model=TranscriptResponse)
async def create_transcript(file: UploadFile = File(...)) -> TranscriptResponse:
    return await transcribe_audio(file)


@router.post("/summary", response_model=MeetingSummaryResponse)
async def create_summary(payload: TranscriptResponse) -> MeetingSummaryResponse:
    return await build_mock_summary(payload)
