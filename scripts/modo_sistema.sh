#!/bin/bash
set -euo pipefail
# modo_sistema.sh — Gestor dinámico de perfiles de hardware
# Controla carga/descarga de modelos según el estado del sistema
# Bloquea a máximo 98 GB para Ollama, reserva 30 GB para el ecosistema

CONTEXT="/opt/ura/data/ura_context.json"
LOG="/opt/ura/logs/modo_sistema.log"
BLOQUEO="/tmp/modo_sistema.lock"
TIMEOUT_INACTIVIDAD=900

MEMORIA_TOTAL=121
MAX_OLLAMA_GB=98
COLCHON_SEGURIDAD_GB=30

mkdir -p "$(dirname "$LOG")" "$(dirname "$CONTEXT")"

exec 200>"$BLOQUEO"
flock -n 200 || { echo "modo_sistema ya en ejecucion" >> "$LOG"; exit 1; }

log() {
    local msg="[$(date +%Y-%m-%dT%H:%M:%S%z)] $1"
    echo "$msg" >> "$LOG"
    echo "$msg"
}

cargar_modelo() {
    local modelo="$1"
    local nombre="${modelo%%:*}"
    if curl -sf http://localhost:11434/api/show -d "{\"model\":\"$modelo\"}" >/dev/null 2>&1; then
        log "Modelo $modelo ya cargado"
        return 0
    fi
    log "Cargando modelo $modelo..."
    curl -s -X POST http://localhost:11434/api/generate \
        -d "{\"model\": \"$modelo\", \"keep_alive\": -1}" >/dev/null 2>&1 &
}

descargar_modelo() {
    local modelo="$1"
    log "Descargando modelo $modelo de memoria..."
    curl -s -X POST http://localhost:11434/api/generate \
        -d "{\"model\": \"$modelo\", \"keep_alive\": 0}" >/dev/null 2>&1
}

purgar_kv_cache() {
    log "Purgando KV-Cache..."
    curl -s -X POST http://localhost:11434/api/generate \
        -d '{"model": "", "keep_alive": 0, "options": {"num_ctx": 0}}' >/dev/null 2>&1
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
}

ultimo_acceso() {
    if [ -f "$CONTEXT" ]; then
        python3 -c "
import json, time
try:
    with open('$CONTEXT') as f:
        ctx = json.load(f)
    ta = ctx.get('opencode_agent', {}).get('ultima_sincronizacion', '')
    if ta:
        import datetime
        ult = datetime.datetime.fromisoformat(ta)
        ahora = datetime.datetime.now(datetime.timezone.utc)
        diff = (ahora - ult).total_seconds()
        print(int(diff))
    else:
        print(9999)
except Exception:
    print(9999)
" 2>/dev/null || echo 9999
    else
        echo 9999
    fi
}

modo_actual() {
    if [ -f "$CONTEXT" ]; then
        python3 -c "
import json
try:
    with open('$CONTEXT') as f:
        ctx = json.load(f)
    print(ctx.get('modo_sistema', 'supervision'))
except Exception:
    print('supervision')
" 2>/dev/null || echo "supervision"
    else
        echo "supervision"
    fi
}

verificar_memoria() {
    local usado_gb
    usado_gb=$(free -b | awk '/Mem:/ {printf "%.0f", ($3+$5)/1024/1024/1024}')
    echo $(( usado_gb ))
}

modo_desarrollo() {
    log ">>> MODO DESARROLLO ACTIVO"
    log "Cargando qwen2.5-coder:32b (FP8 ~35GB) + llama3.2-vision:11b (~8GB)"

    cargar_modelo "qwen2.5-coder:32b"
    cargar_modelo "llama3.2-vision:11b"
    descargar_modelo "qwen2.5:7b"

    python3 -c "
import json
with open('$CONTEXT') as f:
    ctx = json.load(f)
ctx['modo_sistema'] = 'desarrollo'
ctx['memoria']['colchon_30gb_activo'] = True
ctx['memoria']['ollama_max_gb'] = $MAX_OLLAMA_GB
ctx['memoria']['ollama_actual_gb'] = $(verificar_memoria)
ctx['opencode_agent']['tareas_pendientes'] = [t for t in ctx.get('opencode_agent',{}).get('tareas_pendientes',[]) if t]
with open('$CONTEXT', 'w') as f:
    json.dump(ctx, f, indent=2)
" 2>/dev/null || true
}

