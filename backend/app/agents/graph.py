from __future__ import annotations

from fastapi import HTTPException

from app.agents.prompts import build_agent_system_prompt
from app.agents.router import resolve_agent_name
from app.agents.state import MeetingAgentState
from app.schemas.agent import AgentRunResponse
from app.tools.asr_tools import transcribe_meeting_tool
from app.tools.audio_tools import inspect_audio_tool
from app.tools.base import ToolRegistry
from app.tools.summary_tools import build_presentation_sections, summarize_with_agent_tool


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "inspect_audio_tool",
        "检测音频时长、采样率、声道数和文件大小，并给出直传或分段并发策略。",
        stage="preprocess",
    )
    registry.register(
        "transcribe_meeting_tool",
        "执行语音转写，返回带时间戳的文本分段结果。",
        stage="asr",
    )
    registry.register(
        "diarize_segments_tool",
        "根据停顿和片段顺序生成轻量说话人分段标签。",
        stage="speaker",
    )
    registry.register(
        "summarize_with_agent_tool",
        "按不同摘要模式输出会议纪要、关键词和待办事项。",
        stage="summary",
    )
    return registry


async def run_meeting_agent(
    *,
    filename: str,
    raw: bytes,
    content_type: str,
    summary_mode: str = "general",
    scene: str = "general",
) -> AgentRunResponse:
    tool_registry = build_default_tool_registry()
    agent_prompt = build_agent_system_prompt(summary_mode, scene, tool_registry)
    state = MeetingAgentState(
        filename=filename,
        raw=raw,
        content_type=content_type,
        summary_mode=summary_mode,
        scene=scene,
        agent_name=resolve_agent_name(summary_mode, scene),
    )

    state.inspection = await inspect_audio_tool(filename, raw)
    state.add_trace(
        step="inspect_audio",
        tool_name="inspect_audio_tool",
        detail=(
            f"duration={state.inspection.duration_seconds}s, "
            f"channels={state.inspection.channels}, "
            f"strategy={state.inspection.processing_strategy}"
        ),
    )
    state.add_trace(
        step="plan_tools",
        tool_name="agent_router",
        detail=f"agent={state.agent_name}, prompt_ready=true, selected_tools={len(tool_registry.list_tools())}",
    )

    transcript_payload = await transcribe_meeting_tool(filename, raw, content_type)
    state.transcript = transcript_payload.transcript
    state.speaker_turns = transcript_payload.speaker_turns
    state.add_trace(
        step="transcribe_audio",
        tool_name="transcribe_meeting_tool",
        detail=(
            f"segments={len(state.transcript.segments)}, "
            f"speaker_turns={len(state.speaker_turns)}"
        ),
    )

    state.summary = await summarize_with_agent_tool(
        state.transcript.text,
        mode=summary_mode,
        scene=scene,
    )
    state.add_trace(
        step="generate_summary",
        tool_name="summarize_with_agent_tool",
        detail=f"mode={summary_mode}, scene={scene}",
    )

    if state.inspection is None or state.transcript is None or state.summary is None:
        raise HTTPException(status_code=500, detail="Agent pipeline produced incomplete result")

    return AgentRunResponse(
        agent_name=state.agent_name,
        summary_mode=summary_mode,
        scene=scene,
        agent_prompt=agent_prompt,
        inspection=state.inspection,
        transcript=state.transcript,
        speaker_turns=state.speaker_turns,
        summary=state.summary,
        presentation_sections=build_presentation_sections(state.summary, summary_mode, scene),
        tools_used=state.tools_used,
        trace=state.trace,
    )
