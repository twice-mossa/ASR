from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
_SPEECHMATICS_TIMEOUT = httpx.Timeout(connect=20.0, read=120.0, write=120.0, pool=20.0)


@dataclass(slots=True)
class SpeakerTurn:
    speaker_label: str
    start: float
    end: float
    speaker_confidence: float | None = None


@dataclass(slots=True)
class DiarizationResult:
    status: str
    turns: list[SpeakerTurn]
    message: str | None = None


def diarization_is_requested() -> bool:
    return bool(
        settings.diarization_provider.strip().lower() == "speechmatics"
        and settings.diarization_api_key.strip()
    )


async def diarize_audio_with_provider(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
    language: str,
) -> DiarizationResult:
    if not diarization_is_requested():
        return DiarizationResult(status="not_requested", turns=[])

    provider = settings.diarization_provider.strip().lower()
    if provider != "speechmatics":
        raise RuntimeError(f"Unsupported diarization provider: {settings.diarization_provider}")

    return await _diarize_with_speechmatics(
        filename=filename,
        raw=raw,
        content_type=content_type,
        language=language,
    )


async def _diarize_with_speechmatics(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
    language: str,
) -> DiarizationResult:
    base_url = settings.diarization_base_url.rstrip("/")
    provider_language = _map_speechmatics_language(language)
    headers = {"Authorization": f"Bearer {settings.diarization_api_key.strip()}"}
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": provider_language,
            "diarization": "speaker",
            "speaker_diarization_config": {
                "prefer_current_speaker": True,
            },
        },
    }
    if settings.diarization_model:
        config["transcription_config"]["model"] = settings.diarization_model

    async with httpx.AsyncClient(timeout=_SPEECHMATICS_TIMEOUT) as client:
        submit_response = await client.post(
            f"{base_url}/jobs",
            headers=headers,
            files={"data_file": (filename, raw, content_type)},
            data={"config": json.dumps(config, ensure_ascii=False)},
        )
        submit_response.raise_for_status()
        submit_payload = submit_response.json()
        job = submit_payload.get("job") if isinstance(submit_payload, dict) else None
        job_id = (
            submit_payload.get("id")
            or (job or {}).get("id")
            or submit_payload.get("job_id")
        )
        if not job_id:
            raise RuntimeError("Speechmatics did not return a job id.")

        transcript_payload = await _wait_for_speechmatics_transcript(
            client=client,
            base_url=base_url,
            headers=headers,
            job_id=str(job_id),
        )

    turns = _extract_speaker_turns(transcript_payload)
    if not turns:
        return DiarizationResult(
            status="failed",
            turns=[],
            message="已完成转录，但说话人区分未完成。",
        )

    return DiarizationResult(status="ready", turns=turns)


async def _wait_for_speechmatics_transcript(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    job_id: str,
) -> dict:
    poll_delay_seconds = 2
    max_attempts = 180
    for attempt in range(max_attempts):
        status_response = await client.get(f"{base_url}/jobs/{job_id}", headers=headers)
        status_response.raise_for_status()
        payload = status_response.json()
        job = payload.get("job") if isinstance(payload, dict) else {}
        status_value = str((job or {}).get("status") or "").lower()
        if status_value == "done":
            transcript_response = await client.get(
                f"{base_url}/jobs/{job_id}/transcript",
                headers=headers,
                params={"format": "json-v2"},
            )
            transcript_response.raise_for_status()
            return transcript_response.json()
        if status_value == "rejected":
            errors = (job or {}).get("errors") or payload.get("errors") or []
            raise RuntimeError(_extract_speechmatics_error(errors) or "Speechmatics diarization job was rejected.")

        if attempt == max_attempts - 1:
            raise RuntimeError("Speechmatics diarization timed out while waiting for the transcript.")
        await asyncio.sleep(poll_delay_seconds)

    raise RuntimeError("Speechmatics diarization timed out.")


def _extract_speechmatics_error(errors: object) -> str:
    if not isinstance(errors, list):
        return ""
    messages = [str(item.get("message") or "").strip() for item in errors if isinstance(item, dict)]
    return "; ".join(message for message in messages if message)


def _map_speechmatics_language(language: str) -> str:
    normalized = (language or "").strip().lower()
    if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "mandarin"}:
        return "cmn"
    if normalized in {"zh-tw", "zh-hant"}:
        return "cmn"
    return normalized or "cmn"


def _extract_speaker_turns(payload: dict) -> list[SpeakerTurn]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []

    label_mapping: dict[str, str] = {}
    turns: list[SpeakerTurn] = []
    current: dict | None = None

    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") != "word":
            continue
        start = item.get("start_time")
        end = item.get("end_time")
        if start is None or end is None:
            continue
        alternatives = item.get("alternatives") or []
        if not alternatives or not isinstance(alternatives[0], dict):
            continue
        primary = alternatives[0]
        raw_speaker = str(primary.get("speaker") or item.get("speaker") or "").strip()
        if not raw_speaker:
            continue
        display_label = _map_speaker_label(raw_speaker, label_mapping)
        confidence_value = primary.get("confidence")
        confidence = float(confidence_value) if confidence_value is not None else None
        start_value = float(start)
        end_value = float(end)

        if (
            current is not None
            and current["speaker_label"] == display_label
            and start_value - float(current["end"]) <= 1.0
        ):
            current["end"] = max(float(current["end"]), end_value)
            if confidence is not None:
                current["confidences"].append(confidence)
            continue

        if current is not None:
            turns.append(_speaker_turn_from_state(current))

        current = {
            "speaker_label": display_label,
            "start": start_value,
            "end": end_value,
            "confidences": [confidence] if confidence is not None else [],
        }

    if current is not None:
        turns.append(_speaker_turn_from_state(current))

    return turns


def _speaker_turn_from_state(state: dict) -> SpeakerTurn:
    confidences = [float(value) for value in state.get("confidences") or []]
    average_confidence = sum(confidences) / len(confidences) if confidences else None
    return SpeakerTurn(
        speaker_label=str(state["speaker_label"]),
        start=float(state["start"]),
        end=float(state["end"]),
        speaker_confidence=average_confidence,
    )


def _map_speaker_label(raw_label: str, label_mapping: dict[str, str]) -> str:
    normalized = raw_label.strip()
    if not normalized or normalized.upper() in {"UU", "UNKNOWN"}:
        return "Speaker Unknown"
    if normalized not in label_mapping:
        index = len(label_mapping)
        if index < 26:
            label_mapping[normalized] = f"Speaker {chr(ord('A') + index)}"
        else:
            label_mapping[normalized] = f"Speaker {index + 1}"
    return label_mapping[normalized]
