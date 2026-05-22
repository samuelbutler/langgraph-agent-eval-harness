from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import MockResponse, ToolCall


class MockToolError(LookupError):
    """Raised when a strict mock registry cannot satisfy a tool call."""


class MockToolRegistry:
    def __init__(self, responses: list[MockResponse], *, strict: bool = False) -> None:
        self.responses = responses
        self.strict = strict
        self.calls: list[ToolCall] = []

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        call_args = args or {}
        self.calls.append(ToolCall(tool=name, args=call_args))
        for response in self.responses:
            if response.tool == name and _matches(response.when, call_args):
                return response.returns
        if self.strict:
            raise MockToolError(f"No mock response for {name} with args {call_args!r}")
        return {"ok": True, "mock": True, "tool": name}


def _matches(expected: Mapping[str, Any] | None, actual: Mapping[str, Any]) -> bool:
    if expected is None:
        return True
    return all(actual.get(key) == value for key, value in expected.items())
