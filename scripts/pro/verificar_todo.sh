#!/usr/bin/env bash
# verificar_todo.sh [TASK-ID] — Orquestador declarativo de gates (lee gates.json).
# Uso:
#   scripts/pro/verificar_todo.sh             # gates que no requieren TASK
#   scripts/pro/verificar_todo.sh TASK-XXXX   # + gate UDO verify
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"
TASK="${1:-}"

python3 - "$TASK" <<'PY'
import json, subprocess, sys

task = sys.argv[1] if len(sys.argv) > 1 else ""
data = json.load(open("scripts/pro/gates.json"))
fails = []
skips = []

for g in data["gates"]:
    if g.get("needs_task") and not task:
        skips.append(g["id"])
        print(f"SKIP {g['id']} (sin TASK-ID)")
        continue
    cmd = g["cmd"].replace("{TASK}", task)
    print(f"==> {g['id']}: {g['desc']}")
    r = subprocess.run(cmd, shell=True)
    if r.returncode != 0:
        fails.append(g["id"])
        print(f"    ❌ FALLO {g['id']}")

if fails:
    print(f"GATES FALLIDOS: {', '.join(fails)}")
    sys.exit(1)
if skips:
    print(f"SKIPPED: {', '.join(skips)}")
print("✅ todos los gates pasaron")
PY
