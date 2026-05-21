from __future__ import annotations

from typing import Any

from .schema import MockResponse, ToolCall


class MockToolRegistry:
    def __init__(self, responses: list[MockResponse]) -> None:
        self.responses = responses
        self.calls: list[ToolCall] = []

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        args = args or {}
        self.calls.append(ToolCall(tool=name, args=args))
        for response in self.responses:
            if response.tool != name:
                continue
            if response.when is None or all(args.get(k) == v for k, v in response.when.items()):
                return response.returns
        return {"ok": True, "mock": True, "tool": name}
