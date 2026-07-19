#!/bin/bash
# ============================================================
# install_opencode_mac.sh — Instalación limpia de OpenCode CLI v2 (lildax)
# REGLA DE ORO: Todo se ejecuta dentro del proyecto URA de mejora continua
# ============================================================
set -e

URA_DIR="${URA_ROOT:-/Users/ramonesnaola/URA}/ura_ia_1972"
CONFIG_FILE="$URA_DIR/deploy/lildax_config.json"
LILDAX_CONFIG_DIR="$HOME/Library/Application Support/lildax"
LOG_FILE="$URA_DIR/logs/opencode_mac_install.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
    echo "$1"
}

log "=== INSTALACIÓN OPENCODE CLI v2 (lildax) - MAC ==="

# 1. Verificar que estamos en la carpeta correcta
if [ ! -d "$URA_DIR" ]; then
    log "ERROR: Directorio URA no encontrado: $URA_DIR"
    exit 1
fi

log "✅ Directorio URA verificado: $URA_DIR"

# 2. Instalar OpenCode CLI v2 via npm
log "Instalando @opencode-ai/cli via npm..."
npm install -g @opencode-ai/cli >> "$LOG_FILE" 2>&1
log "✅ OpenCode CLI instalado"

# 3. Crear directorio de configuración
log "Creando directorio de configuración lildax..."
mkdir -p "$LILDAX_CONFIG_DIR"
log "✅ Directorio creado: $LILDAX_CONFIG_DIR"

# 4. Copiar configuración desde el proyecto
log "Copiando configuración desde proyecto..."
cp "$CONFIG_FILE" "$LILDAX_CONFIG_DIR/config.json"
log "✅ Configuración copiada"

# 5. Establecer contraseña del servicio
LILDAX_PASSWORD="${LILDAX_PASSWORD:-ura_1972_secure_autonomous}"
log "Estableciendo contraseña del servicio..."
/opt/homebrew/lib/node_modules/@opencode-ai/cli/bin/lildax service password "$LILDAX_PASSWORD" >> "$LOG_FILE" 2>&1
log "✅ Contraseña establecida"

# 6. Iniciar servicio lildax
log "Iniciando servicio lildax en puerto 4096..."
/opt/homebrew/lib/node_modules/@opencode-ai/cli/bin/lildax service start >> "$LOG_FILE" 2>&1
log "✅ Servicio iniciado"

# 7. Verificar estado
log "Verificando estado del servicio..."
/opt/homebrew/lib/node_modules/@opencode-ai/cli/bin/lildax service status >> "$LOG_FILE" 2>&1
log "✅ Servicio verificado"

log "=== INSTALACIÓN COMPLETADA ==="
log "Interfaz web: http://127.0.0.1:4096"
log "Servidor remoto: http://${ASUS_HOST:-10.164.1.99}:8081"
log "Workspace local: $URA_DIR"
