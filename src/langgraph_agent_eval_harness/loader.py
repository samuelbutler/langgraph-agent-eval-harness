from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import ValidationError

from .schema import Scenario


class ScenarioLoadError(ValueError):
    """Raised when a scenario file cannot be loaded or validated."""


def scenario_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        raise ScenarioLoadError(f"Scenario path does not exist: {path}")
    if path.is_file():
        if path.suffix not in {".yaml", ".yml"}:
            raise ScenarioLoadError(f"Scenario file must be .yaml or .yml: {path}")
        yield path
        return
    yield from sorted([*path.glob("*.yaml"), *path.glob("*.yml")])


def _load_yaml(file: Path) -> Any:
    try:
        return yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioLoadError(f"Invalid YAML in {file}: {exc}") from exc


def _validate_scenario(data: Any, file: Path, index: int | None = None) -> Scenario:
    label = f"{file}" if index is None else f"{file}[{index}]"
    if data is None:
        raise ScenarioLoadError(f"Empty scenario: {label}")
    try:
        return Scenario.model_validate(data)
    except ValidationError as exc:
        raise ScenarioLoadError(f"Invalid scenario {label}: {exc}") from exc


def load_scenarios(path: str | Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for file in scenario_files(Path(path)):
        data = _load_yaml(file)
        if isinstance(data, list):
            scenarios.extend(_validate_scenario(item, file, idx) for idx, item in enumerate(data))
        else:
            scenarios.append(_validate_scenario(data, file))
    if not scenarios:
        raise ScenarioLoadError(f"No scenario files found in {path}")
    return scenarios
