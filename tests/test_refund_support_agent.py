from langgraph_agent_eval_harness.loader import load_scenarios
from langgraph_agent_eval_harness.runner import ScenarioRunner
from langgraph_agent_eval_harness.scorer import score_trace


def test_credential_free_refund_support_agent_passes():
    scenario = load_scenarios("examples/scenarios/refund_support_no_credentials.yaml")[0]
    trace = ScenarioRunner().run(scenario)
    result = score_trace(scenario, trace)
    assert result.failed == []
    assert result.score == result.max_score
