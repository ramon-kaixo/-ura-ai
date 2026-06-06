#!/usr/bin/env bash
# ============================================================
# GX10 Bootstrap — Reconstruye todo desde cero.
# Idempotente: ejecutar 10 veces = mismo resultado.
# USO: bash deploy/gx10_bootstrap.sh
# ============================================================
set -e

log() { echo "[BOOTSTRAP] $(date): $1"; }
check() { if command -v "$1" > /dev/null 2>&1; then echo "  ✓ $1"; else echo "  ✗ $1 — instalando..."; return 1; fi; }

REPO_URL="${1:-git@github.com:ramon/ura_ia_1972.git}"
REPO_DIR="/home/ramon/URA/ura_ia_1972"
OLLAMA_HOST="127.0.0.1"

log "=== Fase 1: Dependencias ==="
check python3 || sudo apt-get install -y python3 python3-pip
check docker   || (curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker ramon)
check git      || sudo apt-get install -y git

log "=== Fase 2: Repositorio ==="
if [ -d "$REPO_DIR/.git" ]; then
    cd "$REPO_DIR" && git pull origin main
else
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

log "=== Fase 3: Ollama ==="
if ! systemctl is-active ollama > /dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
    sudo sed -i 's/Environment="OLLAMA_HOST=.*/Environment="OLLAMA_HOST=127.0.0.1"/' /etc/systemd/system/ollama.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now ollama
fi

log "=== Fase 4: Docker Compose ==="
docker compose version > /dev/null 2>&1 || sudo apt-get install -y docker-compose-plugin

log "=== Fase 5: Contenedores ==="
cd "$REPO_DIR/deploy"
docker compose --profile core up -d
docker compose --profile sandbox up -d
docker compose --profile monitoring up -d

log "=== Fase 6: SNC ==="
sudo cp "$REPO_DIR/deploy/snc.service" /etc/systemd/system/
sudo cp "$REPO_DIR/deploy/snc.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snc.timer
sudo systemctl enable --now snc.service

log "=== Fase 7: Rotación de logs ==="
sudo cp "$REPO_DIR/deploy/rotate_logs.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rotate_logs.timer

log "=== Fase 8: Firewall ==="
sudo ufw default deny incoming
sudo ufw allow from 10.164.1.0/24
sudo ufw --force enable

log "=== Fase 9: Verificación ==="
echo ""
echo "  Ollama:    $(systemctl is-active ollama)"
echo "  SNC:       $(systemctl is-active snc)"
echo "  Docker:    $(docker ps --format '{{.Names}}' | wc -l) contenedores"
echo "  Tests:     $(python3 tests/test_unit.py 2>&1 | tail -1)"
echo ""
log "✅ Bootstrap completado. GX10 operativo."
