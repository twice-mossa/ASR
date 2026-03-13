from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import wave

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.schemas.meeting import TranscriptResponse, TranscriptSegment

_whisper_model = None
_load_lock = asyncio.Lock()

logger = logging.getLogger(__name__)
_GROQ_TIMEOUT = httpx.Timeout(connect=20.0, read=600.0, write=600.0, pool=20.0)
_GROQ_PROMPT = "以下是中文会议录音，请输出简体中文，并尽量保留正常标点和专有名词。"


async def _ensure_model_loaded():
    global _whisper_model
    if _whisper_model is not None:
        return

    async with _load_lock:
        if _whisper_model is not None:
            return

        logger.info("Loading local faster-whisper model as fallback...")

        def _load():
            try:
                import torch

                has_cuda = torch.cuda.is_available()
            except Exception:
                has_cuda = False

            from faster_whisper import WhisperModel

            device = "cuda" if has_cuda else "cpu"
            compute_type = "int8" if device == "cpu" else "float16"
            model_size = settings.whisper_model_size or "large-v3"

            logger.info("Local model=%s device=%s compute_type=%s", model_size, device, compute_type)
            return WhisperModel(model_size, device=device, compute_type=compute_type)

        _whisper_model = await asyncio.to_thread(_load)
        logger.info("Local faster-whisper model loaded.")


def _normalize_segments(raw_segments: list[dict] | None) -> list[TranscriptSegment]:
    segments_out: list[TranscriptSegment] = []
    for segment in raw_segments or []:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        segments_out.append(
            TranscriptSegment(
                start=float(segment.get("start", 0.0) or 0.0),
                end=float(segment.get("end", 0.0) or 0.0),
                text=text,
            )
        )
    return segments_out


async def _transcribe_with_groq(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
) -> TranscriptResponse:
    max_bytes = settings.groq_max_upload_mb * 1024 * 1024
    suffix = os.path.splitext(filename)[1].lower()

    if len(raw) > max_bytes:
        if suffix != ".wav":
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Audio file is too large for Groq direct upload ({len(raw) / 1024 / 1024:.1f} MB). "
                    "Please upload a smaller file, convert it to flac, or use wav so the backend can chunk it."
                ),
            )

        return await _transcribe_large_wav_with_groq(filename=filename, raw=raw, max_bytes=max_bytes)

    return await _transcribe_with_groq_single(filename=filename, raw=raw, content_type=content_type)


async def _transcribe_with_groq_single(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
) -> TranscriptResponse:
    url = f"{settings.groq_base_url.rstrip('/')}/audio/transcriptions"
    model = settings.groq_transcription_model or "whisper-large-v3"

    data = {
        "model": model,
        "language": "zh",
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
        "prompt": _GROQ_PROMPT,
    }
    files = {
        "file": (filename, raw, content_type),
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
    }

    def _send():
        with httpx.Client(timeout=_GROQ_TIMEOUT) as client:
            return client.post(url, data=data, files=files, headers=headers)

    response = await asyncio.to_thread(_send)

    if response.status_code >= 400:
        detail = response.text
        logger.error("Groq transcription failed: status=%s body=%s", response.status_code, detail)
        raise HTTPException(status_code=502, detail=f"Groq transcription failed: {detail}")

    payload = response.json()
    full_text = str(payload.get("text", "")).strip()
    language = str(payload.get("language", "zh") or "zh")
    segments = _normalize_segments(payload.get("segments"))

    if full_text and not segments:
        segments = [TranscriptSegment(start=0.0, end=0.0, text=full_text)]

    return TranscriptResponse(
        filename=filename,
        language=language,
        text=full_text,
        segments=segments,
    )


