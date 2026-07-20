"""KnowledgeBase v2 — confianza dinámica, versionado, políticas de olvido.

Cada entrada tiene:
  - confidence que evoluciona con verificaciones (dinámica)
  - version lifecycle (created → modified → deprecated → archived)
  - historial de cambios
  - forzado de archive para conocimiento antiguo no verificado
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class KnowledgeBase:
    """Base de conocimiento con confianza dinámica, versionado y olvido."""

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
        """Crea una entrada de conocimiento con versionado."""
        entry = {
            "id": f"k{int(datetime.now(UTC).timestamp())}",
            "version": 1,
            "claim": claim,
            "evidence": evidence,
            "confidence": round(confidence, 2),
            "category": category,
            "source": source,
            "status": "active",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "verified": False,
            "verifications": 0,
            "verification_history": [],
            "history": [{"action": "created", "timestamp": datetime.now(UTC).isoformat()}],
        }
        self._entries.append(entry)
        self._save()
        return entry

    def search(self, category: str | None = None, min_confidence: float = 0.0,
               status: str = "active") -> list[dict]:
        """Busca conocimiento activo por categoría y confianza mínima."""
        results = [e for e in self._entries if e.get("status") == status]
        if category:
            results = [e for e in results if e.get("category") == category]
        if min_confidence:
            results = [e for e in results if (e.get("confidence") or 0) >= min_confidence]
        return results

    def verify(self, entry_id: str, success: bool) -> None:
        """Verifica una entrada. La confianza evoluciona dinámicamente.

        Regla:
          - Cada verificación exitosa → confidence +0.05 (máx 0.95)
          - Cada verificación fallida  → confidence × 0.5
          - Si confidence < 0.2 después de fallos → deprecar
        """
        for e in self._entries:
            if e["id"] == entry_id:
                before = e.get("confidence", 0.5)
                e["verifications"] = e.get("verifications", 0) + 1
                e["last_verified"] = datetime.now(UTC).isoformat()

                if success:
                    e["confidence"] = min(0.95, round(before + 0.05, 2))
                    e["verified"] = True
                else:
                    new_conf = round(before * 0.5, 2)
                    e["confidence"] = new_conf
                    if new_conf < 0.2:
                        e["status"] = "deprecated"
                        e["history"].append({
                            "action": "deprecated",
                            "reason": f"confidence dropped to {new_conf}",
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                e["verification_history"].append({
                    "success": success,
                    "confidence_after": e["confidence"],
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                e["updated_at"] = datetime.now(UTC).isoformat()
                self._save()
                break

    def update(self, entry_id: str, new_claim: str, new_evidence: str) -> dict | None:
        """Actualiza una entrada. Incrementa versión, mantiene historial."""
        for e in self._entries:
            if e["id"] == entry_id:
                e["version"] = e.get("version", 1) + 1
                e["history"].append({
                    "action": f"updated_to_v{e['version']}",
                    "old_claim": e.get("claim", ""),
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                e["claim"] = new_claim
                e["evidence"] = new_evidence
                e["updated_at"] = datetime.now(UTC).isoformat()
                self._save()
                return e
        return None

    def deprecate(self, entry_id: str, reason: str = "") -> None:
        """Marca una entrada como deprecated (obsoleta pero no eliminada)."""
        for e in self._entries:
            if e["id"] == entry_id:
                e["status"] = "deprecated"
                e["history"].append({
                    "action": "deprecated",
                    "reason": reason,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                e["updated_at"] = datetime.now(UTC).isoformat()
                self._save()
                break

    def forget(self, max_age_days: int = 90, min_confidence: float = 0.0) -> list[str]:
        """Política de olvido: archiva entradas antiguas no verificadas.

        Criterios de archive:
          1. status = active, no verificadas, edad > max_age_days
          2. status = deprecated, edad > max_age_days
          3. confidence < min_confidence y edad > max_age_days / 2
        """
        now = datetime.now(UTC)
        archived = []
        for e in self._entries:
            if e.get("status") == "archived":
                continue
            try:
                created = datetime.fromisoformat(e.get("created_at", ""))
            except (ValueError, TypeError):
                continue
            age = (now - created).days

            should_archive = False
            if e.get("status") == "deprecated" and age > max_age_days:
                should_archive = True
            elif e.get("status") == "active" and not e.get("verified") and age > max_age_days:
                should_archive = True
            elif (e.get("confidence") or 0) < min_confidence and age > max_age_days // 2:
                should_archive = True

            if should_archive:
                e["status"] = "archived"
                e["history"].append({
                    "action": "archived",
                    "reason": f"forget policy: age={age}d, confidence={e.get('confidence', 0)}",
                    "timestamp": now.isoformat(),
                })
                archived.append(e["id"])

        if archived:
            self._save()
        return archived

    def stats(self) -> dict[str, int]:
        """Estadísticas del conocimiento almacenado."""
        return {
            "total": len(self._entries),
            "active": sum(1 for e in self._entries if e.get("status") == "active"),
            "deprecated": sum(1 for e in self._entries if e.get("status") == "deprecated"),
            "archived": sum(1 for e in self._entries if e.get("status") == "archived"),
            "verified": sum(1 for e in self._entries if e.get("verified")),
        }

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
