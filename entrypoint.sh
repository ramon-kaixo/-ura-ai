#!/usr/bin/env bash
# URA — Entrypoint script
# Validates config, waits for dependencies, starts URA.
# Handles SIGTERM gracefully.

set -euo pipefail

echo "URA Entrypoint v0.13.0"
echo "======================"

# Configuration
CONFIG_FILE="${URA_CONFIG_FILE:-/app/deploy/system_config.json}"
DATA_DIR="${URA_DATA_DIR:-/data}"
HOST="${URA_HOST:-0.0.0.0}"
PORT="${URA_PORT:-8000}"
OLLAMA_URL="${URA_OLLAMA_URL:-http://localhost:11434}"
QDRANT_URL="${URA_QDRANT_URL:-http://localhost:6333}"
LOG_LEVEL="${URA_LOG_LEVEL:-INFO}"

# 1. Validate configuration
echo "[1/4] Validating configuration..."
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "  WARNING: Config file ${CONFIG_FILE} not found — using defaults"
fi
mkdir -p "${DATA_DIR}"
echo "  Data dir: ${DATA_DIR}"

# 2. Wait for Qdrant
echo "[2/4] Waiting for Qdrant at ${QDRANT_URL}..."
for i in $(seq 1 30); do
    if curl -sf "${QDRANT_URL}/health" > /dev/null 2>&1; then
        echo "  Qdrant ready after ${i}s"
        break
    fi
    if [ "${i}" -eq 30 ]; then
        echo "  WARNING: Qdrant not reachable — continuing without it"
    fi
    sleep 1
done

# 3. Wait for Ollama (optional)
if [ -n "${OLLAMA_URL}" ]; then
    echo "[3/4] Checking Ollama at ${OLLAMA_URL}..."
    for i in $(seq 1 10); do
        if curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
            echo "  Ollama ready after ${i}s"
            break
        fi
        if [ "${i}" -eq 10 ]; then
            echo "  WARNING: Ollama not reachable — continuing without it"
        fi
        sleep 2
    done
fi

# 4. Start URA
echo "[4/4] Starting URA on ${HOST}:${PORT}..."
cleanup() {
    echo "  Received SIGTERM — shutting down..."
    exit 0
}
trap cleanup SIGTERM SIGINT

exec python3 -m uvicorn motor.observability.http:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --log-level "${LOG_LEVEL,,}" \
    --timeout-keep-alive 30
