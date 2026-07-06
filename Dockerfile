# URA — Multi-agent desktop assistant
#
# Build:  docker build -t ura .
# Run:    docker run -p 8000:8000 ura
#
# Multi-stage: stage 1 installs deps, stage 2 is runtime image.

# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY --link requirements.txt pyproject.toml ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt 2>/dev/null || true && \
    pip install --no-cache-dir uvicorn httpx pyyaml fastapi pydantic

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="URA"
LABEL org.opencontainers.image.description="Multi-agent desktop assistant"
LABEL org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN groupadd -r ura && useradd -r -g ura -d /home/ura -s /sbin/nologin ura && \
    mkdir -p /home/ura /data /app && \
    chown -R ura:ura /home/ura /data /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY --chown=ura:ura . .

# Default environment
ENV URA_CONFIG_FILE=/app/deploy/system_config.json \
    URA_LOG_LEVEL=INFO \
    URA_HOST=0.0.0.0 \
    URA_PORT=8000 \
    URA_OLLAMA_URL=http://localhost:11434 \
    URA_QDRANT_URL=http://localhost:6333 \
    URA_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

USER ura

ENTRYPOINT ["/app/entrypoint.sh"]
