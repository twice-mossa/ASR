from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.agent import AgentTraceStep, AudioInspection, SpeakerTurn
from app.schemas.meeting import MeetingSummaryResponse, TranscriptResponse


@dataclass
class MeetingAgentState:
    filename: str
    raw: bytes
    content_type: str
    summary_mode: str = "general"
    scene: str = "general"
    agent_name: str = "meeting-secretary-agent"
    inspection: AudioInspection | None = None
    transcript: TranscriptResponse | None = None
    speaker_turns: list[SpeakerTurn] = field(default_factory=list)
    summary: MeetingSummaryResponse | None = None
    tools_used: list[str] = field(default_factory=list)
    trace: list[AgentTraceStep] = field(default_factory=list)

    def add_trace(self, step: str, tool_name: str, detail: str) -> None:
        self.trace.append(
            AgentTraceStep(
                step=step,
                tool_name=tool_name,
                status="completed",
                detail=detail,
            )
        )
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)
