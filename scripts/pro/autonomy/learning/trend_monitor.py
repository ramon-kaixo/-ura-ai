"""TrendMonitor — seguimiento de tendencias y verificación de políticas.

Compara métricas antes/después de aplicar una política.
Determina si la política mejoró o empeoró la situación.
"""

from __future__ import annotations

import json
import statistics
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class TrendMonitor:
    """Monitor de tendencias y verificador de políticas."""

    def __init__(self, nervioso: Path) -> None:
        self._policies_file = nervioso / "knowledge" / "applied_policies.json"
        self._policies_file.parent.mkdir(parents=True, exist_ok=True)
        self._policies: list[dict] = []
        self._load()
        self._ledger_dir = nervioso / "ledger"

    def _load(self) -> None:
        if self._policies_file.exists():
            try:
                self._policies = json.loads(self._policies_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._policies = []

    def _save(self) -> None:
        self._policies_file.write_text(json.dumps(self._policies, indent=2, ensure_ascii=False))

    def register_policy(self, policy: dict) -> None:
        policy["metrics_before"] = self._capture_current_metrics()
        policy["status"] = "pending_verification"
        self._policies.append(policy)
        self._save()

    def get_pending_verification(self) -> list[dict]:
        return [p for p in self._policies if p.get("status") == "pending_verification"]

    def compare_before_after(self, policy: dict) -> tuple[float, float]:
        """Compara métricas antes/después. Retorna (before, after)."""
        before = policy.get("metrics_before", {}).get("avg_duration_s", 0)
        metrics_after = self._capture_current_metrics()
        after = metrics_after.get("avg_duration_s", 0)
        return before, after

    def _capture_current_metrics(self) -> dict[str, Any]:
        """Captura métricas actuales del ledger para comparación futura."""
        if not self._ledger_dir.exists():
            return {"avg_duration_s": 0, "total": 0}

        entries = []
        for f in sorted(self._ledger_dir.glob("*.json")):
            try:
                entries.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue

        if not entries:
            return {"avg_duration_s": 0, "total": 0}

        durations = [e.get("duration_ms", 0) for e in entries if e.get("duration_ms")]
        return {
            "avg_duration_s": round(statistics.mean(durations) / 1000, 1) if durations else 0,
            "total": len(entries),
        }

    def mark_verified(self, policy_id: str, success: bool) -> None:
        for p in self._policies:
            if p.get("recommendation_id") == policy_id:
                p["status"] = "verified" if success else "rolled_back"
                p["metrics_after"] = self._capture_current_metrics()
                self._save()
                break
