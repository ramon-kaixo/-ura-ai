import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.qdrant_client import QdrantClient

log = logging.getLogger("ura.cli")
ARCHIVO_ESTADO = "estado_alemania.json"
ARCHIVO_DIAGNOSTICO = "diagnostico.json"
_executor = SubprocessExecutor()


def cmd_notify(config: UraConfig, args=None) -> None:
    estado_path = Path(config.deploy_dir) / ARCHIVO_ESTADO
    if not estado_path.exists():
        sys.exit(0)
    d = json.loads(estado_path.read_text())
    hs = d.get("health_score", 100)
    inc = 0
    diag_path = Path(config.deploy_dir) / ARCHIVO_DIAGNOSTICO
    if diag_path.exists():
        diag = json.loads(diag_path.read_text())
        inc = len(diag.get("incidentes", []))
    if hs < 95 or inc > 0:
        msg = f"URA alerta: health={hs} incidentes={inc}"
        try:
            _executor.run(
                ["notify-send", "--urgency=critical", "URA", msg],
                timeout=5,
            )
        except FileNotFoundError:
            log.debug("notify-send no disponible")
    else:
        pass


def cmd_qdrant_backup(config: UraConfig, args=None) -> None:
    qdrant = QdrantClient.instancia(config)
    if not qdrant.disponible:
        sys.exit(1)
    incidents = qdrant.buscar_incidentes(limit=1000)
    backup_path = Path(config.deploy_dir) / f"qdrant_backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(
        json.dumps(
            {"incidentes": incidents, "exported_at": datetime.now(UTC).isoformat() + "Z", "total": len(incidents)},
            indent=2,
        ),
    )


def cmd_bench(config: UraConfig = None, args=None) -> None:
    pass
