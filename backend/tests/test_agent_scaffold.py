from __future__ import annotations

import unittest

from app.agents.graph import build_default_tool_registry
from app.agents.prompts import build_agent_system_prompt
from app.tools.base import ToolRegistry


class ToolRegistryTestCase(unittest.TestCase):
    def test_registry_registers_and_lists_tools(self) -> None:
        registry = ToolRegistry()
        registry.register("inspect_audio_tool", "inspect uploaded audio")
        registry.register("transcribe_meeting_tool", "transcribe audio")

        names = [tool.name for tool in registry.list_tools()]
        self.assertIn("inspect_audio_tool", names)
        self.assertIn("transcribe_meeting_tool", names)

    def test_default_registry_contains_core_tools(self) -> None:
        registry = build_default_tool_registry()
        names = [tool.name for tool in registry.list_tools()]
        self.assertIn("inspect_audio_tool", names)
        self.assertIn("transcribe_meeting_tool", names)
        self.assertIn("diarize_segments_tool", names)
        self.assertIn("summarize_with_agent_tool", names)

    def test_agent_prompt_mentions_mode_scene_and_tools(self) -> None:
        registry = build_default_tool_registry()
        prompt = build_agent_system_prompt("project", "campus", registry)

        self.assertIn("project", prompt)
        self.assertIn("campus", prompt)
        self.assertIn("inspect_audio_tool", prompt)
        self.assertIn("summarize_with_agent_tool", prompt)


if __name__ == "__main__":
    unittest.main()
