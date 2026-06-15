import json, logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("ura.diagnostico.backup")

def backup_qdrant(config) -> str:
    dest = Path(config.data_dir) / f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    data = {"timestamp": datetime.utcnow().isoformat()+"Z"}
    try:
        dest.write_text(json.dumps(data, indent=2))
        log.info("backup metadata en %s", dest)
        return str(dest)
    except Exception as e:
        log.error("error backup: %s", e)
        return ""
