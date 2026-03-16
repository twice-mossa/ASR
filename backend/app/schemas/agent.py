from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.meeting import MeetingSummaryResponse, TranscriptResponse, TranscriptSegment


class AudioInspection(BaseModel):
    filename: str
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    file_size_bytes: int = 0
    processing_strategy: str = "direct"
    suggested_chunk_seconds: int = 300


class SpeakerTurn(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class AgentTraceStep(BaseModel):
    step: str
    tool_name: str
    status: str = "completed"
    detail: str = ""


class AgentPresentationSection(BaseModel):
    title: str
    summary: str = ""
    bullets: list[str] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    agent_name: str
    summary_mode: str
    scene: str = "general"
    agent_prompt: str = ""
    inspection: AudioInspection
    transcript: TranscriptResponse
    speaker_turns: list[SpeakerTurn] = Field(default_factory=list)
    summary: MeetingSummaryResponse
    presentation_sections: list[AgentPresentationSection] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    trace: list[AgentTraceStep] = Field(default_factory=list)


class TranscriptToolPayload(BaseModel):
    transcript: TranscriptResponse
    speaker_turns: list[SpeakerTurn] = Field(default_factory=list)
    source_segments: list[TranscriptSegment] = Field(default_factory=list)
