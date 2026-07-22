"""Guardian logger — eventos de servicio persistidos a Qdrant."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import IConfigProvider

logger = logging.getLogger("ura.guardian")

GUARDIAN_LOG = os.getenv("GUARDIAN_LOG", "/var/log/ura/guardian.jsonl")


def _ensure_log_dir():
    path = Path(GUARDIAN_LOG).parent
    if path and not Path(path).exists():
        os.makedirs(path, exist_ok=True)


def _publish_to_event_bus(record: dict) -> None:
    try:
        from core.event_bus import publish
        publish("alert", {"source": "guardian", "event": record.get("event"), "reason": record.get("reason", "")[:200], "result_type": record.get("result_type", "")})
    except Exception:
        pass


def _save_to_qdrant(record: dict, config: IConfigProvider | None = None) -> None:
    try:
        if config is None:
            from motor.core.config import UraConfig
            from motor.core.qdrant_client import instancia

            config = UraConfig()
            qc = instancia(config)
        else:
            from motor.core.qdrant_client import instancia

            qc = instancia(config)
        if qc and qc.disponible:
            subtipo = record.get("event", "unknown").replace("_", " ").title().replace(" ", "")
            qc.guardar_incidente({
                "ts": record.get("timestamp", datetime.now(UTC).isoformat()),
                "tipo": "ServiceFailure",
                "subtipo": subtipo[:50],
                "resumen": f"{record.get('event')}: {record.get('reason', '')[:200]}",
                "pre_state": {"attempts": record.get("attempts", 0), "complexity": record.get("complexity", 0)},
                "origin_node": "ASUS",
                "exit_code": -1,
            })
    except Exception:
        pass


def log_event(
    event: str,
    model: str = "",
    file: str = "",
    reason: str = "",
    attempts: int = 0,
    penalty: str = "",
    sandbox_errors: list[str] | None = None,
    complexity: int = 0,
    temperature: float = 0.0,
    result_type: str = "",
):
    _ensure_log_dir()
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "model": model,
        "file": file,
        "reason": reason,
        "attempts": attempts,
        "penalty": penalty[:120] if penalty else "",
        "sandbox_errors": sandbox_errors or [],
        "complexity": complexity,
        "temperature": temperature,
        "result_type": result_type,
    }
    line = json.dumps(record, ensure_ascii=False)
    logger.info("GUARDIAN_EVENT: %s", line)
    try:
        with open(GUARDIAN_LOG, "a") as f:
            f.write(line + "\n")
    except OSError as e:
        logger.error("No se pudo escribir %s: %s", GUARDIAN_LOG, e)
    if result_type in ("failure", "warning") or attempts >= 3:
        _publish_to_event_bus(record)
        if result_type == "failure":
            _save_to_qdrant(record)
