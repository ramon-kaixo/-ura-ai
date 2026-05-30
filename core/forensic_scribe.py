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


# Contador de fallos por fase (aprendizaje automático)
def get_phase_failures(phase_name: str, since_days: int = 30) -> int:
    import json
    from datetime import datetime, timedelta

    log_path = Path.home() / ".ura" / "scribe_log.json"
    if not log_path.exists():
        return 0
    with open(log_path) as f:
        events = json.load(f)
    cutoff = datetime.now() - timedelta(days=since_days)
    return sum(
        1
        for e in events
        if e.get("type") == "pro_rollback"
        and e.get("module") == f"phase{phase_name}"
        and datetime.fromisoformat(e.get("context", {}).get("timestamp", "2000-01-01T00:00:00"))
        > cutoff
    )


def suggest_fix_if_repeated_failures(phase_name: str, threshold: int = 3) -> str | None:
    failures = get_phase_failures(phase_name)
    if failures >= threshold:
        return f"La fase {phase_name} ha fallado {failures} veces en 30 días. Revisa las reglas asociadas."
    return None


# Métricas de falsos positivos por herramienta
def record_tool_findings(tool_name: str, total_findings: int, false_positives: int):
    import json
    from pathlib import Path

    p = Path.home() / ".ura" / "tool_metrics.json"
    m = {}
    if p.exists():
        with open(p) as f:
            m = json.load(f)
    if tool_name not in m:
        m[tool_name] = {"total_findings": 0, "false_positives": 0, "history": []}
    m[tool_name]["total_findings"] += total_findings
    m[tool_name]["false_positives"] += false_positives
    m[tool_name]["history"].append(
        {
            "date": __import__("datetime").datetime.now().isoformat(),
            "total": total_findings,
            "fp": false_positives,
            "fp_rate": false_positives / total_findings if total_findings > 0 else 0,
        }
    )
    with open(p, "w") as f:
        json.dump(m, f, indent=2)


def get_tool_fp_rate(tool_name: str) -> float:
    import json
    from pathlib import Path

    p = Path.home() / ".ura" / "tool_metrics.json"
    if not p.exists():
        return 0.0
    with open(p) as f:
        m = json.load(f)
    if tool_name not in m:
        return 0.0
    t = m[tool_name]["total_findings"]
    return m[tool_name]["false_positives"] / t if t > 0 else 0.0


def suggest_tool_calibration(tool_name: str, threshold: float = 0.3):
    rate = get_tool_fp_rate(tool_name)
    if rate > threshold:
        return f"⚠️  {tool_name} FP rate: {rate:.0%}. Revisar reglas."
    return None


# Decisión con resultado a largo plazo
def record_decision_outcome(decision_id: str, outcome: str, impact_score: float):
    import json

    p = Path.home() / ".ura" / "decision_outcomes.json"
    o = json.loads(p.read_text()) if p.exists() else {}
    o[decision_id] = {
        "outcome": outcome,
        "impact_score": impact_score,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }
    p.write_text(json.dumps(o, indent=2))


def should_repeat_decision(decision_pattern: str) -> bool:
    import json

    p = Path.home() / ".ura" / "decision_outcomes.json"
    if not p.exists():
        return True
    o = json.loads(p.read_text())
    similar = [v for v in o.values() if decision_pattern in str(v)]
    if not similar:
        return True
    rate = sum(1 for s in similar if s["outcome"] == "success") / len(similar)
    return rate >= 0.7


def evaluar_impacto_decision(decision_id: str) -> dict | None:
    """Compara métricas antes y después de una decisión."""
    import json
    from pathlib import Path

    metrics_dir = Path.home() / "URA" / "ura_ia_1972" / "docs" / "metrics"
    if not metrics_dir.exists():
        return None
    m = sorted(metrics_dir.glob("quality_*.json"))
    if len(m) < 2:
        return None
    actual = json.loads(m[-1].read_text())
    anterior = json.loads(m[-2].read_text())
    impacto = {
        "decision_id": decision_id,
        "lineas_antes": anterior.get("lineas", 0),
        "lineas_despues": actual.get("lineas", 0),
        "tests_antes": anterior.get("tests_pasados", 0),
        "tests_despues": actual.get("tests_pasados", 0),
        "mejora": actual.get("lineas", 0) <= anterior.get("lineas", 0)
        and actual.get("tests_pasados", 0) >= anterior.get("tests_pasados", 0),
    }
    record_decision_outcome(
        decision_id,
        "success" if impacto["mejora"] else "degraded",
        impacto["tests_despues"] - impacto["tests_antes"],
    )
    return impacto
