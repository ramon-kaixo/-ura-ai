"""ReportingPlugin — generación de informes y guardado de estado."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class ReportingPlugin:
    """Plugins de reporting y persistencia de estado."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def save_maintenance_state(self, results: dict[str, Any], nivel: str) -> None:
        """Guarda el estado de la ejecución en .nervioso/."""
        state = {
            "ultima_ejecucion": datetime.now(UTC).isoformat(),
            "nivel": nivel,
            "resultado": results,
        }
        state_file = self.engine.config.nervioso / "estado_mantenimiento.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        self.engine.log.info(f"Estado guardado en {state_file}")

    def generate_report(self, results: dict[str, Any]) -> str:
        """Genera un bloque de texto con el informe."""
        lines = []
        for k, v in results.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    lines.append(f"  {k}.{sk}: {sv}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
