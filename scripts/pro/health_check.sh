#!/bin/bash
# health_check.sh — Health check unificado para servicios URA
# Uso: ./health_check.sh [service_name]
#   Sin args: checkea todos los servicios URA
#   Con args: checkea solo el servicio indicado

set -euo pipefail

LOG="/tmp/ura_health_check.log"
: > "$LOG"

# Mapa de servicios → endpoint de salud
declare -A HEALTH_ENDPOINTS=(
    ["ura-openclaw"]="http://127.0.0.1:18789/health"
    ["ura-ejecutor"]="http://127.0.0.1:4096/health"
    ["model-router"]="http://127.0.0.1:11435/health"
    ["ura-mkdocs"]="http://127.0.0.1:8088/health"
    ["ura-contraste"]="http://127.0.0.1:8002/health"
    ["ollama"]="http://127.0.0.1:11434/api/tags"
    ["ura-qdrant"]="http://127.0.0.1:6333/collections"
    ["ura-prometheus"]="http://127.0.0.1:9090/-/ready"
)

check_service() {
    local svc="$1"
    local endpoint="${HEALTH_ENDPOINTS[$svc]:-}"
    
    # 1. Check systemd status
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "[OK]  $svc (systemd active)" >> "$LOG"
    else
        echo "[FAIL] $svc (systemd inactive)" >> "$LOG"
        return 1
    fi
    
    # 2. HTTP health check (if endpoint defined)
    if [ -n "$endpoint" ]; then
        if curl -sf --max-time 3 "$endpoint" > /dev/null 2>&1; then
            echo "[OK]  $svc (HTTP $endpoint)" >> "$LOG"
        else
            echo "[FAIL] $svc (HTTP $endpoint unreachable)" >> "$LOG"
            return 1
        fi
    fi
    
    return 0
}

# Modo: checkear un servicio específico
if [ $# -ge 1 ]; then
    check_service "$1"
    exit $?
fi

# Modo: checkear todos
failed=0
total=0

echo "=== URA Health Check $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"

for svc in "${!HEALTH_ENDPOINTS[@]}"; do
    total=$((total + 1))
    if ! check_service "$svc"; then
        failed=$((failed + 1))
    fi
done

echo "" >> "$LOG"
echo "Resultado: $failed/$total servicios con fallo" >> "$LOG"

if [ $failed -gt 0 ]; then
    cat "$LOG"
    exit 1
fi

echo "Todos los servicios OK ($total)"
exit 0
