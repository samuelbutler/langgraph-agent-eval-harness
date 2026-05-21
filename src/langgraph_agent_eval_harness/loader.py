from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .schema import Scenario


def scenario_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    yield from sorted([*path.glob("*.yaml"), *path.glob("*.yml")])


def load_scenarios(path: str | Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for file in scenario_files(Path(path)):
        data = yaml.safe_load(file.read_text())
        if isinstance(data, list):
            scenarios.extend(Scenario.model_validate(item) for item in data)
        else:
            scenarios.append(Scenario.model_validate(data))
    return scenarios
