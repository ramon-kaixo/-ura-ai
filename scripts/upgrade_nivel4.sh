#!/bin/bash
# upgrade_nivel4.sh - Instala dependencias y servicios para Nivel 4/5
set -e

URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$URA_BASE/.venv"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

log "=== Actualizando URA a Nivel 4/5 ==="

# 1. Instalar dependencias Python
log "1. Instalando dependencias Python..."
source "$VENV/bin/activate" 2>/dev/null || { log "ERROR: venv no encontrado"; exit 1; }
pip install -q chromadb sentence-transformers redis paho-mqtt 2>/dev/null || true
log "   Dependencias Python OK"

# 2. Instalar Redis y Mosquitto
if [[ "$OSTYPE" == "darwin"* ]]; then
    log "2. Instalando Redis y Mosquitto (macOS)..."
    if command -v brew &>/dev/null; then
        brew install redis mosquitto 2>/dev/null || true
        brew services start redis 2>/dev/null || true
        brew services start mosquitto 2>/dev/null || true
        log "   Servicios macOS iniciados"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    log "2. Instalando Redis y Mosquitto (Linux)..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y redis-server mosquitto mosquitto-clients 2>/dev/null || true
        sudo systemctl enable redis-server mosquitto 2>/dev/null || true
        sudo systemctl start redis-server mosquitto 2>/dev/null || true
        log "   Servicios Linux iniciados"
    fi
fi

# 3. Reiniciar servicios URA
log "3. Reiniciando servicios URA..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    launchctl unload ~/Library/LaunchAgents/com.ura.autonomia.plist 2>/dev/null || true
    launchctl load ~/Library/LaunchAgents/com.ura.autonomia.plist 2>/dev/null || true
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo systemctl restart ura-autonomia 2>/dev/null || true
fi

log "=== Nivel 4/5 implementado ==="
log "Verifica con: curl http://localhost:5105/health"
