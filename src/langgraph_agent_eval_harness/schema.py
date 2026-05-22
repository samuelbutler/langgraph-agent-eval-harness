from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(StrictModel):
    tool: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


class MockResponse(StrictModel):
    tool: str = Field(min_length=1)
    when: dict[str, Any] | None = None
    returns: Any


class CallOrder(StrictModel):
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)


class ExpectedBehavior(StrictModel):
    must_call: list[str] = Field(default_factory=list)
    must_not_call: list[str] = Field(default_factory=list)
    must_mention: list[str] = Field(default_factory=list)
    requires_approval_before: list[str] = Field(default_factory=list)
    must_call_before: list[CallOrder] = Field(default_factory=list)


class Scenario(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    agent: Literal["scripted", "langgraph"] = "scripted"
    graph: str | None = Field(default=None, description="Import path: module:function")
    expected: ExpectedBehavior = Field(default_factory=ExpectedBehavior)
    mocks: list[MockResponse] = Field(default_factory=list)
    scripted_plan: list[ToolCall] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_agent_config(self) -> Scenario:
        if self.agent == "langgraph" and not self.graph:
            raise ValueError("LangGraph scenarios must set graph: 'module:function'")
        if self.agent == "scripted" and self.graph:
            raise ValueError("Scripted scenarios must not set graph")
        return self


class EvalTrace(StrictModel):
    scenario_id: str
    final_answer: str
    tool_calls: list[ToolCall]
    approvals: list[str] = Field(default_factory=list)
    started_at: datetime
    duration_ms: float = Field(ge=0)


class EvalResult(StrictModel):
    scenario_id: str
    title: str
    score: int = Field(ge=0)
    max_score: int = Field(ge=0)
    passed: list[str]
    failed: list[str]
    trace: EvalTrace

    @property
    def ok(self) -> bool:
        return not self.failed
