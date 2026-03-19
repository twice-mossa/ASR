from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import threading
import uuid
from collections.abc import Callable

import httpx
import soundfile as sf
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.schemas.meeting import (
    TranscriptJobCreateResponse,
    TranscriptJobStatusResponse,
    TranscriptResponse,
    TranscriptSegment,
)
from app.services.meeting_service import (
    ensure_owned_meeting,
    get_meeting_audio_payload,
    reset_meeting_transcript,
    save_partial_transcript_result,
    save_transcript_result,
    update_meeting_status,
)

_whisper_model = None
_load_lock = asyncio.Lock()
_jobs_lock = threading.Lock()
_transcription_jobs: dict[str, TranscriptJobStatusResponse] = {}
_job_cancel_flags: dict[str, bool] = {}
_meeting_job_index: dict[int, str] = {}

logger = logging.getLogger(__name__)
_GROQ_TIMEOUT = httpx.Timeout(connect=20.0, read=600.0, write=600.0, pool=20.0)
_GROQ_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_GROQ_MAX_ATTEMPTS = 3
_LOCAL_PROMPT = "以下是中文会议录音，请输出简体中文，并尽量保留正常标点和专有名词。"
_TRANSCRIPT_NOISE_PHRASES = (
    "请输出简体中文",
    "尽量保留正常标点",
    "尽量保留正常标点和专有名词",
    "请不吝点赞",
    "订阅 转发 打赏支持",
    "打赏支持明镜与点点栏目",
)

PartialCallback = Callable[[TranscriptResponse, int, int], None]
StopCheck = Callable[[], bool]


class _TranscriptionStopped(RuntimeError):
    pass


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


def _sanitize_transcript_text(text: str) -> str:
    cleaned = (text or "").strip()
    for phrase in _TRANSCRIPT_NOISE_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip(" ,，。；;：:")


def _normalize_segments(raw_segments: list[dict] | None) -> list[TranscriptSegment]:
    segments_out: list[TranscriptSegment] = []
    for segment in raw_segments or []:
        text = _sanitize_transcript_text(str(segment.get("text", "")))
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


def _build_transcript_response(
    *,
    filename: str,
    language: str,
    segments: list[TranscriptSegment],
    text: str | None = None,
) -> TranscriptResponse:
    full_text = text if text is not None else " ".join(segment.text for segment in segments).strip()
    return TranscriptResponse(
        filename=filename,
        language=language or "zh",
        text=full_text.strip(),
        segments=segments,
    )


def _store_job(job: TranscriptJobStatusResponse) -> None:
    with _jobs_lock:
        _transcription_jobs[job.job_id] = _with_job_flags(job)
        _job_cancel_flags[job.job_id] = False
        if job.meeting_id is not None:
            _meeting_job_index[job.meeting_id] = job.job_id


def _update_job(
    job_id: str,
    **updates,
) -> None:
    with _jobs_lock:
        current = _transcription_jobs.get(job_id)
        if current is None:
            return
        _transcription_jobs[job_id] = _with_job_flags(current.model_copy(update=updates))


def _job_is_stoppable(job: TranscriptJobStatusResponse | None) -> bool:
    if job is None or job.meeting_id is None:
        return False
    return job.status in {"queued", "processing"}


def _with_job_flags(job: TranscriptJobStatusResponse) -> TranscriptJobStatusResponse:
    partial_available = bool((job.text or "").strip() or job.segments)
    return job.model_copy(
        update={
            "is_stoppable": _job_is_stoppable(job),
            "partial_available": partial_available,
        }
    )


def _set_meeting_job_index(meeting_id: int | None, job_id: str) -> None:
    if meeting_id is None:
        return
    with _jobs_lock:
        _meeting_job_index[meeting_id] = job_id


def _clear_job_runtime(job_id: str, meeting_id: int | None = None) -> None:
    with _jobs_lock:
        _job_cancel_flags.pop(job_id, None)
        if meeting_id is not None and _meeting_job_index.get(meeting_id) == job_id:
            _meeting_job_index.pop(meeting_id, None)


def _request_job_stop(job_id: str) -> None:
    with _jobs_lock:
        _job_cancel_flags[job_id] = True


def _is_stop_requested(job_id: str) -> bool:
    with _jobs_lock:
        return bool(_job_cancel_flags.get(job_id))


async def get_transcription_job(job_id: str) -> TranscriptJobStatusResponse:
    with _jobs_lock:
        job = _transcription_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Transcription job not found")
        return _with_job_flags(job)


