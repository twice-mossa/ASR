from __future__ import annotations

from app.schemas.agent import SpeakerTurn
from app.schemas.meeting import TranscriptSegment


def _next_speaker(current: str) -> str:
    if current == "Speaker A":
        return "Speaker B"
    if current == "Speaker B":
        return "Speaker C"
    return "Speaker A"


async def diarize_segments_tool(segments: list[TranscriptSegment]) -> list[SpeakerTurn]:
    if not segments:
        return []

    speaker = "Speaker A"
    speaker_turns: list[SpeakerTurn] = []

    for index, segment in enumerate(segments):
        if index > 0:
            previous = segments[index - 1]
            pause = segment.start - previous.end
            if pause >= 1.2:
                speaker = _next_speaker(speaker)

        speaker_turns.append(
            SpeakerTurn(
                speaker=speaker,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
        )

    return speaker_turns
