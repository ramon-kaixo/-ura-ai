#!/usr/bin/env python3
"""
ErrorCrossReference - Sistema de cruce de errores de URA.
Detecta correlaciones, puntúa módulos y sugiere refactorizaciones.
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

ERROR_PATTERNS_PATH = Path.home() / ".ura" / "error_patterns.json"
CAUSAS_RAIZ_PATH = Path.home() / ".ura" / "causas_raiz.json"


class ErrorCrossReference:
    """Cruzar errores para detectar correlaciones y módulos problemáticos."""

    def __init__(self):
        from core.forensic_scribe import get_forensic_scribe

        self.scribe = get_forensic_scribe()
        self.error_patterns = self._load_patterns()
        self.causas_raiz = self._load_causas()

    def _load_patterns(self) -> list[dict]:
        if ERROR_PATTERNS_PATH.exists():
            try:
                with open(ERROR_PATTERNS_PATH) as f:
                    return json.load(f).get("patterns", [])
            except Exception as e:
                logger.warning(f"Error cargando patterns: {e}")
        return []

    def _load_causas(self) -> list[dict]:
        if CAUSAS_RAIZ_PATH.exists():
            try:
                with open(CAUSAS_RAIZ_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando causas: {e}")
        return []

    def find_correlations(self) -> dict:
        """Cruzar todos los errores buscando correlaciones."""
        self.error_patterns = self._load_patterns()
        self.causas_raiz = self._load_causas()

        # a) Módulos afectados en común
        module_to_errors = defaultdict(list)
        for p in self.error_patterns:
            for archivo in p.get("archivos_afectados", []):
                module_to_errors[archivo].append(p.get("error_id", ""))
        for c in self.causas_raiz:
            for archivo in c.get("archivos_corregidos", []):
                module_to_errors[archivo].append(c.get("patron_error", "")[:40])
        common_modules = {m: errs for m, errs in module_to_errors.items() if len(errs) > 1}

        # b) Secuencias temporales (ventanas de 5 min en scribe events)
        events = self.scribe.events
        error_events = [e for e in events if e.get("type") in ("error", "warning", "failure")]
        temporal_pairs = []
        for i, e1 in enumerate(error_events):
            try:
                t1 = datetime.fromisoformat(e1.get("timestamp", ""))
            except Exception:
                continue
            for e2 in error_events[i + 1 : i + 10]:
                try:
                    t2 = datetime.fromisoformat(e2.get("timestamp", ""))
                except Exception:
                    continue
                if (t2 - t1) <= timedelta(minutes=5):
                    temporal_pairs.append((e1.get("module", "?"), e2.get("module", "?")))

        pair_counts = Counter(temporal_pairs)

        # c) Errores en cascada (A precede a B con >80% frecuencia)
        cascade = []
        module_errors = defaultdict(list)
        for e in error_events:
            module_errors[e.get("module", "?")].append(e.get("action", ""))
        for (m1, m2), count in pair_counts.most_common(10):
            total_m1 = len([e for e in error_events if e.get("module") == m1])
            if total_m1 > 0 and count / total_m1 >= 0.8:
                cascade.append(
                    {
                        "precede": m1,
                        "sigue": m2,
                        "frecuencia": count,
                        "ratio": round(count / total_m1, 2),
                    }
                )

        return {
            "common_modules": common_modules,
            "temporal_sequences": dict(pair_counts.most_common(10)),
            "cascade_errors": cascade,
            "total_correlations": len(common_modules) + len(pair_counts) + len(cascade),
        }

    def score_modules(self) -> list[dict]:
        """Puntuar cada módulo por problemática."""
        self.error_patterns = self._load_patterns()
        self.causas_raiz = self._load_causas()

        scores = defaultdict(
            lambda: {"error_count": 0, "gravity": 0.0, "frequency": 0, "systemic": False}
        )
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        for p in self.error_patterns:
            gravity = 0.5 + (p.get("auto_repair_count", 0) * 0.1)
            for archivo in p.get("archivos_afectados", []):
                scores[archivo]["error_count"] += 1
                scores[archivo]["gravity"] += gravity

        for c in self.causas_raiz:
            for archivo in c.get("archivos_corregidos", []):
                scores[archivo]["error_count"] += 1
                scores[archivo]["gravity"] += 0.8

        # Frecuencia: errores por semana en scribe
        for event in self.scribe.events:
            if event.get("type") in ("error", "failure"):
                try:
                    ts = datetime.fromisoformat(event.get("timestamp", ""))
                    if ts >= week_ago:
                        mod = event.get("module", "")
                        if mod in scores:
                            scores[mod]["frequency"] += 1
                except Exception:
                    continue

        systemic_patterns = self.scribe.cross_reference_detonates()
        systemic_modules = {sp.get("module") for sp in systemic_patterns}
        for mod in systemic_modules:
            if mod in scores:
                scores[mod]["systemic"] = True

        result = []
        for mod, data in scores.items():
            total_score = (
                data["error_count"] * 2
                + data["gravity"]
                + data["frequency"] * 1.5
                + (5 if data["systemic"] else 0)
            )
            result.append({"module": mod, "score": round(total_score, 2), **data})
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    def suggest_refactors(self) -> list[str]:
        """Generar sugerencias de refactorización concretas."""
        suggestions = []
        correlations = self.find_correlations()
        scores = self.score_modules()

        # Módulos con múltiples errores
        for mod, errors in correlations.get("common_modules", {}).items():
            if len(errors) >= 3:
                suggestions.append(
                    f"El módulo {mod} aparece en {len(errors)} errores distintos: revisar acoplamiento"
                )

        # Errores en cascada
        for c in correlations.get("cascade_errors", []):
            suggestions.append(
                f"Los errores en {c['precede']} y {c['sigue']} ocurren juntos el {int(c['ratio'] * 100)}% de las veces: posible causa común"
            )

        # Top 3 módulos más problemáticos
        for mod_data in scores[:3]:
            if mod_data["score"] >= 5:
                suggestions.append(
                    f"El módulo {mod_data['module']} tiene score {mod_data['score']} (errores: {mod_data['error_count']}, sistémico: {mod_data['systemic']}): considerar rediseño"
                )

        return suggestions

    def get_cross_reference_context(self) -> str:
        """Generar resumen para system prompt."""
        scores = self.score_modules()
        correlations = self.find_correlations()
        suggestions = self.suggest_refactors()

        parts = ["CROSS-REFERENCE DE ERRORES:"]
        if scores:
            parts.append("Top 3 módulos problemáticos:")
            for s in scores[:3]:
                parts.append(f"  - {s['module']} (score: {s['score']})")

        if correlations.get("cascade_errors"):
            parts.append("Correlaciones fuertes:")
            for c in correlations["cascade_errors"][:3]:
                parts.append(f"  - {c['precede']} → {c['sigue']} ({int(c['ratio'] * 100)}%)")

        if suggestions:
            parts.append("Sugerencias prioritarias:")
            for s in suggestions[:3]:
                parts.append(f"  - {s}")

        return "\n".join(parts) + "\n"


_error_cross_reference: ErrorCrossReference | None = None


def get_error_cross_reference() -> ErrorCrossReference:
    global _error_cross_reference
    if _error_cross_reference is None:
        _error_cross_reference = ErrorCrossReference()
    return _error_cross_reference
