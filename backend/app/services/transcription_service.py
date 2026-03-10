from __future__ import annotations

import asyncio
import os
import tempfile
import logging
from typing import Optional

from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.schemas.meeting import TranscriptResponse, TranscriptSegment

# Global variable to hold the loaded model
_whisper_model = None
_load_lock = asyncio.Lock()

logger = logging.getLogger(__name__)

async def _ensure_model_loaded():
    """
    Ensure the faster-whisper model is loaded. 
    Uses a lock to prevent concurrent loading.
    """
    global _whisper_model
    if _whisper_model is not None:
        return
    async with _load_lock:
        if _whisper_model is not None:
            return
        
        logger.info("Loading faster-whisper model...")
        def _load():
            try:
                import torch
                has_cuda = torch.cuda.is_available()
            except Exception:
                has_cuda = False
            
            from faster_whisper import WhisperModel
            device = "cuda" if has_cuda else "cpu"
            # Use int8 quantization for CPU to speed up, float16 for GPU
            compute_type = "int8" if device == "cpu" else "float16"
            model_size = settings.whisper_model_size or "small"
            
            logger.info(f"Model: {model_size}, Device: {device}, Compute Type: {compute_type}")
            return WhisperModel(model_size, device=device, compute_type=compute_type)
            
        _whisper_model = await asyncio.to_thread(_load)
        logger.info("faster-whisper model loaded successfully.")


async def transcribe_audio(file: UploadFile) -> TranscriptResponse:
    """
    Transcribe audio file using faster-whisper.
    
    Process:
    1. Save uploaded file to a temporary file.
    2. Load model if not loaded.
    3. Run transcription in a separate thread.
    4. Clean up temporary file.
    5. Return transcription result.
    """
    await _ensure_model_loaded()
    
    filename = file.filename or "unknown.wav"
    # Read file content
    try:
        raw = await file.read()
    except Exception as e:
        logger.error(f"Failed to read upload file: {e}")
        raise HTTPException(status_code=400, detail="Invalid audio file")

    suffix = os.path.splitext(filename)[1] or ".wav"
    
    # 1. Save to temporary file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
    except Exception as e:
        logger.error(f"Failed to create temp file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save audio file")

    async def _run(path: str) -> tuple[str, str, list[TranscriptSegment]]:
        """Run blocking transcription in a thread."""
        model = _whisper_model
        segments_out: list[TranscriptSegment] = []
        text_chunks: list[str] = []
        
        try:
            # 2. Call local faster-whisper model
            seg_iter, info = model.transcribe(
                path,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 150},
            )
            
            for seg in seg_iter:
                start = float(getattr(seg, "start", 0.0))
                end = float(getattr(seg, "end", 0.0))
                text = str(getattr(seg, "text", "")).strip()
                if text:
                    text_chunks.append(text)
                segments_out.append(TranscriptSegment(start=start, end=end, text=text))
            
            language = getattr(info, "language", "zh")
            full_text = " ".join(text_chunks).strip()
            return language, full_text, segments_out
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise e

    try:
        # Run CPU-bound task in thread pool
        language, full_text, segments_out = await asyncio.to_thread(_run, tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # 3. Clean up temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError as e:
            logger.warning(f"Failed to remove temp file {tmp_path}: {e}")

    return TranscriptResponse(
        filename=filename,
        language=language or "zh",
        text=full_text,
        segments=segments_out,
    )
