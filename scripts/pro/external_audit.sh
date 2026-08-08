#!/bin/bash
# external_audit.sh — Auditoría externa verificable del sistema URA
# Modos:
#   manual (default): ejecuta ahora y envía a IA externa
#   auto:            ejecuta ahora, guarda resultado (para cron)
#   cron-install:    instala timer diario a las 3 AM
#   cron-remove:     elimina el timer
#
# IA externa: OpenRouter (Claude 3.5 Sonnet) con fallback a Ollama local.
set -u
OUTDIR="/tmp/ura_audit"
REPO="$HOME/URA/ura_ia_1972"
DATE=$(date +%Y%m%d_%H%M)
mkdir -p "$OUTDIR" "$REPO/docs/external_audits"

# ── Config ──────────────────────────────────────────────
OPENROUTER_MODEL="anthropic/claude-3.5-sonnet"
OLLAMA_MODEL="qwen2.5-coder:14b"
HISTORIAL="$REPO/docs/pro/reports/historial_sesiones.md"
TIMER_NAME="ura-external-audit.timer"
SERVICE_NAME="ura-external-audit.service"
UNIT_DIR="$HOME/.config/systemd/user"

_section() {
    local name="$1" cmd="$2" timeout="${3:-30}"
    echo "[$(date '+%H:%M:%S')] === $name ===" >&2
    timeout "$timeout" bash -c "$cmd" > "$OUTDIR/${name}.txt" 2>&1
    local rc=$?
    [ $rc -eq 124 ] && echo "(TIMEOUT ${timeout}s)" >> "$OUTDIR/${name}.txt"
    echo "exit=$rc" >> "$OUTDIR/${name}.txt"
    return $rc
}

_cleanup() { rm -rf "$OUTDIR"; }
trap _cleanup EXIT TERM INT

# ── Modo auto (silencioso, para cron) ────────────────────
if [ "${1:-}" = "auto" ]; then
    exec > /dev/null 2>&1
fi

# ── Modo cron-install / cron-remove ──────────────────────
if [ "${1:-}" = "cron-install" ]; then
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_DIR/$SERVICE_NAME" << UNIT
[Unit]
Description=URA External Audit — ejecuta auditoría y envía a IA
[Service]
Type=oneshot
ExecStart=$REPO/scripts/pro/external_audit.sh auto
UNIT
    cat > "$UNIT_DIR/$TIMER_NAME" << TIMER
[Unit]
Description=URA External Audit diario (3 AM)
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=default.target
TIMER
    systemctl --user daemon-reload
    systemctl --user enable --now "$TIMER_NAME"
    echo "[$(date '+%H:%M:%S')] Timer instalado: $TIMER_NAME (diario 3 AM)" >&2
    exit 0
fi

if [ "${1:-}" = "cron-remove" ]; then
    systemctl --user disable --now "$TIMER_NAME" 2>/dev/null || true
    rm -f "$UNIT_DIR/$TIMER_NAME" "$UNIT_DIR/$SERVICE_NAME"
    systemctl --user daemon-reload
    echo "[$(date '+%H:%M:%S')] Timer eliminado" >&2
    exit 0
fi

cd "$REPO" || exit 1

# ═══════════════════════════════════════════════════════════
# SECCIONES DE AUDITORÍA
# ═══════════════════════════════════════════════════════════

_section "01_git" "
echo '=== LOG ===' && git log --oneline -5
echo '=== STATUS ===' && git status --short
echo '=== DIFF ===' && git diff --stat
" 15

_section "02_lint" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
ruff check . --exclude .venv,__pycache__,.git,.sandbox_packages,.opencode,.tuneladora --statistics
" 60

_section "03_tests" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
python3 -m pytest tests/nightly/test_events.py tests/integration/test_pipeline_mvp.py tests/integration/test_plugin.py tests/integration/test_plugin_registry.py tests/integration/test_assistant_auth.py tests/integration/test_registry_v2.py tests/infra/test_security.py tests/infra/test_preflight_system.py tests/integration/test_audit_models.py tests/integration/test_audit_message_store.py tests/infra/test_ci_cd.py tests/infra/test_documentation.py tests/integration/test_integration_f10.py tests/integration/test_integration_f11.py tests/integration/test_observability_f11.py -q --tb=line --no-header -p no:timeout 2>&1
" 120

_section "04_bandit" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
echo '=== HIGH ===' && bandit -r . -x .venv,__pycache__,.git,.sandbox_packages,.opencode,.tuneladora -lll 2>&1 | grep -E 'Severity: High|Issue|Location'
" 120

_section "05_services" "
echo '=== ACTIVOS ===' && systemctl list-units --type=service --state=active --no-pager 2>/dev/null | grep -E '(ura|model|mochila|heartbeat|watch)'
echo '=== FALLIDOS ===' && systemctl list-units --type=service --state=failed --no-pager 2>/dev/null
" 15

