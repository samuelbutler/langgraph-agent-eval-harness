from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from .mock_tools import MockToolRegistry
from .schema import EvalTrace, Scenario


class ScenarioRunner:
    def run(self, scenario: Scenario) -> EvalTrace:
        started = datetime.now(timezone.utc)
        t0 = perf_counter()
        registry = MockToolRegistry(scenario.mocks)
        approvals: list[str] = []
        notes: list[str] = []

        if scenario.agent == "scripted":
            for step in scenario.scripted_plan:
                if step.tool == "request_approval":
                    approvals.append(str(step.args.get("action", "unknown")))
                    notes.append(f"approval requested for {approvals[-1]}")
                else:
                    result = registry.call(step.tool, step.args)
                    notes.append(f"{step.tool} -> {result}")
                    if isinstance(result, dict) and result.get("issues"):
                        notes.append("possible duplicate found")
        else:
            raise NotImplementedError(
                "LangGraph adapter scaffold pending: implement a graph factory and call it here."
            )

        final_answer = "Completed scenario. " + " | ".join(notes)
        return EvalTrace(
            scenario_id=scenario.id,
            final_answer=final_answer,
            tool_calls=registry.calls,
            approvals=approvals,
            started_at=started,
            duration_ms=(perf_counter() - t0) * 1000,
        )
