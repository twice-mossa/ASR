from __future__ import annotations

import io

import soundfile as sf
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.agent import AudioInspection


async def inspect_audio_tool(filename: str, raw: bytes) -> AudioInspection:
    try:
        with sf.SoundFile(io.BytesIO(raw)) as reader:
            duration_seconds = len(reader) / reader.samplerate if reader.samplerate else 0.0
            sample_rate = int(reader.samplerate or 0)
            channels = int(reader.channels or 0)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {exc}") from exc

    file_size_bytes = len(raw)
    groq_limit_bytes = settings.groq_max_upload_mb * 1024 * 1024
    processing_strategy = "chunked_parallel" if file_size_bytes > groq_limit_bytes or duration_seconds > 300 else "direct"

    return AudioInspection(
        filename=filename,
        duration_seconds=round(duration_seconds, 2),
        sample_rate=sample_rate,
        channels=channels,
        file_size_bytes=file_size_bytes,
        processing_strategy=processing_strategy,
        suggested_chunk_seconds=300,
    )
