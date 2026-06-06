#!/usr/bin/env python3
"""telemetry_sink.py — Persistencia de telemetría en JSON Lines con rotación diaria.

Exporta el estado del sistema a logs/telemetry/YYYY-MM-DD.jsonl.
Cada línea es un snapshot JSON con timestamp, modo, CPU, latencia, etc.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("telemetry")

TELEMETRY_DIR = Path(__file__).parent.parent / "logs" / "telemetry"


def _ensure_dir() -> None:
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)


def _today_path() -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return TELEMETRY_DIR / f"{date_str}.jsonl"


def write_snapshot(
    *,
    mode: str = "?",
    cpu_pct: float = -1.0,
    mem_pct: float = -1.0,
    latency_ms: float = -1.0,
    models_available: int = 0,
    backend_label: str = "?",
    fallback_count_1h: int = 0,
    active_coroutines: int = 0,
    total_coroutines: int = 0,
    orchestrator_status: str = "?",
    orchestrator_reason: str = "",
    router_ok: bool = False,
    lan_reachable: bool = False,
    state_backend: str = "?",
) -> None:
    """Escribe un snapshot en el archivo JSON Lines del día.

    Fails silently — nunca lanza excepciones hacia el event loop.
    """
    try:
        _ensure_dir()
        path = _today_path()
        snapshot = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": mode,
            "cpu_pct": cpu_pct,
            "mem_pct": mem_pct,
            "latency_ms": latency_ms,
            "models_available": models_available,
            "backend_label": backend_label,
            "fallback_count_1h": fallback_count_1h,
            "active_coroutines": active_coroutines,
            "total_coroutines": total_coroutines,
            "orchestrator_status": orchestrator_status,
            "orchestrator_reason": orchestrator_reason,
            "router_ok": router_ok,
            "lan_reachable": lan_reachable,
            "state_backend": state_backend,
        }
        with open(path, "a") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("telemetry write falló silenciosamente: %s", e)
