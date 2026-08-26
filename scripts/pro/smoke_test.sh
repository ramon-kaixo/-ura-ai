#!/usr/bin/env bash
# smoke_test.sh — Smoke tests rapidos del sistema URA
# Ejecutar: ./scripts/pro/smoke_test.sh
# Requiere: curl, jq (opcional), systemctl (GX10)

set -euo pipefail

GX10_TS="100.72.103.12"
MAC_TS="100.72.103.7"
ERRORS=0

log() { echo "[$(date '+%H:%M:%S')] $*"; }
pass() { log "OK: $*"; }
fail() { log "FAIL: $*"; ERRORS=$((ERRORS + 1)); }

# --- OpenCode ---
log "Verificando OpenCode..."
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/ 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "401" || "$HTTP_CODE" == "403" ]]; then
    pass "OpenCode responde (HTTP $HTTP_CODE)"
else
    fail "OpenCode no responde (HTTP $HTTP_CODE)"
fi

# --- Ollama ---
log "Verificando Ollama..."
MODELS=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "0")
if [[ "$MODELS" -gt 0 ]]; then
    pass "Ollama tiene $MODELS modelos"
else
    fail "Ollama sin modelos o no disponible"
fi

# --- Servicios systemd ---
if command -v systemctl &>/dev/null; then
    for svc in opencode.service ollama.service tailscaled.service; do
        STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
        if [[ "$STATUS" == "active" ]]; then
            pass "$svc activo"
        else
            fail "$svc no activo ($STATUS)"
        fi
    done
fi

# --- SSH ---
log "Verificando SSH..."
SSH_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 ssh://localhost:22 2>/dev/null || echo "000")
if [[ "$SSH_CODE" != "000" ]]; then
    pass "SSH responde"
else
    fail "SSH no responde"
fi

# --- Tailscale relay check ---
if command -v tailscale &>/dev/null; then
    log "Verificando Tailscale relay/directo..."
    PING_OUT=$(tailscale ping "$GX10_TS" 2>&1 | head -1 || true)
    if echo "$PING_OUT" | grep -q "pong from"; then
        LATENCY=$(echo "$PING_OUT" | grep -oP 'in \K\d+' || echo "0")
        if [[ "$LATENCY" -gt 30 ]]; then
            log "WARN: Tailscale latencia ${LATENCY}ms (posible relay)"
        else
            pass "Tailscale directo (${LATENCY}ms)"
        fi
    else
        log "WARN: No se pudo verificar Tailscale"
    fi
fi

# --- Modelos instalados ---
log "Verificando modelos Ollama..."
MODEL_LIST=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('models', [])
for m in sorted(models, key=lambda x: x.get('name', '')):
    size_gb = m.get('size', 0) / (1024**3)
    print(f\"  {m['name']} ({size_gb:.1f}GB)\")
print(f'Total: {len(models)} modelos')
" 2>/dev/null || echo "  No disponible")
log "$MODEL_LIST"

# --- VRAM / GPU ---
log "Verificando GPU..."
if command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader 2>/dev/null || echo "N/A")
    log "GPU: $GPU_INFO"
else
    log "GPU: nvidia-smi no disponible (GB10 unified memory)"
fi

# --- Conectividad remota (si estamos en GX10) ---
if [[ "$(hostname)" == *"gx10"* ]] || [[ "$GX10_TS" == "127.0.0.1" ]]; then
    log "Verificando conectividad GX10→Mac..."
    MAC_PING=$(tailscale ping "$MAC_TS" 2>&1 | head -1 || true)
    if echo "$MAC_PING" | grep -q "pong"; then
        pass "GX10→Mac alcanzable"
    else
        fail "GX10→Mac no alcanzable"
    fi
fi

# --- Resumen ---
echo ""
if [[ $ERRORS -eq 0 ]]; then
    log "TODOS LOS SMOKE TESTS PASARON"
else
    log "$ERRORS SMOKE TESTS FALLARON"
fi
exit $ERRORS
