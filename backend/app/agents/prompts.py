from __future__ import annotations

from app.tools.base import ToolRegistry


def build_agent_system_prompt(summary_mode: str, scene: str, tool_registry: ToolRegistry) -> str:
    tool_lines = [
        f"- {tool.name}: {tool.description}"
        for tool in tool_registry.list_tools()
    ]
    tool_block = "\n".join(tool_lines)

    return (
        "你是会议智能体调度器，不是直接生成答案的单一模型。\n"
        f"当前摘要模式: {summary_mode}\n"
        f"当前业务场景: {scene}\n"
        "你必须根据音频长度、文件大小和任务目标，组合调用合适的工具链。\n"
        "优先顺序：先检查音频，再决定长音频策略，再执行转写，再做说话人切分，最后生成对应风格的纪要。\n"
        "可用工具如下：\n"
        f"{tool_block}\n"
        "输出需要保留处理轨迹，方便前端展示 Agent 的决策过程。"
    )
