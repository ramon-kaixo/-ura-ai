#!/bin/bash
# /home/ramon/URA/ura_ia_1972/scripts/pro/sync_knowledge.sh
set -e
trap 'rm -f /tmp/metadata_raw.json' EXIT

echo "[SYNC] [1/3] Minando metadatos deterministas en Alemania..."
ssh -o ConnectTimeout=10 hetzner "python3 /home/ramon/scraping/meta_miner_remote.py /home/ramon/scraping/data"

echo "[SYNC] [2/3] Descargando paquete de metadatos vía Tailscale..."
scp -o ConnectTimeout=10 hetzner:/tmp/metadata_raw.json /tmp/metadata_raw.json

echo "[SYNC] [3/3] Indexando vectores localmente en el Asus (Ollama GPU)..."
python3 -c "
from core.memory_engine import MemoryEngine
me = MemoryEngine()
me.import_remote_metadata_package('/tmp/metadata_raw.json')
"
echo "[SYNC] Pipeline finalizado con éxito. Temporales purgados."
