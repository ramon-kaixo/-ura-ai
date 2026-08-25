import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.core.config import UraConfig

log = logging.getLogger("ura.diagnostico.backup")


def backup_incidente(config: UraConfig, incidente: dict[str, Any] | None = None) -> str:
    """Guarda backup de un incidente a disco."""
    dest_dir = Path(config.data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    data: dict[str, object] = {"timestamp": datetime.now(UTC).isoformat() + "Z"}
    if incidente:
        data["incidente"] = incidente
    try:
        dest.write_text(json.dumps(data, indent=2))
        log.info("backup metadata en %s", dest)
        return str(dest)
    except (OSError, TypeError) as e:
        log.exception("error backup: %s", e)
        return ""
