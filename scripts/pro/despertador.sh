#!/usr/bin/env bash
# despertador.sh — Despertador del auto-dispatcher.
# Ejecuta dispatcher.py cuando hay agentes libres y tareas pendientes,
# y registra la última ejecución en docs/udo/coordination.json.
# Uso: bash scripts/pro/despertador.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

COORD="docs/udo/coordination.json"

# Ejecutar dispatcher.py solo si hay agentes libres y tareas pendientes.
# dispatcher.py ya implementa flock y verifica conflictos de zonas.
python3 scripts/pro/dispatcher.py >"$(mktemp)" 2>&1 || true

# Registrar timestamp de la última ejecución, protegido con flock.
python3 - "$COORD" <<'PY'
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

coord_path = Path(sys.argv[1])
lock_path = coord_path.with_suffix(".lock")

with lock_path.open("w", encoding="utf-8") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    with coord_path.open(encoding="utf-8") as f:
        data = json.load(f)

    data["ultima_ejecucion_despertador"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    tmp = coord_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(coord_path)
PY

echo "Despertador ejecutado. Última ejecución registrada en $COORD."