_section "06_ports" "
ss -tlnp 2>/dev/null | grep LISTEN | sort -n -t: -k2
" 10

_section "07_disk" "
df -h / /home /run 2>/dev/null
echo '---'
du -sh \"$REPO\" 2>/dev/null
" 10

_section "08_manifest" "
python3 scripts/pro/tuneladora/preflight_system.py audit
" 15

_section "09_merge" "
find \"$REPO\" -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/.git/*' -not -path '*/.sandbox_packages/*' -not -path '*/.opencode/*' -not -path '*/build/*' -not -path '*/.tuneladora/*' -exec grep -l '<<<<<<<' {} \\; 2>/dev/null | grep -v inspectores || echo '(ninguno)'
" 10

_section "10_stash" "
git stash list || echo '0'
" 5

# ═══════════════════════════════════════════════════════════
# GENERAR INFORME
# ═══════════════════════════════════════════════════════════
REPORT_FILE="$REPO/docs/external_audits/$DATE.md"

{
echo "# Auditoría Externa URA — $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "## Resumen Ejecutivo"
echo ""

LINT=$(grep -c "^[0-9]" "$OUTDIR/02_lint.txt" 2>/dev/null || echo "?")
TEST_PASS=$(grep -oP '\d+ passed' "$OUTDIR/03_tests.txt" 2>/dev/null | head -1 || echo "?")
TEST_FAIL=$(grep -oP '\d+ failed' "$OUTDIR/03_tests.txt" 2>/dev/null | head -1 || echo "?")
TEST_SKIP=$(grep -oP '\d+ skipped' "$OUTDIR/03_tests.txt" 2>/dev/null | head -1 || echo "?")
BANDIT_HIGH=$(grep -c "Severity: High" "$OUTDIR/04_bandit.txt" 2>/dev/null || echo "0")
SERV_FAILED=$(grep -c "failed" "$OUTDIR/05_services.txt" 2>/dev/null || echo "?")
MANIFEST=$(grep -c "Sistema coincide\|0 discrepancias" "$OUTDIR/08_manifest.txt" 2>/dev/null || echo "no")
MERGE=$(head -1 "$OUTDIR/09_merge.txt" 2>/dev/null || echo "?")

echo "| Métrica | Valor |"
echo "|---------|-------|"
echo "| Linting (ruff) | $LINT errores |"
echo "| Tests pasados | $TEST_PASS |"
echo "| Tests fallidos | $TEST_FAIL |"
echo "| Tests skipped | $TEST_SKIP |"
echo "| Bandit HIGH | $BANDIT_HIGH |"
echo "| Servicios fallidos | $SERV_FAILED |"
echo "| Manifest vs sistema | $MANIFEST |"
echo "| Merge conflicts | $MERGE |"
echo ""

for s in 01_git 02_lint 03_tests 04_bandit 05_services 06_ports 07_disk 08_manifest 09_merge 10_stash; do
    echo "---"
    echo ""
    echo "## $(echo $s | tr '_' ' ' | tr '[:lower:]' '[:upper:]')"
    echo ""
    echo '```'
    cat "$OUTDIR/$s.txt" 2>/dev/null || echo "(NO DATA)"
    echo '```'
    echo ""
done

echo "---"
echo ""
echo "*Auditoría generada el $(date) por external_audit.sh*"
echo "*Host: $(hostname)*"

} > "$REPORT_FILE"

ln -sf "$REPORT_FILE" "$REPO/docs/external_audits/latest.md"
echo "[$(date '+%H:%M:%S')] Reporte: $REPORT_FILE" >&2

# ═══════════════════════════════════════════════════════════
# ENVÍO A IA EXTERNA (multi-LLM)
# ═══════════════════════════════════════════════════════════

_llm_prompt() {
    local report="$1"
    cat << 'PROMPT'
Eres un auditor senior de sistemas. Revisa este informe de auditoría de URA y genera:
1. VEREDICTO: ESTABLE / NO ESTABLE / INESTABLE CON RIESGOS
2. RIESGOS: lista priorizada (CRITICAL, HIGH, MEDIUM, LOW)
3. RECOMENDACIONES: qué arreglar primero
4. MÉTRICAS CLAVE: tests, linting, seguridad, servicios

Informe:
PROMPT
    head -300 "$report"
}

