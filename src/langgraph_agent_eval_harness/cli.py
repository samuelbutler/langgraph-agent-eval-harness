from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .loader import load_scenarios
from .npm_security import scan_npm_update
from .runner import ScenarioRunner
from .scorer import score_trace

app = typer.Typer(help="Run scenario evals for LangGraph-style agents.")
console = Console()


@app.command()
def run(path: Path, json_out: Path | None = None, strict_mocks: bool = False) -> None:
    scenarios = load_scenarios(path)
    runner = ScenarioRunner(strict_mocks=strict_mocks)
    results = [score_trace(s, runner.run(s)) for s in scenarios]

    table = Table(title="LangGraph Agent Eval Results")
    table.add_column("Scenario")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    for result in results:
        status = "✅ pass" if result.score == result.max_score else "❌ fail"
        table.add_row(result.scenario_id, f"{result.score}/{result.max_score}", status)
    console.print(table)

    for result in results:
        if result.failed:
            console.print(f"\n[red]{result.scenario_id} failures[/red]")
            for failure in result.failed:
                console.print(f"  - {failure}")

    if json_out:
        json_out.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
        console.print(f"Wrote {json_out}")

    if any(r.failed for r in results):
        raise typer.Exit(1)


@app.command("scan-npm")
def scan_npm(
    package: str,
    from_version: str,
    to_version: str,
    registry_url: str = "https://registry.npmjs.org",
    keep_workdir: bool = False,
) -> None:
    """Download npm tarballs into an isolated temp dir and scan the update."""
    result = scan_npm_update(
        package,
        from_version,
        to_version,
        registry_url=registry_url,
        keep_workdir=keep_workdir,
    )
    console.print_json(json.dumps(asdict(result), default=str))
    if result.verdict != "safe":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
