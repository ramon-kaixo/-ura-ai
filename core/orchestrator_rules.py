#!/usr/bin/env python3
"""orchestrator_rules.py — FSM determinista para el orquestador URA.

Tabla de Verdad:
  ECO  + (Latencia >= 5ms | Carga >= 70%) → TURBO
  TURBO + (Latencia < 2ms & Carga < 30%)  → ECO
  Cualquier otro estado                    → KEEP
"""

THRESHOLDS = {
    "eco_to_turbo_latency_ms": 5.0,
    "eco_to_turbo_cpu_pct": 70.0,
    "turbo_to_eco_latency_ms": 2.0,
    "turbo_to_eco_cpu_pct": 30.0,
}


def evaluate(state: dict) -> str:
    """Evalúa estado y devuelve 'TURBO', 'ECO', o 'KEEP'.

    Args:
        state: Diccionario con current_mode, latency_ms, cpu_pct
    """
    current = state.get("current_mode", "AUTO").upper()
    latency = state.get("latency_ms", -1.0)
    cpu = state.get("cpu_pct", -1.0)

    # ECO + (latencia >= 5ms | cpu >= 70%) → TURBO
    if current == "ECO":
        if latency >= THRESHOLDS["eco_to_turbo_latency_ms"]:
            return "TURBO"
        if cpu >= THRESHOLDS["eco_to_turbo_cpu_pct"]:
            return "TURBO"
        return "KEEP"

    # TURBO + (latencia < 2ms & cpu < 30%) → ECO
    if current == "TURBO":
        if 0 <= latency < THRESHOLDS["turbo_to_eco_latency_ms"]:
            if 0 <= cpu < THRESHOLDS["turbo_to_eco_cpu_pct"]:
                return "ECO"
        return "KEEP"

    # AUTO → no intervenir
    return "KEEP"
