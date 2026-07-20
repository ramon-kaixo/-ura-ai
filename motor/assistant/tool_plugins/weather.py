"""Ejemplo de plugin: consulta de clima."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from motor.assistant.executor import ToolResult

from motor.assistant.tool_plugin import ToolPlugin


class WeatherPlugin(ToolPlugin):
    name = "weather"
    description = "Consulta el clima actual de una ciudad"
    keywords = ("clima", "weather", "temperatura", "tiempo")

    async def execute(self, params: dict[str, Any] | None = None) -> ToolResult:
        from motor.assistant.executor import ToolResult
        location = params.get("location", "")
        if not location:
            return ToolResult(False, error="Ciudad no especificada")
        try:
            resp = await httpx.get(
                f"https://wttr.in/{location}?format=%C+%t+%w+%h",
                timeout=10,
            )
            if resp.status_code == 200:
                return ToolResult(True, f"Clima en {location}: {resp.text}")
            return ToolResult(False, error=f"Error {resp.status_code}")
        except Exception as e:
            return ToolResult(False, error=str(e))
