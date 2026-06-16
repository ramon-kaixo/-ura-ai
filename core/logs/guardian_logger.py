import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger("ura.guardian")

GUARDIAN_LOG = os.getenv("GUARDIAN_LOG", "/var/log/ura/guardian.jsonl")


def _ensure_log_dir():
    path = os.path.dirname(GUARDIAN_LOG)
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
