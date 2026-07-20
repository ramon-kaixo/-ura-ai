"""KnowledgeBase — persiste conocimiento útil extraído del análisis.

No almacena logs. Almacena conocimiento accionable como:
  Plugin X falla con Python 3.13
  El orden A→B reduce errores
  Ruff antes del refactor evita regresiones
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class KnowledgeBase:
    """Base de conocimiento persistente en .nervioso/knowledge/."""

    def __init__(self, nervioso: Path) -> None:
        self._dir = nervioso / "knowledge"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        path = self._dir / "knowledge.json"
        if path.exists():
            try:
                self._entries = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def _save(self) -> None:
        path = self._dir / "knowledge.json"
        path.write_text(json.dumps(self._entries, indent=2, ensure_ascii=False))

    def add(self, claim: str, evidence: str, confidence: float = 0.5,
            category: str = "rendimiento", source: str = "") -> dict:
        entry = {
            "id": f"k{len(self._entries) + 1}",
            "claim": claim,
            "evidence": evidence,
            "confidence": round(confidence, 2),
            "category": category,
            "source": source,
            "created_at": datetime.now(UTC).isoformat(),
            "verified": False,
            "verifications": 0,
        }
        self._entries.append(entry)
        self._save()
        return entry

    def search(self, category: str | None = None, min_confidence: float = 0.0) -> list[dict]:
        results = self._entries
        if category:
            results = [e for e in results if e["category"] == category]
        if min_confidence:
            results = [e for e in results if e["confidence"] >= min_confidence]
        return results

    def verify(self, entry_id: str, success: bool) -> None:
        for e in self._entries:
            if e["id"] == entry_id:
                e["verified"] = success
                e["verifications"] = e.get("verifications", 0) + 1
                e["last_verified"] = datetime.now(UTC).isoformat()
                self._save()
                break

    def from_pattern(self, pattern: dict) -> dict | None:
        """Crea entrada de conocimiento desde un patrón detectado."""
        pname = pattern.get("pattern", "")
        if "plugin_fail" in pname:
            plugin = pname.replace("plugin_fail_", "")
            return self.add(
                claim=f"El plugin {plugin} tiene una tasa de fallo del {pattern.get('tasa_fallo', 0) * 100}%",
                evidence=f"Detectado en {pattern.get('occurrences', 0)} de {pattern.get('total_ejecuciones', 0)} ejecuciones",
                confidence=1.0 - pattern.get('tasa_fallo', 0),
                category="fiabilidad",
                source="pattern_analyzer",
            )
        if "phase_slow" in pname:
            phase = pname.replace("phase_slow_", "")
            return self.add(
                claim=f"La fase {phase} tiene picos de hasta {pattern.get('max_s', 0)}s (media: {pattern.get('avg_s', 0)}s)",
                evidence=f"{pattern.get('occurrences', 0)} ejecuciones superaron el doble de la media",
                confidence=0.7,
                category="rendimiento",
                source="pattern_analyzer",
            )
        return None
