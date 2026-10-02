#!/bin/bash
# check_mac_ssh.sh — Health-check SSH al Mac desde GX10 (mejora auditoría 2026-08-28).
# La auditoría industrial marcó el Mac como "degraded" por no poder SSH; el check
# real es: probar SSH con el alias mac-mini-ramon (usuario ramonesnaola + clave
# id_gx10_mac) y reportar estado. Reversible, read-only.
#
# Uso:
#   check_mac_ssh.sh            # exit 0 = OK, 1 = fallo
#   check_mac_ssh.sh --registry # además actualiza .ura/node_registry.json (mac online/degraded)
set -u

MAC_ALIAS="${MAC_ALIAS:-mac-mini-ramon}"
REGISTRY="${URA_REPO:-/home/ramon/URA/ura_ia_1972}/.ura/node_registry.json"

if ! command -v ssh >/dev/null 2>&1; then
	echo "ERROR: ssh no disponible"
	exit 1
fi

if timeout 15 ssh -o BatchMode=yes "$MAC_ALIAS" "hostname" >/dev/null 2>&1; then
	echo "OK: SSH al Mac ($MAC_ALIAS) funciona"
	ST=online
	RC=0
else
	echo "FAIL: SSH al Mac ($MAC_ALIAS) denegado/inaccesible"
	ST=degraded
	RC=1
fi

if [ "${1:-}" = "--registry" ] && [ -f "$REGISTRY" ]; then
	python3 - "$ST" <<'PY'
import json, sys, time
from pathlib import Path
st = sys.argv[1]
p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/home/ramon/URA/ura_ia_1972/.ura/node_registry.json")
try:
    d = json.loads(p.read_text())
except Exception:
    sys.exit(0)  # no tocar si el registry es ilegible
mac = d.get("nodes", {}).get("mac")
if mac:
    mac["status"] = st
    mac["last_seen"] = time.time()
    mac["consecutive_failures"] = 0 if st == "online" else (mac.get("consecutive_failures", 0) + 1)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    print(f"registry mac → {st}")
PY
fi

exit "$RC"
