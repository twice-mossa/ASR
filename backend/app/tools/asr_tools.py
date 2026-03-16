from __future__ import annotations

from app.schemas.agent import TranscriptToolPayload
from app.services.transcription_service import transcribe_audio_bytes
from app.tools.speaker_tools import diarize_segments_tool


async def transcribe_meeting_tool(filename: str, raw: bytes, content_type: str) -> TranscriptToolPayload:
    transcript = await transcribe_audio_bytes(filename=filename, raw=raw, content_type=content_type)
    speaker_turns = await diarize_segments_tool(transcript.segments)
    return TranscriptToolPayload(
        transcript=transcript,
        speaker_turns=speaker_turns,
        source_segments=transcript.segments,
    )
