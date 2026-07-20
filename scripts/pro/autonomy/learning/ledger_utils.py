"""LedgerUtils — carga y validación compartida del ExecutionLedger.

Elimina la duplicación D1 (learning.py + pattern_analyzer.py tenían la misma lógica de carga).
Valida esquema, ignora registros inválidos, contabiliza descartes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {"execution_id", "start_time", "pipeline"}
OPTIONAL_FIELDS = {
    "goal", "decisions", "plan", "evaluation",
    "pattern_detections", "knowledge", "recommendations", "policies", "verifications",
    "plugin_status", "plugin_durations", "plugins_activated",
    "phases_executed", "phases_skipped",
    "changed_files", "changed_lines", "promotion", "rollback",
    "warnings", "errors", "resources", "result",
    "duration_ms", "git_commit_before", "git_commit_after",
}


class LedgerValidator:
    """Valida entradas del ledger. Ignora inválidas, contabiliza descartes."""

    def __init__(self, nervioso: Path) -> None:
        self._ledger_dir = nervioso / "ledger"
        self._stats = {"total": 0, "validos": 0, "invalidos": 0, "motivos": {}}

    def _record_invalid(self, reason: str) -> None:
        self._stats["invalidos"] += 1
        self._stats["motivos"][reason] = self._stats["motivos"].get(reason, 0) + 1

    def _is_valid(self, entry: dict) -> bool:
        """Valida una entrada del ledger.

        Criterios:
        - Debe tener execution_id, start_time, pipeline
        - goal puede ser None (registros pre-v3.0) — válido
        - plugins opcionales — válido
        """
        for field in REQUIRED_FIELDS:
            if field not in entry:
                self._record_invalid(f"missing_{field}")
                return False
            if entry[field] is None:
                self._record_invalid(f"null_{field}")
                return False
        # engine_version puede no existir en registros muy antiguos
        return True

    def load(self) -> list[dict[str, Any]]:
        """Carga el ledger. Ignora corruptos. Retorna solo válidos."""
        if not self._ledger_dir.exists():
            return []

        validos = []
        for f in sorted(self._ledger_dir.glob("*.json")):
            self._stats["total"] += 1
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                if self._is_valid(entry):
                    validos.append(entry)
                # Si es inválido, _record_invalid ya se llamó
            except (json.JSONDecodeError, OSError):
                self._record_invalid("corrupto_json")
                continue

        self._stats["validos"] = len(validos)
        return validos

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    @property
    def summary(self) -> str:
        s = self._stats
        partes = [f"Ledger: {s['total']} registros"]
        partes.append(f"{s['validos']} válidos")
        if s['invalidos']:
            partes.append(f"{s['invalidos']} inválidos")
            for motivo, count in s['motivos'].items():
                partes.append(f"  - {motivo}: {count}")
        return "\n".join(partes)
