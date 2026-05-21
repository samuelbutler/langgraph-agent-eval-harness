from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .loader import load_scenarios
from .runner import ScenarioRunner
from .scorer import score_trace

app = typer.Typer(help="Run scenario evals for LangGraph-style agents.")
console = Console()


@app.command()
def run(path: Path, json_out: Path | None = None) -> None:
    scenarios = load_scenarios(path)
    runner = ScenarioRunner()
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


if __name__ == "__main__":
    app()
