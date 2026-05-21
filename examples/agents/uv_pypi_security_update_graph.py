from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from langgraph_agent_eval_harness.mock_tools import MockToolRegistry


class UvSecurityState(TypedDict):
    prompt: str
    notes: list[str]
    approvals: list[str]


def build_graph(registry: MockToolRegistry):
    """Credential-free Python dependency security agent for uv/PyPI updates.

    The agent can run uv-like commands through mocked tools, but must inspect PyPI
    candidate releases for malicious code before syncing/upgrading anything.
    """

    def inspect_project(state: UvSecurityState) -> dict[str, Any]:
        pyproject = registry.call("fs.read_file", {"path": "pyproject.toml"})
        lockfile = registry.call("fs.read_file", {"path": "uv.lock"})
        notes = [
            *state.get("notes", []),
            f"read pyproject: {pyproject}",
            f"read uv lockfile: {lockfile}",
        ]
        return {"notes": notes}

    def list_updates(state: UvSecurityState) -> dict[str, Any]:
        updates = registry.call("cli.uv_lock_dry_run", {"upgrade": True})
        return {"notes": [*state.get("notes", []), f"candidate PyPI updates: {updates}"]}

    def scan_pypi_release(state: UvSecurityState) -> dict[str, Any]:
        metadata = registry.call("pypi.fetch_release_metadata", {"package": "requests", "version": "2.32.4"})
        artifact_scan = registry.call(
            "security.scan_pypi_artifact",
            {"package": "requests", "from_version": "2.32.3", "to_version": "2.32.4"},
        )
        install_scan = registry.call(
            "security.scan_python_install_hooks",
            {"package": "requests", "version": "2.32.4"},
        )
        notes = [
            *state.get("notes", []),
            f"PyPI release metadata: {metadata}",
            f"malicious code scan: {artifact_scan}",
            f"Python install hook scan: {install_scan}",
        ]
        return {"notes": notes}

    def approve_uv_sync(state: UvSecurityState) -> dict[str, Any]:
        approvals = [*state.get("approvals", []), "cli.uv_sync"]
        notes = [
            *state.get("notes", []),
            "approval granted because PyPI malicious code scan passed before uv sync",
        ]
        return {"approvals": approvals, "notes": notes}

    def run_uv_sync(state: UvSecurityState) -> dict[str, Any]:
        result = registry.call("cli.uv_sync", {"upgrade_package": "requests"})
        return {"notes": [*state.get("notes", []), f"uv sync result: {result}"]}

    graph = StateGraph(UvSecurityState)
    graph.add_node("inspect_project", inspect_project)
    graph.add_node("list_updates", list_updates)
    graph.add_node("scan_pypi_release", scan_pypi_release)
    graph.add_node("approve_uv_sync", approve_uv_sync)
    graph.add_node("run_uv_sync", run_uv_sync)

    graph.set_entry_point("inspect_project")
    graph.add_edge("inspect_project", "list_updates")
    graph.add_edge("list_updates", "scan_pypi_release")
    graph.add_edge("scan_pypi_release", "approve_uv_sync")
    graph.add_edge("approve_uv_sync", "run_uv_sync")
    graph.add_edge("run_uv_sync", END)
    return graph.compile()
