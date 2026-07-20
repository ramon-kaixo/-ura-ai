"""ToolPlugin — plugin system for external tools."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.assistant.executor import ToolResult

PLUGIN_DIR = Path(__file__).resolve().parent / "tool_plugins"


class ToolPlugin:
    name: str = ""
    description: str = ""
    keywords: list[str] | None = None

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


def discover_plugins() -> dict[str, ToolPlugin]:
    plugins: dict[str, ToolPlugin] = {}
    if not PLUGIN_DIR.exists():
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        return plugins
    for f in sorted(PLUGIN_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and issubclass(obj, ToolPlugin) and obj is not ToolPlugin:
                    instance = obj()
                    if instance.name:
                        plugins[instance.name] = instance
        except Exception:
            continue
    return plugins
