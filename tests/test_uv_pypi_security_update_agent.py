from langgraph_agent_eval_harness.loader import load_scenarios
from langgraph_agent_eval_harness.runner import ScenarioRunner
from langgraph_agent_eval_harness.scorer import score_trace


def test_uv_pypi_security_update_agent_scans_before_sync():
    scenario = load_scenarios("examples/scenarios/uv_pypi_security_update.yaml")[0]
    trace = ScenarioRunner().run(scenario)
    result = score_trace(scenario, trace)
    assert result.failed == []
    assert result.score == result.max_score

    tools = [call.tool for call in trace.tool_calls]
    assert tools.index("pypi.fetch_release_metadata") < tools.index("cli.uv_sync")
    assert tools.index("security.scan_pypi_artifact") < tools.index("cli.uv_sync")
    assert tools.index("security.scan_python_install_hooks") < tools.index("cli.uv_sync")
