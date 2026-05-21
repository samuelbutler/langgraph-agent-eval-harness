from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable

from .mock_tools import MockToolRegistry

GraphFactory = Callable[[MockToolRegistry], Any]


def load_graph_factory(spec: str) -> GraphFactory:
    """Load `package.module:function` and return the graph factory."""
    if ":" not in spec:
        raise ValueError("Graph spec must look like 'module.submodule:function_name'")
    module_name, function_name = spec.split(":", 1)
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    module = importlib.import_module(module_name)
    factory = getattr(module, function_name)
    if not callable(factory):
        raise TypeError(f"{spec} is not callable")
    return factory


def invoke_graph(spec: str, registry: MockToolRegistry, prompt: str) -> dict[str, Any]:
    graph = load_graph_factory(spec)(registry)
    return graph.invoke({"prompt": prompt, "notes": [], "approvals": []})
