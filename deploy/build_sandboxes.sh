#!/bin/bash
# build_sandboxes.sh — Construir y arrancar todos los sandboxes URA
set -euo pipefail

SANDBOX_DIR="/home/ramon/URA/ura_ia_1972/deploy/docker/sandbox"

echo "[SANDBOX] Construyendo contenedores de sandbox..."

for dir in "$SANDBOX_DIR"/*/; do
    name=$(basename "$dir")
    image="ura-sandbox-$(echo "$name" | tr '[:upper:]' '[:lower:]')"
    echo "  -> Construyendo $image desde $dir"
    docker build -t "$image:latest" -f "${dir}Dockerfile" "$dir" 2>&1 | tail -3
done

# Also build the coding-agent sandbox
echo "  -> Construyendo ura-coding-agent-sandbox"
docker build -t "ura-coding-agent-sandbox:latest" \
    -f "/home/ramon/URA/ura_ia_1972/agents/sandbox/Dockerfile" \
    "/home/ramon/URA/ura_ia_1972/agents/sandbox/" 2>&1 | tail -3

echo ""
echo "[SANDBOX] Todas las imágenes construidas."
echo "Imágenes disponibles:"
docker images --format "{{.Repository}}" | grep "ura-sandbox" | sort
