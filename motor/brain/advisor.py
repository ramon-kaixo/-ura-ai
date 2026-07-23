"""Cerebro propositor.

Basado en analisis, propone acciones concretas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from motor.brain.analyzer import CodeAnalyzer


class ArchitectureAdvisor:
    def __init__(self) -> None:
        self.analyzer = CodeAnalyzer()

    def propose(self, module_path: str) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        for result in self.analyzer.analyze_module(Path(module_path)):
            if result.get("complex_functions"):
                proposals.append(
                    {
                        "type": "refactor",
                        "target": result["file"],
                        "reason": f"Funciones complejas: {result['complex_functions']}",
                        "priority": "high",
                    }
                )
            if result.get("lines", 0) > 500:
                proposals.append(
                    {
                        "type": "split",
                        "target": result["file"],
                        "reason": f"Archivo grande: {result['lines']} lines",
                        "priority": "medium",
                    }
                )
        return proposals
