from langgraph_agent_eval_harness.loader import load_scenarios
from langgraph_agent_eval_harness.runner import ScenarioRunner
from langgraph_agent_eval_harness.scorer import score_trace


def test_example_scenario_passes():
    scenario = load_scenarios("examples/scenarios/github_duplicate_issue.yaml")[0]
    trace = ScenarioRunner().run(scenario)
    result = score_trace(scenario, trace)
    assert result.failed == []
    assert result.score == result.max_score
