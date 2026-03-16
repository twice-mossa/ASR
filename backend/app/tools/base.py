from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolInvocation:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolInvocation] = {}

    def register(self, name: str, description: str, **metadata: Any) -> None:
        self._tools[name] = ToolInvocation(name=name, description=description, metadata=metadata)

    def get(self, name: str) -> ToolInvocation:
        return self._tools[name]

    def list_tools(self) -> list[ToolInvocation]:
        return list(self._tools.values())
