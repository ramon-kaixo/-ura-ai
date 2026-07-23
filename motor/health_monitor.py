"""Health Monitor — alertas automáticas cuando componentes se degradan.

Flujo:
1. Consulta /health del metrics_server cada N segundos
2. Si un componente cambia a degraded/unhealthy, envía alerta
3. Si un componente se recupera, envía recuperación

Uso:
  python3 -m motor.health_monitor                   # una ejecucion
  python3 -m motor.health_monitor --daemon           # bucle cada 60s
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
from typing import Any

log = logging.getLogger("ura.health_monitor")

METRICS_URL = os.environ.get("METRICS_URL", "http://127.0.0.1:9091")
CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "60"))
MEMORY_DB = os.environ.get("URA_MEMORY_DB", str(Path.home() / ".ura" / "memory.db"))
BACKUP_DIR = Path(os.environ.get("URA_BACKUP_DIR", str(Path.home() / ".ura" / "backups")))
BACKUP_INTERVAL = int(os.environ.get("HEALTH_BACKUP_INTERVAL", "3600"))
_PREVIOUS: dict[str, str] = {}
_last_backup: float = 0


def _fetch_health() -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{METRICS_URL}/health", timeout=5) as r:  # nosec  # noqa: S310
            return json.loads(r.read().decode())
    except Exception as e:
        log.warning("Health fetch falló: %s", e)
        return None


def _send_alert(message: str, level: str = "warning") -> bool:
    """Envía alerta via notifier. Fallback silencioso si no está disponible."""
    try:
        from core.notifier import notify

        return notify(message, level=level)  # type: ignore[arg-type]
    except Exception as e:
        log.debug("Notifier no disponible: %s", e)
        return False


def check_and_alert() -> dict[str, Any]:
    """Compara health actual con estado previo. Retorna cambios detectados."""
    global _PREVIOUS  # noqa: PLW0603
    health = _fetch_health()
    if not health:
        return {"status": "error", "detail": "No se pudo obtener health"}

    components = health.get("components", {})
    current: dict[str, str] = {name: c.get("status", "unknown") for name, c in components.items()}
    changes: dict[str, Any] = {"new_degraded": [], "recovered": []}

    for name, status in current.items():
        prev = _PREVIOUS.get(name, "unknown")
        if prev != status:
            if status in ("degraded", "unhealthy"):
                changes["new_degraded"].append(name)
                msg = f"Componente '{name}' → {status}"
                _send_alert(msg, "warning" if status == "degraded" else "critical")
                log.warning("ALERTA: %s", msg)
            elif status == "healthy" and prev in ("degraded", "unhealthy"):
                changes["recovered"].append(name)
                msg = f"Componente '{name}' recuperado → healthy"
                _send_alert(msg, "info")
                log.info("RECUPERACION: %s", msg)

    _PREVIOUS = current
    changes["global"] = health.get("global", "unknown")
    return changes


def _backup_memory() -> None:
    global _last_backup  # noqa: PLW0603
    now = time.time()
    if now - _last_backup < BACKUP_INTERVAL:
        return
    _last_backup = now
    try:
        db = Path(MEMORY_DB)
        if not db.exists():
            return
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"memory_{ts}.db"
        copy2(str(db), str(backup_path))
        log.info("Memoria respaldada: %s (%d bytes)", backup_path.name, backup_path.stat().st_size)
        for old in sorted(BACKUP_DIR.glob("memory_*.db"))[:-14]:
            old.unlink(missing_ok=True)
    except Exception:
        log.debug("Backup falló", exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de salud URA")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle")
    parser.add_argument("--backup", action="store_true", help="Solo backup de memoria")
    args = parser.parse_args()

    if args.backup:
        _backup_memory()
        return

    if args.daemon:
        log.info("Health monitor iniciado (intervalo=%ds)", CHECK_INTERVAL)
        while True:
            check_and_alert()
            _backup_memory()
            time.sleep(CHECK_INTERVAL)
    else:
        result = check_and_alert()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
