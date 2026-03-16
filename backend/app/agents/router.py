from __future__ import annotations


def resolve_agent_name(summary_mode: str, scene: str) -> str:
    mode_map = {
        "general": "meeting-secretary-agent",
        "project": "project-ops-agent",
        "executive": "executive-briefing-agent",
    }
    base = mode_map.get(summary_mode, "meeting-secretary-agent")
    if scene and scene != "general":
        return f"{base}-{scene}"
    return base