def _split_wav_bytes(raw: bytes, max_bytes: int) -> list[tuple[float, bytes]]:
    with wave.open(io.BytesIO(raw), "rb") as reader:
        params = reader.getparams()
        channels = reader.getnchannels()
        sampwidth = reader.getsampwidth()
        framerate = reader.getframerate()
        total_frames = reader.getnframes()

        bytes_per_frame = channels * sampwidth
        if bytes_per_frame <= 0 or framerate <= 0:
            raise HTTPException(status_code=400, detail="Unsupported WAV file")

        # Reserve some room for headers and multipart overhead.
        target_bytes = max(4 * 1024 * 1024, max_bytes - 512 * 1024)
        frames_per_chunk = max(1, target_bytes // bytes_per_frame)

        chunks: list[tuple[float, bytes]] = []
        frame_cursor = 0

        while frame_cursor < total_frames:
            frame_count = min(frames_per_chunk, total_frames - frame_cursor)
            frames = reader.readframes(frame_count)

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as writer:
                writer.setparams(params)
                writer.writeframes(frames)

            start_seconds = frame_cursor / framerate
            chunks.append((start_seconds, buffer.getvalue()))
            frame_cursor += frame_count

    return chunks


async def _transcribe_large_wav_with_groq(
    *,
    filename: str,
    raw: bytes,
    max_bytes: int,
) -> TranscriptResponse:
    try:
        chunks = await asyncio.to_thread(_split_wav_bytes, raw, max_bytes)
    except wave.Error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid WAV file: {exc}") from exc

    logger.info("Chunking large WAV for Groq transcription: %s chunks", len(chunks))

    combined_text: list[str] = []
    combined_segments: list[TranscriptSegment] = []
    language = "zh"

    for index, (offset_seconds, chunk_raw) in enumerate(chunks, start=1):
        chunk_name = f"{os.path.splitext(filename)[0]}_part_{index}.wav"
        logger.info(
            "Sending chunk %s/%s to Groq: offset=%.2fs size=%.2fMB",
            index,
            len(chunks),
            offset_seconds,
            len(chunk_raw) / 1024 / 1024,
        )
        result = await _transcribe_with_groq_single(
            filename=chunk_name,
            raw=chunk_raw,
            content_type="audio/wav",
        )

        if result.text:
            combined_text.append(result.text)
        if result.language:
            language = result.language

        for segment in result.segments:
            combined_segments.append(
                TranscriptSegment(
                    start=segment.start + offset_seconds,
                    end=segment.end + offset_seconds,
                    text=segment.text,
                )
            )

    return TranscriptResponse(
        filename=filename,
        language=language,
        text=" ".join(part.strip() for part in combined_text if part.strip()).strip(),
        segments=combined_segments,
    )


async def _transcribe_with_local_model(filename: str, raw: bytes) -> TranscriptResponse:
    await _ensure_model_loaded()

    suffix = os.path.splitext(filename)[1] or ".wav"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
    except Exception as exc:
        logger.error("Failed to create temp file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save audio file") from exc

    def _run(path: str) -> tuple[str, str, list[TranscriptSegment]]:
        model = _whisper_model
        segments_out: list[TranscriptSegment] = []
        text_chunks: list[str] = []

        seg_iter, info = model.transcribe(
            path,
            language="zh",
            task="transcribe",
            beam_size=5,
            best_of=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 150},
            initial_prompt=_GROQ_PROMPT,
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

    try:
        language, full_text, segments_out = await asyncio.to_thread(_run, tmp_path)
    except Exception as exc:
        logger.error("Local transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError as exc:
            logger.warning("Failed to remove temp file %s: %s", tmp_path, exc)

    return TranscriptResponse(
        filename=filename,
        language=language or "zh",
        text=full_text,
        segments=segments_out,
    )


async def transcribe_audio(file: UploadFile) -> TranscriptResponse:
    filename = file.filename or "unknown.wav"

    try:
        raw = await file.read()
    except Exception as exc:
        logger.error("Failed to read upload file: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid audio file") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    content_type = file.content_type or "application/octet-stream"

    if settings.groq_api_key:
        return await _transcribe_with_groq(filename=filename, raw=raw, content_type=content_type)

    logger.info("GROQ_API_KEY is empty, falling back to local faster-whisper model.")
    return await _transcribe_with_local_model(filename=filename, raw=raw)
