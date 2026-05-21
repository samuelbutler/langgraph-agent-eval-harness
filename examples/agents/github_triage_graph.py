from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from langgraph_agent_eval_harness.mock_tools import MockToolRegistry


class TriageState(TypedDict):
    prompt: str
    notes: list[str]
    approvals: list[str]


def build_graph(registry: MockToolRegistry):
    def search(state: TriageState) -> dict[str, Any]:
        result = registry.call("github.search_issues", {"query": "login button is broken"})
        notes = [*state.get("notes", []), f"search result: {result}"]
        if isinstance(result, dict) and result.get("issues"):
            notes.append("possible duplicate found")
        return {"notes": notes}

    graph = StateGraph(TriageState)
    graph.add_node("search", search)
    graph.set_entry_point("search")
    graph.add_edge("search", END)
    return graph.compile()
