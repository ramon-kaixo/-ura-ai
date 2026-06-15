import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from core.config import RUTAS_CONFIG_OPENCODE, UraConfig
from core.state import PreflightResult

log = logging.getLogger("ura.guard.preflight")

def ejecutar_preflight(config: UraConfig) -> PreflightResult:
    """Ejecuta verificación prevuelo: detecta duplicados y toma snapshot."""
    r = PreflightResult()
    snap = {"timestamp": datetime.utcnow().isoformat()+"Z"}
    dups = _detectar_configs_duplicadas()
    if dups:
        r.ok = False
        r.bloqueado = True
        r.razon = f"Configs duplicadas: {dups}"
        r.configs_duplicadas = dups
        log.warning("BLOQUEO: %s", r.razon)
    snap["configs"] = _snapshot_configs()
    snap["procesos"] = _snapshot_procesos()
    snaps_dir = Path(config.data_dir) / "snapshots"
    snaps_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snaps_dir / f"preflight_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    snap_path.write_text(json.dumps(snap, indent=2))
    r.snapshot_path = str(snap_path)
    log.info("preflight ok, snapshot en %s", snap_path)
    return r

def _detectar_configs_duplicadas() -> list:
    """Detecta si hay múltiples archivos de configuración de opencode."""
    existentes = [p for p in RUTAS_CONFIG_OPENCODE if Path(p).exists()]
    return existentes if len(existentes) > 1 else []

def _snapshot_configs() -> dict:
    """Toma hash y tamaño de los archivos de configuración."""
    snap = {}
    for p in RUTAS_CONFIG_OPENCODE:
        f = Path(p)
        if f.exists():
            snap[p] = {"hash": hashlib.sha256(f.read_bytes()).hexdigest()[:16], "size": f.stat().st_size}
    return snap

def _snapshot_procesos() -> list:
    """Snapshot de los primeros 30 procesos del sistema."""
    try:
        r = subprocess.run(["ps", "-eo", "pid,comm", "--no-headers"], capture_output=True, text=True, timeout=3)
        return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()][:30]
    except Exception as e:
        log.debug("snapshot procesos falló: %s", e)
        return []
