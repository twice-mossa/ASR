from fastapi import APIRouter, File, UploadFile, HTTPException

from app.schemas.meeting import (
    MeetingSummaryResponse, 
    TranscriptResponse, 
    SummaryRequest
)
from app.services.minimax_service import build_summary
from app.services.transcription_service import transcribe_audio

router = APIRouter(prefix="/api")


@router.get("/ping")
def ping() -> dict[str, str]:
    """
    Health check endpoint.
    """
    return {"message": "pong"}


@router.post("/transcribe", response_model=TranscriptResponse)
async def create_transcript(file: UploadFile = File(...)) -> TranscriptResponse:
    """
    Upload an audio file and get the transcription.
    
    - **file**: Audio file (wav, mp3, etc.)
    """
    return await transcribe_audio(file)


@router.post("/summary", response_model=MeetingSummaryResponse)
async def create_summary(payload: SummaryRequest) -> MeetingSummaryResponse:
    """
    Generate a meeting summary from the transcribed text.
    
    - **transcribed_text**: The full text of the meeting transcription.
    """
    return await build_summary(payload.transcribed_text)