def get_active_meeting_transcription_job(meeting_id: int) -> TranscriptJobStatusResponse | None:
    with _jobs_lock:
        job_id = _meeting_job_index.get(meeting_id)
        if not job_id:
            return None
        job = _transcription_jobs.get(job_id)
        if job is None:
            return None
        if job.status not in {"queued", "processing", "stopping"}:
            return None
        return _with_job_flags(job)


def _set_partial_job_result(
    job_id: str,
    result: TranscriptResponse,
    completed_chunks: int,
    total_chunks: int,
) -> None:
    _update_job(
        job_id,
        status="processing",
        filename=result.filename,
        language=result.language,
        text=result.text,
        segments=result.segments,
        completed_chunks=completed_chunks,
        total_chunks=total_chunks,
        error=None,
    )


def _handle_partial_transcription_result(
    job_id: str,
    result: TranscriptResponse,
    completed_chunks: int,
    total_chunks: int,
    meeting_id: int | None = None,
) -> None:
    if meeting_id is not None:
        save_partial_transcript_result(meeting_id, result, status_value="transcribing")
    _set_partial_job_result(job_id, result, completed_chunks, total_chunks)


async def stop_transcription_job(job_id: str, current_user) -> TranscriptJobStatusResponse:
    job = await get_transcription_job(job_id)
    if job.meeting_id is None:
        raise HTTPException(status_code=400, detail="当前任务不支持停止")

    ensure_owned_meeting(job.meeting_id, current_user)

    if job.status in {"stopped", "completed", "failed"}:
        return job

    _request_job_stop(job_id)
    _update_job(job_id, status="stopping", error=None)
    return await get_transcription_job(job_id)


def stop_transcription_jobs_for_meeting(meeting_id: int) -> None:
    with _jobs_lock:
        job_id = _meeting_job_index.get(meeting_id)
    if not job_id:
        return
    _request_job_stop(job_id)
    _update_job(job_id, status="stopping", error=None)


async def start_transcription_job(file: UploadFile) -> TranscriptJobCreateResponse:
    filename = file.filename or "unknown.wav"

    try:
        raw = await file.read()
    except Exception as exc:
        logger.error("Failed to read upload file: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid audio file") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    content_type = file.content_type or "application/octet-stream"
    job_id = uuid.uuid4().hex

    _store_job(
        TranscriptJobStatusResponse(
            job_id=job_id,
            status="queued",
            meeting_id=None,
            filename=filename,
            language="zh",
            text="",
            segments=[],
            total_chunks=1,
            completed_chunks=0,
            error=None,
        )
    )

    threading.Thread(
        target=lambda: asyncio.run(_run_transcription_job(job_id, filename, raw, content_type)),
        name=f"transcription-job-{job_id[:8]}",
        daemon=True,
    ).start()
    return TranscriptJobCreateResponse(job_id=job_id, status="queued")


async def start_transcription_job_for_meeting(meeting_id: int, current_user) -> TranscriptJobCreateResponse:
    meeting, raw, content_type = get_meeting_audio_payload(meeting_id, current_user)
    job_id = uuid.uuid4().hex
    reset_meeting_transcript(meeting_id, status_value="transcribing")

    _store_job(
        TranscriptJobStatusResponse(
            job_id=job_id,
            status="queued",
            meeting_id=meeting_id,
            filename=meeting.filename,
            language=meeting.language or "zh",
            text="",
            segments=[],
            total_chunks=1,
            completed_chunks=0,
            is_stoppable=True,
            partial_available=False,
            error=None,
        )
    )
    update_meeting_status(meeting_id, status_value="transcribing", error_message="")

    threading.Thread(
        target=lambda: asyncio.run(
            _run_transcription_job(job_id, meeting.filename, raw, content_type, meeting_id=meeting_id)
        ),
        name=f"transcription-job-{job_id[:8]}",
        daemon=True,
    ).start()
    return TranscriptJobCreateResponse(job_id=job_id, status="queued", meeting_id=meeting_id)


