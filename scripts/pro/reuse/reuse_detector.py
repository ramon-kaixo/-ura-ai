"""ReuseDetector — busca código similar antes de crear código nuevo.

PLUGIN para plugin_registry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

PLUGIN = {
    "name": "reuse_detector",
    "phase": "pre",
    "timeout": 60,
    "priority": 100,
    "capability": "quality",
    "args": ["index"],
}

from scripts.pro.reuse.ast_index import index_file  # noqa: E402
from scripts.pro.reuse.similarity import compare  # noqa: E402


class ReuseDetector:
    _feedback: list[dict] = []  # retroalimentación: aceptado/rechazado

    @classmethod
    def metrics(cls) -> dict:
        """Métricas de eficacia del detector."""
        total = len(cls._feedback)
        if total == 0:
            return {"recomendaciones_emitidas": 0, "tasa_aceptacion": 0, "reutilizaciones_efectivas": 0}
        accepted = sum(1 for f in cls._feedback if f.get("accepted"))
        rejected = total - accepted
        return {
            "recomendaciones_emitidas": total,
            "recomendaciones_aceptadas": accepted,
            "recomendaciones_rechazadas": rejected,
            "tasa_aceptacion": round(accepted / total, 2),
            "reutilizaciones_efectivas": accepted,
        }

    """Detector de reutilización. Indexa el repo y compara firmas."""

    def __init__(self, project_root: str | Path = "") -> None:
        self._root = Path(project_root or Path.cwd())
        self._index: list[dict[str, Any]] = []

    def build_index(self, max_files: int = 0) -> int:
        """Indexa todos los .py del proyecto."""
        processed = 0
        for pyfile in sorted(self._root.rglob("*.py")):
            if ".venv" in str(pyfile) or ".sandbox" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            entries = index_file(pyfile)
            self._index.extend(entries)
            processed += 1
            if max_files and processed >= max_files:
                break
        return len(self._index)

    def search(self, name: str, min_score: float = 0.4) -> list[dict]:
        """Busca funciones existentes similares a un nombre dado."""
        if not self._index:
            return []
        query = {"name": name, "params": [], "body_hash": "", "calls": [], "docstring_preview": ""}
        results = []
        for entry in self._index:
            result = compare(query, entry)
            if result["score"] >= min_score:
                results.append(result)
        results.sort(key=lambda r: -r["score"])
        return results[:10]

    def analyze_new_code(self, code: str, min_score: float = 0.4) -> list[dict]:
        """Analiza código nuevo contra el índice."""
        tmp = Path(tempfile.mktemp(suffix=".py"))
        try:
            tmp.write_text(code)
            new_entries = index_file(tmp)
        finally:
            tmp.unlink(missing_ok=True)

        if not new_entries:
            return []

        results = []
        for new_entry in new_entries:
            for existing in self._index:
                if new_entry["type"] != existing["type"]:
                    continue
                result = compare(new_entry, existing)
                if result["score"] >= min_score:
                    result["categoria_desc"] = {
                        "reutilizar": "Reutilizar directamente",
                        "adaptar": "Adaptar con cambios menores",
                        "revisar": "Revisar antes de implementar",
                        "descarta": "Código diferente, implementación segura",
                    }.get(result["categoria"], "")
                    results.append(result)
        results.sort(key=lambda r: -r["score"])
        return results[:15]

    @classmethod
    def record_feedback(cls, recommendation: dict, accepted: bool, reason: str = "") -> None:
        """Registra retroalimentación sobre una recomendación para ajustar pesos futuros."""
        cls._feedback.append(
            {
                "new_name": recommendation.get("new_name", ""),
                "existing_name": recommendation.get("existing_name", ""),
                "score": recommendation.get("score", 0),
                "accepted": accepted,
                "reason": reason,
            }
        )
