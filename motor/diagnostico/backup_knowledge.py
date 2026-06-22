import json
import logging
from pathlib import Path
from datetime import UTC, datetime

log = logging.getLogger("ura.diagnostico.backup")

def backup_incidente(config, incidente: dict = None) -> str:
    """Guarda backup de un incidente a disco."""
    dest = Path(config.data_dir) / f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    data = {"timestamp": datetime.now(UTC).isoformat()+"Z"}
    if incidente:
        data["incidente"] = incidente
    try:
        dest.write_text(json.dumps(data, indent=2))
        log.info("backup metadata en %s", dest)
        return str(dest)
    except (OSError, json.JSONEncodeError) as e:
        log.error("error backup: %s", e)
        return ""