modo_supervision() {
    log ">>> MODO SUPERVISION PASIVA"

    local usado_antes
    usado_antes=$(verificar_memoria)
    log "Memoria antes de purgar: ${usado_antes}GB"

    purgar_kv_cache
    descargar_modelo "qwen2.5-coder:32b"
    descargar_modelo "qwen2.5-coder:14b"
    descargar_modelo "codestral:22b"
    descargar_modelo "deepseek-coder:6.7b"
    cargar_modelo "qwen2.5:7b"

    sleep 2
    local usado_despues
    usado_despues=$(verificar_memoria)
    log "Memoria despues de purgar: ${usado_despues}GB"
    log "Liberados: $(( usado_antes - usado_despues ))GB"

    python3 -c "
import json
with open('$CONTEXT') as f:
    ctx = json.load(f)
ctx['modo_sistema'] = 'supervision'
ctx['memoria']['colchon_30gb_activo'] = True
ctx['memoria']['ollama_max_gb'] = $MAX_OLLAMA_GB
ctx['memoria']['ollama_actual_gb'] = ${usado_despues}
ctx['memoria']['ultima_purga'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
ctx['memoria']['gb_liberados'] = $(( usado_antes - usado_despues ))
with open('$CONTEXT', 'w') as f:
    json.dump(ctx, f, indent=2)
" 2>/dev/null || true
}

auditar_memoria() {
    local usado_gb
    usado_gb=$(verificar_memoria)

    if [ "$usado_gb" -gt $(( MEMORIA_TOTAL - COLCHON_SEGURIDAD_GB )) ]; then
        log "ALERTA: Memoria usada ${usado_gb}GB > limite seguro $(( MEMORIA_TOTAL - COLCHON_SEGURIDAD_GB ))GB"
        log "Forzando purga de emergencia..."
        purgar_kv_cache
        for m in qwen2.5-coder:32b codestral:22b llama3.3:70b qwen3:32b-q8_0; do
            descargar_modelo "$m"
        done
        cargar_modelo "qwen2.5:7b"
        log "Purga de emergencia completada"
    fi

    log "Memoria actual: ${usado_gb}GB / ${MEMORIA_TOTAL}GB total"
    log "Colchon seguridad: ${COLCHON_SEGURIDAD_GB}GB (libre: $(( MEMORIA_TOTAL - usado_gb ))GB)"
    log "Limite Ollama: ${MAX_OLLAMA_GB}GB"
}

case "${1:-auto}" in
    desarrollo)
        modo_desarrollo
        ;;
    supervision)
        modo_supervision
        ;;
    audit)
        auditar_memoria
        ;;
    auto)
        local diff
        diff=$(ultimo_acceso)
        local modo
        modo=$(modo_actual)

        if [ "$diff" -lt "$TIMEOUT_INACTIVIDAD" ]; then
            if [ "$modo" != "desarrollo" ]; then
                log "Actividad reciente (${diff}s). Cambiando a DESARROLLO..."
                modo_desarrollo
            else
                log "Ya en DESARROLLO. Actividad reciente (${diff}s)."
                auditar_memoria
            fi
        else
            if [ "$modo" != "supervision" ]; then
                log "Inactividad detectada (${diff}s). Cambiando a SUPERVISION..."
                modo_supervision
            else
                log "Ya en SUPERVISION. Inactividad continua (${diff}s)."
            fi
        fi
        ;;
    *)
        echo "Uso: modo_sistema.sh {desarrollo|supervision|audit|auto}"
        exit 1
        ;;
esac