_call_deepseek() {
    local model="$1" prompt="$2" outfile="$3"
    # Leer key directamente del .env del proyecto
    local api_key
    api_key=$(grep DEEPSEEK_API_KEY "$REPO/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | xargs)
    [ -z "$api_key" ] && api_key="${DEEPSEEK_API_KEY:-}"
    [ -z "$api_key" ] && return 1

    local escaped
    escaped=$(echo "$prompt" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" 2>/dev/null)
    [ -z "$escaped" ] && return 1

    local resp
    resp=$(curl -s -w "\n%{http_code}" --max-time 180 "https://api.deepseek.com/chat/completions" \
        -H "Authorization: Bearer $api_key" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"$model\", \"messages\": [{\"role\": \"user\", \"content\": $escaped}], \"max_tokens\": 4000}" 2>/dev/null)

    local http_code=$(echo "$resp" | tail -1)
    local body=$(echo "$resp" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo "$body" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d['choices'][0]['message']['content'])
except Exception as e:
    print(f'Error: {e}')
" 2>/dev/null > "$outfile"
        [ -s "$outfile" ] && return 0
    fi
    return 1
}

_call_ollama() {
    local model="$1" prompt="$2" outfile="$3"
    local prompt_tokens=$(echo "$prompt" | wc -c)
    if [ "$prompt_tokens" -gt 2000 ] && [ "$model" != "qwen2.5-coder:14b" ]; then
        model="qwen2.5-coder:14b"
        echo "[$(date '+%H:%M:%S')] Prompt grande (${prompt_tokens} chars), usando qwen2.5-coder:14b" >&2
    fi
    curl -s --max-time 600 "http://localhost:11434/api/generate" \
        -d "{\"model\": \"$model\", \"prompt\": \"$prompt\", \"stream\": false}" 2>/dev/null | \
    python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('response',''))
except: pass
" 2>/dev/null > "$outfile"
    [ -s "$outfile" ] && return 0 || return 1
}

_alert_if_critical() {
    local report="$1"
    local alert=""
    
    # Check test failures
    local fails
    fails=$(grep -oP '\d+ failed' "$report" | head -1 | grep -oP '\d+')
    [ -n "$fails" ] && [ "$fails" -gt 5 ] && alert+="CRITICAL: $fails tests fallan\n"
    
    # Check disk
    local disk_usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    [ -n "$disk_usage" ] && [ "$disk_usage" -gt 90 ] && alert+="CRITICAL: Disco al ${disk_usage}%\n"
    
    # Check services
    local failed_services
    failed_services=$(grep -c "failed" "$OUTDIR/05_services.txt" 2>/dev/null)
    [ -n "$failed_services" ] && [ "$failed_services" -gt 0 ] && alert+="WARNING: $failed_services servicios fallidos\n"
    
    if [ -n "$alert" ]; then
        local alert_file="$REPO/docs/external_audits/${DATE}_ALERTA.txt"
        echo -e "$alert" > "$alert_file"
        echo "[$(date '+%H:%M:%S')] ⚠️ ALERTA: $(echo "$alert" | tr '\n' ' ')" >&2
    fi
}

PROMPT=$(_llm_prompt "$REPORT_FILE")

echo "[$(date '+%H:%M:%S')] Enviando a DeepSeek..." >&2

DEEPSEEK_FILE="$REPO/docs/external_audits/${DATE}_DEEPSEEK.md"
if _call_deepseek "deepseek-coder" "$PROMPT" "$DEEPSEEK_FILE"; then
    if [ ! -s "$DEEPSEEK_FILE" ] || [ "$(wc -c < "$DEEPSEEK_FILE")" -lt 500 ]; then
        echo "[$(date '+%H:%M:%S')] ⚠️ DeepSeek devolvió contenido vacío o muy corto, fallback a Ollama" >&2
    else
        echo "[$(date '+%H:%M:%S')] ✅ DeepSeek: $DEEPSEEK_FILE" >&2
    fi
else
    echo "[$(date '+%H:%M:%S')] ⚠️ DeepSeek no disponible, fallback a Ollama" >&2
fi

# Fallback: Ollama local si DeepSeek no generó output válido
if [ ! -s "$DEEPSEEK_FILE" ] || [ "$(wc -c < "$DEEPSEEK_FILE")" -lt 500 ]; then
    echo "[$(date '+%H:%M:%S')] Ejecutando fallback Ollama..." >&2
    OLLAMA_FILE="$REPO/docs/external_audits/${DATE}_OLLAMA.md"
    if _call_ollama "$OLLAMA_MODEL" "$PROMPT" "$OLLAMA_FILE"; then
        if [ ! -s "$OLLAMA_FILE" ] || [ "$(wc -c < "$OLLAMA_FILE")" -lt 500 ]; then
            echo "[$(date '+%H:%M:%S')] [ERROR] Ollama tampoco generó auditoría válida" >&2
            exit 1
        fi
        echo "[$(date '+%H:%M:%S')] ✅ Ollama fallback: $OLLAMA_FILE" >&2
    else
        echo "[$(date '+%H:%M:%S')] [ERROR] Ollama fallback falló" >&2
        exit 1
    fi
fi

# Alertas
_alert_if_critical "$REPORT_FILE"

echo "[$(date '+%H:%M:%S')] Auditoría completa: $REPORT_FILE" >&2
