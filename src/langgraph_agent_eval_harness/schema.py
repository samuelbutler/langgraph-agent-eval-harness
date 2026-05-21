from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class MockResponse(BaseModel):
    tool: str
    when: dict[str, Any] | None = None
    returns: Any


class ExpectedBehavior(BaseModel):
    must_call: list[str] = Field(default_factory=list)
    must_not_call: list[str] = Field(default_factory=list)
    must_mention: list[str] = Field(default_factory=list)
    requires_approval_before: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    title: str
    prompt: str
    agent: Literal["scripted", "langgraph"] = "scripted"
    graph: str | None = Field(default=None, description="Import path: module:function")
    expected: ExpectedBehavior = Field(default_factory=ExpectedBehavior)
    mocks: list[MockResponse] = Field(default_factory=list)
    scripted_plan: list[ToolCall] = Field(default_factory=list)


class EvalTrace(BaseModel):
    scenario_id: str
    final_answer: str
    tool_calls: list[ToolCall]
    approvals: list[str] = Field(default_factory=list)
    started_at: datetime
    duration_ms: float


class EvalResult(BaseModel):
    scenario_id: str
    title: str
    score: int
    max_score: int
    passed: list[str]
    failed: list[str]
    trace: EvalTrace
