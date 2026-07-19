import json
import logging
import os
from datetime import UTC
from pathlib import Path

logger = logging.getLogger("ura.state")
STATE_FILE = "/tmp/ura_state.json"  # noqa: S108


def save_checkpoint(task_id: str, target_file: str, content: str, attempt: int = 1) -> None:
    record = {
        "task_id": task_id,
        "target_file": target_file,
        "content": content,
        "attempt": attempt,
        "timestamp": __import__("datetime").datetime.now(UTC).isoformat(),
    }
    try:
        with open(STATE_FILE, "w") as f:  # noqa: PTH123
            json.dump(record, f, ensure_ascii=False)
        logger.info("[STATE] Checkpoint guardado: task=%s file=%s attempt=%d", task_id, target_file, attempt)
    except OSError as e:
        logger.exception("[STATE] No se pudo guardar checkpoint: %s", e)


def load_checkpoint() -> dict | None:
    if not Path(STATE_FILE).exists():
        return None
    try:
        with open(STATE_FILE) as f:  # noqa: PTH123
            record = json.load(f)
        logger.info(
            "[STATE] Checkpoint recuperado: task=%s file=%s attempt=%d",
            record.get("task_id"),
            record.get("target_file"),
            record.get("attempt"),
        )
        return record
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[STATE] Checkpoint corrupto, ignorando: %s", e)
        return None


def clear_checkpoint() -> None:
    if Path(STATE_FILE).exists():
        try:
            os.remove(STATE_FILE)  # noqa: PTH107
            logger.info("[STATE] Checkpoint eliminado")
        except OSError as e:
            logger.exception("[STATE] No se pudo eliminar checkpoint: %s", e)
