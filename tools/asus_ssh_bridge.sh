#!/bin/bash
###############################################################################
# Script de reconexión automática del puente SSH Mac M4 ↔ ASUS GX10
# Mantiene la conexión estable y verifica disponibilidad de Ollama
###############################################################################

set -e

# Configuración
ASUS_HOST="192.168.1.135"
ASUS_USER="ramon"
OLLAMA_PORT=11434
CHECK_INTERVAL=30  # segundos entre verificaciones
LOG_FILE="/Users/ramonesnaola/URA/ura_ia_1972/logs/asus_bridge.log"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Crear directorio de logs si no existe
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_ssh() {
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${ASUS_USER}@${ASUS_HOST}" "echo 'SSH OK'" > /dev/null 2>&1
    return $?
}

check_ollama() {
    nc -z -w 3 "$ASUS_HOST" "$OLLAMA_PORT" > /dev/null 2>&1
    return $?
}

restart_ollama() {
    log "${YELLOW}Intentando reiniciar Ollama en ASUS...${NC}"
    ssh "${ASUS_USER}@${ASUS_HOST}" "systemctl restart ollama" >> "$LOG_FILE" 2>&1
    sleep 5
}

log "${CYAN}══════════════════════════════════════════════════════════════${NC}"
log "${CYAN}  PUENTE SSH MAC M4 ↔ ASUS GX10 INICIADO${NC}"
log "${CYAN}══════════════════════════════════════════════════════════════${NC}"
log "ASUS: ${ASUS_USER}@${ASUS_HOST}"
log "Ollama: ${ASUS_HOST}:${OLLAMA_PORT}"
log "Intervalo: ${CHECK_INTERVAL}s"
log ""

while true; do
    # Verificar SSH
    if check_ssh; then
        log "${GREEN}✅ SSH: Conectado${NC}"
        
        # Verificar Ollama
        if check_ollama; then
            log "${GREEN}✅ Ollama: Accesible${NC}"
        else
            log "${RED}❌ Ollama: No accesible${NC}"
            restart_ollama
            if check_ollama; then
                log "${GREEN}✅ Ollama: Recuperado${NC}"
            else
                log "${RED}❌ Ollama: No se pudo recuperar${NC}"
            fi
        fi
    else
        log "${RED}❌ SSH: No conectado${NC}"
        log "${YELLOW}Esperando ${CHECK_INTERVAL}s antes de reintentar...${NC}"
    fi
    
    log ""
    sleep "$CHECK_INTERVAL"
done
