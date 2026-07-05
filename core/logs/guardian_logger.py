import json
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger("ura.guardian")

GUARDIAN_LOG = os.getenv("GUARDIAN_LOG", "/var/log/ura/guardian.jsonl")


def _ensure_log_dir():
    path = os.path.dirname(GUARDIAN_LOG)
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _publish_to_event_bus(record: dict) -> None:
    try:
        from core.event_bus import publish
        publish("alert", {"source": "guardian", "event": record.get("event"), "reason": record.get("reason", "")[:200], "result_type": record.get("result_type", "")})
    except Exception:
        pass  # noqa: S110


def _save_to_qdrant(record: dict) -> None:
    try:
        from motor.core.config import UraConfig
        from motor.core.qdrant_client import instancia
        cfg = UraConfig()
        qc = instancia(cfg)
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
        pass  # noqa: S110


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
