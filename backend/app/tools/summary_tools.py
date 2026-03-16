from __future__ import annotations

from app.schemas.agent import AgentPresentationSection
from app.schemas.meeting import MeetingSummaryResponse
from app.services.minimax_service import build_summary, build_summary_with_guidance


SUMMARY_GUIDANCE_MAP = {
    "general": (
        "你是通用会议秘书智能体。请给出标准会议纪要，重点输出会议主旨、关键词和可执行待办。"
    ),
    "project": (
        "你是项目管理智能体。请重点关注项目进度、风险、负责人、截止时间、阻塞项，"
        "并把待办事项写得更明确。"
    ),
    "executive": (
        "你是领导汇报智能体。请压缩成高层可快速阅读的摘要，突出背景、关键结论、待决策事项。"
    ),
}


async def summarize_with_agent_tool(text: str, mode: str, scene: str = "general") -> MeetingSummaryResponse:
    guidance = SUMMARY_GUIDANCE_MAP.get(mode, SUMMARY_GUIDANCE_MAP["general"])

    if scene and scene != "general":
        guidance = f"{guidance} 当前会议场景：{scene}。请让摘要更贴合该业务场景。"

    if mode in SUMMARY_GUIDANCE_MAP:
        return await build_summary_with_guidance(text, guidance)

    return await build_summary(text)


def build_presentation_sections(
    summary: MeetingSummaryResponse,
    mode: str,
    scene: str = "general",
) -> list[AgentPresentationSection]:
    scene_note = "" if scene == "general" else f"场景：{scene}"

    if mode == "project":
        return [
            AgentPresentationSection(
                title="项目概览",
                summary=summary.summary,
                bullets=[scene_note] if scene_note else [],
            ),
            AgentPresentationSection(
                title="关键推进项",
                bullets=summary.keywords[:4],
            ),
            AgentPresentationSection(
                title="落地行动",
                bullets=summary.todos,
            ),
        ]

    if mode == "executive":
        return [
            AgentPresentationSection(
                title="高层摘要",
                summary=summary.summary,
                bullets=[scene_note] if scene_note else [],
            ),
            AgentPresentationSection(
                title="关键结论",
                bullets=summary.keywords[:4],
            ),
            AgentPresentationSection(
                title="待决策/待推进事项",
                bullets=summary.todos,
            ),
        ]

    return [
        AgentPresentationSection(
            title="会议摘要",
            summary=summary.summary,
            bullets=[scene_note] if scene_note else [],
        ),
        AgentPresentationSection(
            title="关键词",
            bullets=summary.keywords,
        ),
        AgentPresentationSection(
            title="待办事项",
            bullets=summary.todos,
        ),
    ]
