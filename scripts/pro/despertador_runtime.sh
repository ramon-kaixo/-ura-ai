#!/usr/bin/env bash
# despertador_runtime.sh — Actualiza solo coordination.runtime.json (runtime metadata)
# No toca coordination.json (manual UDO data)
# Ejecutado por systemd timer cada 5 min

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

RUNTIME_FILE="docs/udo/coordination.runtime.json"

# Ejecutar dispatcher.py solo si hay agentes libres y tareas pendientes
python3 scripts/pro/dispatcher.py >"$(mktemp)" 2>&1 || true

# Registrar timestamp de la última ejecución SOLO en runtime file
python3 - "$RUNTIME_FILE" <<'PY'
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

coord_path = Path(sys.argv[1])
lock_path = coord_path.with_suffix(".lock")

with lock_path.open("w", encoding="utf-8") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    # Cargar existente o crear nuevo
    if coord_path.exists():
        with coord_path.open(encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"ultima_ejecucion_despertador": ""}
    
    data["ultima_ejecucion_despertador"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    tmp = coord_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(coord_path)
PY

echo "Despertador runtime ejecutado. Timestamp en $RUNTIME_FILE"
