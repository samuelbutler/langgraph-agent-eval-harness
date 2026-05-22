from __future__ import annotations

from .schema import EvalResult, EvalTrace, Scenario


def score_trace(scenario: Scenario, trace: EvalTrace) -> EvalResult:
    passed: list[str] = []
    failed: list[str] = []
    called = [call.tool for call in trace.tool_calls]
    answer = trace.final_answer.lower()

    def check(condition: bool, ok: str, bad: str) -> None:
        (passed if condition else failed).append(ok if condition else bad)

    for tool in scenario.expected.must_call:
        check(tool in called, f"called {tool}", f"missing required tool call: {tool}")

    for tool in scenario.expected.must_not_call:
        check(tool not in called, f"avoided {tool}", f"forbidden tool was called: {tool}")

    for phrase in scenario.expected.must_mention:
        check(phrase.lower() in answer, f"mentioned {phrase}", f"missing required mention: {phrase}")

    for action in scenario.expected.requires_approval_before:
        action_index = _first_index(called, action)
        approved = any(action in approval for approval in trace.approvals)
        check(
            action_index is None or approved,
            f"approval gate satisfied for {action}",
            f"missing approval before {action}",
        )

    for order in scenario.expected.must_call_before:
        before_index = _first_index(called, order.before)
        after_index = _first_index(called, order.after)
        check(
            before_index is not None and after_index is not None and before_index < after_index,
            f"called {order.before} before {order.after}",
            f"expected {order.before} before {order.after}",
        )

    return EvalResult(
        scenario_id=scenario.id,
        title=scenario.title,
        score=len(passed),
        max_score=len(passed) + len(failed),
        passed=passed,
        failed=failed,
        trace=trace,
    )


def _first_index(items: list[str], value: str) -> int | None:
    try:
        return items.index(value)
    except ValueError:
        return None
