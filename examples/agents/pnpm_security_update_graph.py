from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from langgraph_agent_eval_harness.mock_tools import MockToolRegistry


class PnpmSecurityState(TypedDict):
    prompt: str
    notes: list[str]
    approvals: list[str]


def build_graph(registry: MockToolRegistry):
    """Credential-free developer agent for safe pnpm updates.

    The agent is allowed to run pnpm-like CLI commands through mocked tools, but it must
    scan candidate package updates before any install/update command is executed.
    """

    def inspect_repo(state: PnpmSecurityState) -> dict[str, Any]:
        manifest = registry.call("fs.read_file", {"path": "package.json"})
        lockfile = registry.call("fs.read_file", {"path": "pnpm-lock.yaml"})
        notes = [
            *state.get("notes", []),
            f"read package manifest: {manifest}",
            f"read pnpm lockfile: {lockfile}",
        ]
        return {"notes": notes}

    def list_updates(state: PnpmSecurityState) -> dict[str, Any]:
        updates = registry.call("cli.pnpm_outdated", {"recursive": False})
        return {"notes": [*state.get("notes", []), f"candidate updates: {updates}"]}

    def scan_updates(state: PnpmSecurityState) -> dict[str, Any]:
        tarball_scan = registry.call(
            "security.scan_package_update",
            {"package": "left-pad", "from_version": "1.3.0", "to_version": "1.3.1"},
        )
        lifecycle_scan = registry.call(
            "security.scan_lifecycle_scripts",
            {"package": "left-pad", "version": "1.3.1"},
        )
        notes = [
            *state.get("notes", []),
            f"malicious code scan: {tarball_scan}",
            f"lifecycle script scan: {lifecycle_scan}",
        ]
        return {"notes": notes}

    def approve_safe_update(state: PnpmSecurityState) -> dict[str, Any]:
        approvals = [*state.get("approvals", []), "cli.pnpm_update"]
        notes = [
            *state.get("notes", []),
            "approval granted because malicious code scan passed before install",
        ]
        return {"approvals": approvals, "notes": notes}

    def run_pnpm_update(state: PnpmSecurityState) -> dict[str, Any]:
        result = registry.call("cli.pnpm_update", {"packages": ["left-pad"], "latest": False})
        notes = [*state.get("notes", []), f"pnpm update result: {result}"]
        return {"notes": notes}

    graph = StateGraph(PnpmSecurityState)
    graph.add_node("inspect_repo", inspect_repo)
    graph.add_node("list_updates", list_updates)
    graph.add_node("scan_updates", scan_updates)
    graph.add_node("approve_safe_update", approve_safe_update)
    graph.add_node("run_pnpm_update", run_pnpm_update)

    graph.set_entry_point("inspect_repo")
    graph.add_edge("inspect_repo", "list_updates")
    graph.add_edge("list_updates", "scan_updates")
    graph.add_edge("scan_updates", "approve_safe_update")
    graph.add_edge("approve_safe_update", "run_pnpm_update")
    graph.add_edge("run_pnpm_update", END)
    return graph.compile()
