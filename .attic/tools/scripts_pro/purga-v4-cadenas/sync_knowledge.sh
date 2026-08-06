#!/bin/bash
# /home/ramon/URA/ura_ia_1972/scripts/pro/sync_knowledge.sh
# Pipeline Alemania→Asus: mina metadatos en Hetzner y los indexa localmente.
# Resiliente: si Hetzner esta caido, escribe estado y sale con codigo 2.
set -euo pipefail

HETZNER_HOST="hetzner"
SSH_TIMEOUT=10
METADATA_FILE="/tmp/metadata_raw.json"
STATUS_FILE="/home/ramon/URA/ura_ia_1972/deploy/estado_alemania.json"

cleanup() { rm -f "$METADATA_FILE"; }
trap cleanup EXIT

echo "[SYNC] [1/3] Verificando conexion con Alemania ($HETZNER_HOST)..."
if ! ssh -o ConnectTimeout=$SSH_TIMEOUT "$HETZNER_HOST" "echo OK" 2>/dev/null; then
    NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[SYNC] Hetzner no responde. Escribiendo estado DOWN y abortando."
    sudo chattr -i "$STATUS_FILE" 2>/dev/null || true
    python3 -c "
import json
payload = {
    'ts': '$NOW',
    'global': 'DOWN',
    'ip_publica': '178.105.81.83',
    'ip_tailscale': '100.78.49.106',
    'publica': 'caido',
    'tailscale': 'caido',
    'ssh_port': 2222,
    'detalle': {'error': 'SSH connection refused. Server needs reboot via Hetzner Cloud Console.'}
}
with open('$STATUS_FILE', 'w') as f:
    json.dump(payload, f, indent=2)
"
    sudo chattr +i "$STATUS_FILE" 2>/dev/null || true
    exit 2
fi

echo "[SYNC] [1/3] Minando metadatos deterministas en Alemania..."
ssh -o ConnectTimeout=$SSH_TIMEOUT "$HETZNER_HOST" "python3 /home/ramon/scraping/meta_miner_remote.py /home/ramon/scraping/data"

echo "[SYNC] [2/3] Descargando paquete de metadatos..."
scp -o ConnectTimeout=$SSH_TIMEOUT "$HETZNER_HOST:/tmp/metadata_raw.json" "$METADATA_FILE"

echo "[SYNC] [3/3] Indexando vectores localmente en el Asus..."
python3 -c "
from core.memory_engine import MemoryEngine
me = MemoryEngine()
me.import_remote_metadata_package('$METADATA_FILE')
"

echo "[SYNC] Pipeline finalizado con exito."
