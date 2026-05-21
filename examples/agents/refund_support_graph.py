from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from langgraph_agent_eval_harness.mock_tools import MockToolRegistry


class RefundState(TypedDict):
    prompt: str
    notes: list[str]
    approvals: list[str]


def build_graph(registry: MockToolRegistry):
    """Credential-free support agent used for local eval demos.

    It only calls the harness mock registry. No network, API keys, or external services.
    """

    def lookup_order(state: RefundState) -> dict[str, Any]:
        order = registry.call("shop.lookup_order", {"order_id": "ORDER-123"})
        return {"notes": [*state.get("notes", []), f"looked up order: {order}"]}

    def check_policy(state: RefundState) -> dict[str, Any]:
        policy = registry.call("kb.search", {"query": "refund policy damaged item"})
        notes = [*state.get("notes", []), f"refund policy: {policy}"]
        notes.append("refund appears eligible because item arrived damaged")
        return {"notes": notes}

    def ask_approval(state: RefundState) -> dict[str, Any]:
        approvals = [*state.get("approvals", []), "shop.issue_refund"]
        notes = [*state.get("notes", []), "approval requested before issuing refund"]
        return {"approvals": approvals, "notes": notes}

    def issue_refund(state: RefundState) -> dict[str, Any]:
        result = registry.call("shop.issue_refund", {"order_id": "ORDER-123", "amount": 49.99})
        return {"notes": [*state.get("notes", []), f"refund result: {result}"]}

    graph = StateGraph(RefundState)
    graph.add_node("lookup_order", lookup_order)
    graph.add_node("check_policy", check_policy)
    graph.add_node("ask_approval", ask_approval)
    graph.add_node("issue_refund", issue_refund)
    graph.set_entry_point("lookup_order")
    graph.add_edge("lookup_order", "check_policy")
    graph.add_edge("check_policy", "ask_approval")
    graph.add_edge("ask_approval", "issue_refund")
    graph.add_edge("issue_refund", END)
    return graph.compile()
