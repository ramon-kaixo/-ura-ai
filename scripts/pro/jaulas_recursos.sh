#!/bin/bash
# jaulas_recursos.sh — Despliegue idempotente de límites de recursos.
# Sin color, sin emoji, sin adornos. Ejecutar como root.
# Uso: sudo bash scripts/pro/jaulas_recursos.sh

set -euo pipefail
LOG="/var/log/ura-jaulas.log"

log() { echo "$(date +%Y-%m-%dT%H:%M:%S) $*" | tee -a "$LOG"; }

log "=== Jaulas de Recursos — inicio ==="

# === 1. OOM Score ===
set_oom() {
    local name=$1 score=$2
    local pid
    pid=$(pgrep -x "$name" 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        echo "$score" > "/proc/$pid/oom_score_adj" 2>/dev/null || true
        log "  oom $name=$score (pid $pid)"
    fi
}
set_oom ollama -1000
set_oom ura-executor 500
# qdrant corre en docker, su OOM se maneja via --memory

# === 2. systemd drop-in para ura-executor ===
mkdir -p /etc/systemd/system/ura-executor.service.d
cat > /etc/systemd/system/ura-executor.service.d/recursos.conf << 'EOF'
[Service]
MemoryMax=1G
CPUWeight=50
MemoryHigh=768M
IOWeight=25
EOF
log "  drop-in ura-executor: MemoryMax=1G CPUWeight=50"

# === 3. Servicio systemd para Qdrant ===
cat > /etc/systemd/system/qdrant.service << 'EOF'
[Unit]
Description=Qdrant Vector Database
After=docker.service
Requires=docker.service
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
ExecStartPre=-/usr/bin/docker rm -f qdrant
ExecStart=/usr/bin/docker run --rm --name qdrant \
  --memory=2g --memory-reservation=1g \
  --cpus=1.0 --cpuset-cpus=0 \
  -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
ExecStop=/usr/bin/docker stop qdrant
Restart=always
RestartSec=5
MemoryMax=2G

[Install]
WantedBy=multi-user.target
EOF
log "  qdrant.service: --memory=2g --cpus=1.0"

# === 4. sysctl tuning ===
cat > /etc/sysctl.d/99-ura-tuning.conf << 'EOF'
vm.swappiness=10
vm.dirty_ratio=10
vm.dirty_background_ratio=5
EOF
sysctl --system >/dev/null 2>&1 || true
log "  sysctl: swappiness=10 dirty_ratio=10"

# === 5. Recargar systemd ===
systemctl daemon-reload
log "  systemctl daemon-reload"

log "=== Jaulas de Recursos — completado ==="
