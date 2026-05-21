from langgraph_agent_eval_harness.loader import load_scenarios
from langgraph_agent_eval_harness.runner import ScenarioRunner
from langgraph_agent_eval_harness.scorer import score_trace


def test_pnpm_security_update_agent_scans_before_update():
    scenario = load_scenarios("examples/scenarios/pnpm_security_update.yaml")[0]
    trace = ScenarioRunner().run(scenario)
    result = score_trace(scenario, trace)
    assert result.failed == []
    assert result.score == result.max_score

    tools = [call.tool for call in trace.tool_calls]
    assert tools.index("security.scan_package_update") < tools.index("cli.pnpm_update")
    assert tools.index("security.scan_lifecycle_scripts") < tools.index("cli.pnpm_update")