async def _run_transcription_job(
    job_id: str,
    filename: str,
    raw: bytes,
    content_type: str,
    meeting_id: int | None = None,
) -> None:
    _update_job(job_id, status="processing")
    try:
        result = await _transcribe_from_bytes(
            filename=filename,
            raw=raw,
            content_type=content_type,
            on_partial=lambda partial, completed, total: _handle_partial_transcription_result(
                job_id,
                partial,
                completed,
                total,
                meeting_id=meeting_id,
            ),
            should_stop=lambda: _is_stop_requested(job_id),
        )
        if meeting_id is not None:
            save_transcript_result(meeting_id, result)
        current_job = await get_transcription_job(job_id)
        _update_job(
            job_id,
            status="completed",
            meeting_id=meeting_id,
            filename=result.filename,
            language=result.language,
            text=result.text,
            segments=result.segments,
            completed_chunks=max(1, current_job.completed_chunks),
            total_chunks=max(1, current_job.total_chunks),
            error=None,
        )
        _clear_job_runtime(job_id, meeting_id)
    except _TranscriptionStopped:
        current_job = await get_transcription_job(job_id)
        _update_job(
            job_id,
            status="stopped",
            meeting_id=meeting_id,
            completed_chunks=current_job.completed_chunks,
            total_chunks=current_job.total_chunks,
            error=None,
        )
        if meeting_id is not None:
            update_meeting_status(meeting_id, status_value="stopped", error_message="")
        _clear_job_runtime(job_id, meeting_id)
    except HTTPException as exc:
        _update_job(job_id, status="failed", error=str(exc.detail))
        if meeting_id is not None:
            update_meeting_status(meeting_id, status_value="failed", error_message=str(exc.detail))
        _clear_job_runtime(job_id, meeting_id)
    except Exception as exc:
        logger.exception("Unexpected transcription job failure: %s", exc)
        _update_job(job_id, status="failed", error=str(exc))
        if meeting_id is not None:
            update_meeting_status(meeting_id, status_value="failed", error_message=str(exc))
        _clear_job_runtime(job_id, meeting_id)


async def _transcribe_from_bytes(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
    on_partial: PartialCallback | None = None,
    should_stop: StopCheck | None = None,
) -> TranscriptResponse:
    if settings.groq_api_key:
        return await _transcribe_with_groq(
            filename=filename,
            raw=raw,
            content_type=content_type,
            on_partial=on_partial,
            should_stop=should_stop,
        )

    logger.info("GROQ_API_KEY is empty, falling back to local faster-whisper model.")
    result = await _transcribe_with_local_model(filename=filename, raw=raw)
    if on_partial is not None:
        on_partial(result, 1, 1)
    return result


