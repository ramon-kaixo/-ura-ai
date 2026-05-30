#!/bin/bash
set -euo pipefail
apt-get update && apt-get install -y python3.12-venv docker.io 2>/dev/null || true
cd /workspace
python3 -m venv .venv 2>/dev/null
source .venv/bin/activate
pip install -r requirements.txt 2>/dev/null
docker compose -f docker-compose.sandbox.yml up -d 2>/dev/null || true
echo "✅ Setup cloud completado"
