#!/bin/bash
# deploy/sandbox_mochila.sh — Build & run Mochila Middleware en Docker sandbox
set -e

REPO="/home/ramon/URA/ura_ia_1972"
IMAGE="ura-mochila"
CONTAINER="sandbox-mochila"

echo "=== Mochila Sandbox ==="

# Build
echo "Building $IMAGE..."
docker build -t "$IMAGE" -f "$REPO/deploy/Dockerfile.mochila" "$REPO"

# Stop & rm old container
docker rm -f "$CONTAINER" 2>/dev/null || true

# Run with host network for Ollama access
echo "Starting $CONTAINER on :4099..."
docker run -d --name "$CONTAINER" \
    --network host \
    -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    -e GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
    -v "$REPO/.nervioso:/workspace/.nervioso" \
    "$IMAGE"

sleep 3

# Smoke test
if curl -s --max-time 5 http://127.0.0.1:4099/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null | grep -q ok; then
    echo "✅ Mochila sandbox healthy on :4099"
else
    echo "❌ Mochila sandbox failed"
    docker logs "$CONTAINER" 2>&1 | tail -10
    exit 1
fi
