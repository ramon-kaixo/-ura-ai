# PLUGIN = {"name": "reuse_detector", "phase": "pre", "timeout": 60, "priority": 100, "capability": "quality", "args": ["index"]}
"""ReuseDetector — busca código similar antes de crear código nuevo.

Escanea el repositorio, extrae firmas de funciones con AST,
compara contra código nuevo propuesto y recomienda reutilización.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.pro.reuse.ast_index import index_file
from scripts.pro.reuse.similarity import compare


class ReuseDetector:
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
        import tempfile
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
