#!/usr/bin/env python3
"""
ForensicScribe - Escribiente Causal de URA
Registro absoluto, análisis de detonantes, cruce de patrones y predicción.
"""

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIBE_LOG_PATH = Path.home() / ".ura" / "scribe_log.json"
CAUSAS_RAIZ_PATH = Path.home() / ".ura" / "causas_raiz.json"
SCRIBE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
MAX_EVENTS = 1000
TRACE_WINDOW = 50
PREDICT_WINDOW = 100
SIMILARITY_THRESHOLD = 0.7


class ForensicScribe:
    """Escribiente causal: registra, analiza y predice."""

    def __init__(self):
        self.events = self._load_events()
        self.causas_raiz = self._load_causas_raiz()

    def _load_events(self) -> list[dict]:
        if SCRIBE_LOG_PATH.exists():
            try:
                with open(SCRIBE_LOG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando scribe_log: {e}")
        return []

    def _load_causas_raiz(self) -> list[dict]:
        if CAUSAS_RAIZ_PATH.exists():
            try:
                with open(CAUSAS_RAIZ_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando causas_raiz: {e}")
        return []

    def _save_events(self):
        with open(SCRIBE_LOG_PATH, "w") as f:
            json.dump(self.events, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    def _save_causas_raiz(self):
        with open(CAUSAS_RAIZ_PATH, "w") as f:
            json.dump(self.causas_raiz, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    def log_event(
        self,
        event_type: str,
        module: str,
        action: str,
        context: dict = None,
        dependencies: list[str] = None,
    ):
        """Registrar evento en el historial circular."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "module": module,
            "action": action,
            "context": context or {},
            "dependencies": dependencies or [],
        }
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]
        self._save_events()

    def trace_trigger(self, error_message: str, error_module: str) -> dict | None:
        """Buscar el detonante más probable de un error."""
        if len(self.events) < 2:
            return None

        window = (
            self.events[-TRACE_WINDOW:] if len(self.events) > TRACE_WINDOW else self.events[:-1]
        )
        if not window:
            return None

        error_keywords = set(re.findall(r"\w+", error_message.lower()))
        best_score = 0
        best_event = None

        for event in reversed(window):
            score = 0
            if event.get("module") == error_module:
                score += 3
            event_text = f"{event.get('action', '')} {event.get('module', '')} {' '.join(event.get('dependencies', []))}"
            event_keywords = set(re.findall(r"\w+", event_text.lower()))
            overlap = len(error_keywords & event_keywords)
            score += overlap * 2
            if event.get("type") in ("error", "warning", "failure"):
                score += 2
            if score > best_score:
                best_score = score
                best_event = event

        return best_event

    def cross_reference_detonates(self) -> list[dict]:
        """Cruzar patrones de detonantes para identificar problemas sistémicos."""
        systemic = []
        module_groups = {}
        for causa in self.causas_raiz:
            mod = causa.get("module", "unknown")
            module_groups.setdefault(mod, []).append(causa)

        for mod, causas in module_groups.items():
            if len(causas) >= 2:
                actions = Counter(c.get("action_type", "") for c in causas)
                systemic.append(
                    {
                        "module": mod,
                        "count": len(causas),
                        "common_actions": actions.most_common(3),
                        "marked_systemic": True,
                    }
                )
        return systemic

    def predict_issues(self) -> list[dict]:
        """Predecir problemas futuros basado en patrones sistémicos."""
        alerts = []
        if len(self.events) < 10:
            return alerts

        recent = self.events[-PREDICT_WINDOW:]
        systemic = self.cross_reference_detonates()

        for pattern in systemic:
            mod = pattern["module"]
            recent_mod_events = [e for e in recent if e.get("module") == mod]
            if recent_mod_events:
                for causa in self.causas_raiz:
                    if causa.get("module") == mod and causa.get("verified"):
                        causa_keywords = set(
                            re.findall(r"\w+", causa.get("patron_error", "").lower())
                        )
                        for event in recent_mod_events[-10:]:
                            event_text = f"{event.get('action', '')} {event.get('type', '')} {json.dumps(event.get('context', {}))}"
                            event_keywords = set(re.findall(r"\w+", event_text.lower()))
                            if causa_keywords and event_keywords:
                                sim = len(causa_keywords & event_keywords) / len(
                                    causa_keywords | event_keywords
                                )
                                if sim > SIMILARITY_THRESHOLD:
                                    alerts.append(
                                        {
                                            "module": mod,
                                            "predicted_issue": causa.get("patron_error", ""),
                                            "similarity": round(sim, 2),
                                            "solution": causa.get("solucion_permanente", ""),
                                            "timestamp": datetime.now().isoformat(),
                                        }
                                    )
        return alerts

    def register_root_cause(
        self,
        patron_error: str,
        causa_raiz: str,
        solucion_permanente: str,
        archivos_corregidos: list[str],
        module: str = "",
        action_type: str = "",
    ):
        """Registrar causa raíz verificada."""
        entry = {
            "patron_error": patron_error,
            "causa_raiz": causa_raiz,
            "solucion_permanente": solucion_permanente,
            "archivos_corregidos": archivos_corregidos,
            "module": module,
            "action_type": action_type,
            "verified": True,
            "timestamp": datetime.now().isoformat(),
        }
        self.causas_raiz.append(entry)
        self._save_causas_raiz()
        logger.info(f"Causa raíz registrada: {patron_error[:60]}")

    def find_verified_solution(self, error_message: str) -> dict | None:
        """Buscar solución verificada para un error."""
        for causa in self.causas_raiz:
            if (
                causa.get("verified")
                and causa.get("patron_error", "").lower() in error_message.lower()
            ):
                return causa
        return None

    def get_status(self) -> dict:
        """Obtener estado del escribiente."""
        systemic = self.cross_reference_detonates()
        predictions = self.predict_issues()
        return {
            "total_events": len(self.events),
            "total_root_causes": len(self.causas_raiz),
            "last_detonante": self.events[-1] if self.events else None,
            "systemic_patterns": len(systemic),
            "active_alerts": len(predictions),
            "predictions": predictions[:5],
        }


_forensic_scribe: ForensicScribe | None = None


def get_forensic_scribe() -> ForensicScribe:
    global _forensic_scribe
    if _forensic_scribe is None:
        _forensic_scribe = ForensicScribe()
    return _forensic_scribe