async def _transcribe_with_groq(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
    on_partial: PartialCallback | None = None,
    should_stop: StopCheck | None = None,
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

        return await _transcribe_large_wav_with_groq(
            filename=filename,
            raw=raw,
            max_bytes=max_bytes,
            on_partial=on_partial,
            should_stop=should_stop,
        )

    result = await _transcribe_with_groq_single(filename=filename, raw=raw, content_type=content_type)
    if on_partial is not None:
        on_partial(result, 1, 1)
    return result


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

    response = await _send_groq_request_with_retry(filename=filename, request_factory=_send)

    if response.status_code >= 400:
        detail = response.text
        logger.error("Groq transcription failed: status=%s body=%s", response.status_code, detail)
        if response.status_code in _GROQ_RETRYABLE_STATUS_CODES:
            raise HTTPException(status_code=502, detail="Groq transcription service temporarily unavailable")
        raise HTTPException(status_code=502, detail=f"Groq transcription failed: {detail}")

    payload = response.json()
    full_text = _sanitize_transcript_text(str(payload.get("text", "")))
    language = str(payload.get("language", "zh") or "zh")
    segments = _normalize_segments(payload.get("segments"))

    if full_text and not segments:
        segments = [TranscriptSegment(start=0.0, end=0.0, text=full_text)]
    elif not full_text and segments:
        full_text = " ".join(segment.text for segment in segments).strip()

    return _build_transcript_response(
        filename=filename,
        language=language,
        segments=segments,
        text=full_text,
    )


async def _send_groq_request_with_retry(*, filename: str, request_factory: Callable[[], httpx.Response]) -> httpx.Response:
    last_error: Exception | None = None

    for attempt in range(1, _GROQ_MAX_ATTEMPTS + 1):
        try:
            response = await asyncio.to_thread(request_factory)
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            logger.warning(
                "Groq transcription transport error for %s on attempt %s/%s: %s",
                filename,
                attempt,
                _GROQ_MAX_ATTEMPTS,
                exc,
            )
            if attempt < _GROQ_MAX_ATTEMPTS:
                await asyncio.sleep(attempt)
                continue
            raise HTTPException(status_code=502, detail="远程转录服务网络异常，请稍后重试。") from exc

        if response.status_code in _GROQ_RETRYABLE_STATUS_CODES and attempt < _GROQ_MAX_ATTEMPTS:
            logger.warning(
                "Groq transcription returned retryable status for %s on attempt %s/%s: %s",
                filename,
                attempt,
                _GROQ_MAX_ATTEMPTS,
                response.status_code,
            )
            await asyncio.sleep(attempt)
            continue

        return response

    if last_error is not None:
        raise HTTPException(status_code=502, detail="远程转录服务网络异常，请稍后重试。") from last_error
    raise HTTPException(status_code=502, detail="远程转录服务暂时不可用，请稍后重试。")


def _raise_if_stop_requested(should_stop: StopCheck | None = None) -> None:
    if should_stop is not None and should_stop():
        raise _TranscriptionStopped()


def _split_wav_bytes(raw: bytes, max_bytes: int) -> list[tuple[float, bytes]]:
    try:
        with sf.SoundFile(io.BytesIO(raw)) as reader:
            samplerate = reader.samplerate
            channels = reader.channels
            subtype = reader.subtype or "PCM_16"
            total_frames = len(reader)

            if samplerate <= 0 or channels <= 0:
                raise HTTPException(status_code=400, detail="Unsupported WAV file")

            if subtype == "PCM_16":
                bytes_per_channel = 2
            elif subtype == "PCM_24":
                bytes_per_channel = 3
            elif subtype in {"PCM_32", "FLOAT"}:
                bytes_per_channel = 4
            elif subtype == "DOUBLE":
                bytes_per_channel = 8
            else:
                bytes_per_channel = 2

            bytes_per_frame = channels * bytes_per_channel
            target_bytes = max(4 * 1024 * 1024, max_bytes - 512 * 1024)
            frames_per_chunk = max(1, target_bytes // bytes_per_frame)

            chunks: list[tuple[float, bytes]] = []
            frame_cursor = 0

            while frame_cursor < total_frames:
                frame_count = min(frames_per_chunk, total_frames - frame_cursor)
                frames = reader.read(frame_count, dtype="float32", always_2d=True)

                buffer = io.BytesIO()
                sf.write(buffer, frames, samplerate, format="WAV", subtype=subtype)

                start_seconds = frame_cursor / samplerate
                chunks.append((start_seconds, buffer.getvalue()))
                frame_cursor += frame_count
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid WAV file: {exc}") from exc

    return chunks


async def _transcribe_large_wav_with_groq(
    *,
    filename: str,
    raw: bytes,
    max_bytes: int,
    on_partial: PartialCallback | None = None,
    should_stop: StopCheck | None = None,
) -> TranscriptResponse:
    chunks = await asyncio.to_thread(_split_wav_bytes, raw, max_bytes)
    logger.info("Chunking large WAV for Groq transcription: %s chunks", len(chunks))

    combined_segments: list[TranscriptSegment] = []
    language = "zh"
    total_chunks = len(chunks)

    for index, (offset_seconds, chunk_raw) in enumerate(chunks, start=1):
        _raise_if_stop_requested(should_stop)
        chunk_name = f"{os.path.splitext(filename)[0]}_part_{index}.wav"
        logger.info(
            "Sending chunk %s/%s to Groq: offset=%.2fs size=%.2fMB",
            index,
            total_chunks,
            offset_seconds,
            len(chunk_raw) / 1024 / 1024,
        )
        result = await _transcribe_with_groq_single(
            filename=chunk_name,
            raw=chunk_raw,
            content_type="audio/wav",
        )

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

        partial_result = _build_transcript_response(
            filename=filename,
            language=language,
            segments=combined_segments.copy(),
        )
        if on_partial is not None:
            on_partial(partial_result, index, total_chunks)
        _raise_if_stop_requested(should_stop)

    return _build_transcript_response(
        filename=filename,
        language=language,
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
            initial_prompt=_LOCAL_PROMPT,
        )

        for seg in seg_iter:
            start = float(getattr(seg, "start", 0.0))
            end = float(getattr(seg, "end", 0.0))
            text = _sanitize_transcript_text(str(getattr(seg, "text", "")))
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

    return _build_transcript_response(
        filename=filename,
        language=language or "zh",
        segments=segments_out,
        text=full_text,
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
    return await _transcribe_from_bytes(filename=filename, raw=raw, content_type=content_type)
