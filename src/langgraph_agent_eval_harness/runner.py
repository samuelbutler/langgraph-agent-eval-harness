from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from .langgraph_adapter import invoke_graph
from .mock_tools import MockToolRegistry
from .schema import EvalTrace, Scenario


class ScenarioRunner:
    def __init__(self, *, strict_mocks: bool = False) -> None:
        self.strict_mocks = strict_mocks

    def run(self, scenario: Scenario) -> EvalTrace:
        started = datetime.now(timezone.utc)
        t0 = perf_counter()
        registry = MockToolRegistry(scenario.mocks, strict=self.strict_mocks)
        approvals: list[str] = []
        notes: list[str] = []

        if scenario.agent == "scripted":
            notes, approvals = self._run_scripted(scenario, registry)
        else:
            output = invoke_graph(scenario.graph or "", registry, scenario.prompt)
            notes = _coerce_str_list(output.get("notes", []))
            approvals = _coerce_str_list(output.get("approvals", []))

        final_answer = "Completed scenario. " + " | ".join(notes)
        return EvalTrace(
            scenario_id=scenario.id,
            final_answer=final_answer,
            tool_calls=registry.calls,
            approvals=approvals,
            started_at=started,
            duration_ms=(perf_counter() - t0) * 1000,
        )

    @staticmethod
    def _run_scripted(
        scenario: Scenario,
        registry: MockToolRegistry,
    ) -> tuple[list[str], list[str]]:
        notes: list[str] = []
        approvals: list[str] = []
        for step in scenario.scripted_plan:
            if step.tool == "request_approval":
                approvals.append(str(step.args.get("action", "unknown")))
                notes.append(f"approval requested for {approvals[-1]}")
                continue
            result = registry.call(step.tool, step.args)
            notes.append(f"{step.tool} -> {result}")
            if isinstance(result, dict) and result.get("issues"):
                notes.append("possible duplicate found")
        return notes, approvals


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]
