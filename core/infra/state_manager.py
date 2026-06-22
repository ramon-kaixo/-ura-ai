from datetime import UTC
import json
import os
import logging

logger = logging.getLogger("ura.state")
STATE_FILE = "/tmp/ura_state.json"


def save_checkpoint(task_id: str, target_file: str, content: str, attempt: int = 1):
    record = {
        "task_id": task_id,
        "target_file": target_file,
        "content": content,
        "attempt": attempt,
        "timestamp": __import__("datetime").datetime.now(UTC).isoformat(),
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(record, f, ensure_ascii=False)
        logger.info("[STATE] Checkpoint guardado: task=%s file=%s attempt=%d", task_id, target_file, attempt)
    except OSError as e:
        logger.error("[STATE] No se pudo guardar checkpoint: %s", e)


def load_checkpoint() -> dict | None:
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE) as f:
            record = json.load(f)
        logger.info("[STATE] Checkpoint recuperado: task=%s file=%s attempt=%d",
                     record.get("task_id"), record.get("target_file"), record.get("attempt"))
        return record
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[STATE] Checkpoint corrupto, ignorando: %s", e)
        return None


def clear_checkpoint():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            logger.info("[STATE] Checkpoint eliminado")
        except OSError as e:
            logger.error("[STATE] No se pudo eliminar checkpoint: %s", e)
