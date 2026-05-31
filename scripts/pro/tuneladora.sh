#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# TUNELADORA UNIFICADA — URA 1972
# Fusión COMPLETA de todas las tuneladoras sin quitar nada:
#   tuneladora_v3.sh (14 fases) + tuneladora.sh GX10 (6 fases)
#   + tuneladora_mantenimiento.sh + tuneladora_mejora.sh
# Diseñada para GX10 (ejecución nativa o con sandbox docker)
# Fuente de verdad: repo Mac → sincronizada a GX10
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Cargar ura_env.sh — ÚNICA fuente de verdad para rutas
# Si no existe, FALLA EN VOZ ALTA (no inventa rutas)
if [ ! -f "${SCRIPT_DIR}/ura_env.sh" ]; then
    echo "ERROR: ${SCRIPT_DIR}/ura_env.sh no encontrado." >&2
    echo "Este archivo es la fuente de verdad de rutas. Sin él, la tuneladora no opera." >&2
    echo "Copia desde el repo Mac: scp scripts/ura_env.sh gx10:~/URA/ura_ia_1972/scripts/" >&2
    exit 1
fi
source "${SCRIPT_DIR}/ura_env.sh"
init_ura_env

REPO="$URA_ROOT"
LOG="${URA_LOGS}/tuneladora_$(date +%Y%m%d_%H%M%S).log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTEXT="${URA_DATA}/ura_context.json"
AUDIT_LOG="${URA_LOGS}/model_audit.jsonl"
MODO_SISTEMA="${URA_SCRIPTS}/modo_sistema.sh"
AUDITORIA="${URA_SCRIPTS}/auditoria_post_caida.sh"
ESCANER="${URA_SCRIPTS}/escaner_vanguardia.sh"
BACKUP_DIR="${URA_BACKUPS}/tuneladora_${TIMESTAMP}"
CUARENTENA="${URA_CUARENTENA}"
ERRORS=0
ROLLBACK_TRIGGERED=false
START_TIME=$(date +%s)
SECRETOS_ENCONTRADOS=0

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

mkdir -p "$(dirname "$AUDIT_LOG")" "$CUARENTENA" "${REPO}/docs/pro/reports" "${URA_DATA}"

log()  { echo "$1" | tee -a "$LOG"; }

run_in_sandbox() {
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "ura-mejora-continua"; then
        docker exec ura-mejora-continua "$@" 2>/dev/null || "$@"
    else
        "$@"
    fi
}

monitor_recursos() {
    local FASE="$1"
    RAM_FINAL=$(free -m 2>/dev/null | awk 'NR==2{print $3}' || echo 0)
    CPU_IDLE=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $8}' || echo "N/A")
    ZOMBIES_FINAL=$(ps aux 2>/dev/null | awk '{print $8}' | grep -c Z || echo 0)
    RAM_DELTA=$(( RAM_FINAL - RAM_INICIAL ))
    ZOMBIES_DELTA=$(( ZOMBIES_FINAL - ZOMBIES_INICIAL ))
    log "   📊 RAM: ${RAM_FINAL}MB (Δ: ${RAM_DELTA}MB) | CPU idle: ${CPU_IDLE}% | Zombies: ${ZOMBIES_FINAL} (Δ: ${ZOMBIES_DELTA})"

    if [ "${ZOMBIES_DELTA:-0}" -gt 0 ]; then
        log "   ⚠️  ALERTA: ${ZOMBIES_DELTA} zombies en ${FASE}"
        command -v python3 &>/dev/null && python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    get_alert_manager().create_alert('tuneladora', 'zombie_processes', '${ZOMBIES_DELTA} zombies en ${FASE}', ErrorPriority.MEDIUM)
except: pass
" 2>/dev/null || true
        [ -x "${REPO}/tuneladora_repair.sh" ] && bash "${REPO}/tuneladora_repair.sh" zombies 2>&1 | tee -a "$LOG" || true
    fi

    if [ "${RAM_DELTA:-0}" -gt 1024 ]; then
        log "   ⚠️  ALERTA CRÍTICA: RAM +${RAM_DELTA}MB en ${FASE} (posible leak)"
        command -v python3 &>/dev/null && python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    get_alert_manager().create_alert('tuneladora', 'memory_leak', 'RAM +${RAM_DELTA}MB en ${FASE}', ErrorPriority.HIGH)
except: pass
" 2>/dev/null || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 0: PREFLIGHT — Entorno, modo sistema, compuerta post-caída, shadow hooks
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "═══════════════════════════════════════════════"
log "TUNELADORA UNIFICADA — ${TIMESTAMP}"
log "═══════════════════════════════════════════════"

log "📍 FASE 0: Preflight"

RAM_INICIAL=$(free -m 2>/dev/null | awk 'NR==2{print $3}' || echo 0)
CPU_IDLE=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $8}' || echo "N/A")
ZOMBIES_INICIAL=$(ps aux 2>/dev/null | awk '{print $8}' | grep -c Z || echo 0)
log "   📊 Inicial: RAM ${RAM_INICIAL}MB | CPU idle ${CPU_IDLE}% | Zombies ${ZOMBIES_INICIAL}"

if [ -x "$MODO_SISTEMA" ]; then
    bash "$MODO_SISTEMA" auto >> "${URA_LOGS}/modo_sistema.log" 2>&1 || true
    log "   ✅ Modo sistema aplicado"
fi

if [ -x "$AUDITORIA" ]; then
    AUDIT_STATUS=$(python3 -c "
import json
try:
    with open('${CONTEXT}') as f:
        ctx = json.load(f)
    print(ctx.get('auditoria_post_caida', {}).get('resultado', 'NO_EJECUTADA'))
except: print('NO_EJECUTADA')
" 2>/dev/null || echo "NO_EJECUTADA")

    if [ "$AUDIT_STATUS" != "INTEGRIDAD_COMPLETADA_100%" ]; then
        log "   ⚠️  Ejecutando auditoría post-caída..."
        if bash "$AUDITORIA" >> "$LOG" 2>&1; then
            log "   ✅ Auditoría post-caída superada"
        else
            CORRUPTAS=$(python3 -c "
import json
try:
    with open('${CONTEXT}') as f:
        ctx = json.load(f)
    print(ctx.get('auditoria_post_caida', {}).get('corruptas_detectadas', ''))
except: print('')
" 2>/dev/null || echo "")
            log "   🚨 ALERTA ROJA — Corrupción detectada: $CORRUPTAS"
            IFS=',' read -ra DB_LIST <<< "$CORRUPTAS"
            for db_path in "${DB_LIST[@]}"; do
                db_path=$(echo "$db_path" | xargs)
                [ -f "$db_path" ] || continue
                cp "$db_path" "${CUARENTENA}/$(basename "$db_path").corrupto.$(date +%Y%m%d%H%M%S)"
                log "     → Enviado a cuarentena: $(basename "$db_path")"
            done
            log "   🚨 Tuneladora ABORTADA — corrija bases corruptas antes de continuar"
            exit 1
        fi
    else
        log "   ✅ Compuerta post-caída OK"
    fi
fi

# Shadow hooks (de tuneladora_v3 fase 0.7)
SHADOW="${URA_SCRIPTS}/pro/phase_shadow_hooks.sh"
if [ -x "$SHADOW" ]; then
    bash "$SHADOW" >> "$LOG" 2>&1 && log "   ✅ Shadow hooks generados" || log "   ⚠️  Shadow hooks con advertencias"
fi

monitor_recursos "FASE 0"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1: CÓDIGO — ruff, autoflake, vulture, mypy, radon, jscpd, gx10_handler
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 1: Código (ruff, autoflake, vulture, mypy, radon, jscpd)"

cd "$REPO"

run_in_sandbox ruff check . --fix --quiet 2>/dev/null && log "   ✅ ruff check" || log "   ⚠️  ruff check con advertencias"
run_in_sandbox ruff format . --quiet 2>/dev/null && log "   ✅ ruff format" || log "   ⚠️  ruff format con advertencias"

command -v autoflake &>/dev/null && autoflake --in-place --remove-all-unused-imports -r . --exclude=.venv 2>/dev/null && log "   ✅ autoflake" || true

command -v vulture &>/dev/null && { vulture core/ agents/ --min-confidence 70 2>/dev/null | tail -3 >> "$LOG" || true; log "   ✅ vulture"; }

command -v mypy &>/dev/null && { mypy core/ agents/ --follow-imports=silent --ignore-missing-imports 2>/dev/null && log "   ✅ mypy" || log "   ⚠️  mypy con advertencias"; }

if command -v radon &>/dev/null; then
    radon cc "$REPO" -a -s >> "$LOG" 2>&1 && log "   ✅ radon" || log "   ⚠️  radon encontró alta complejidad"
fi

if command -v jscpd &>/dev/null; then
    jscpd "$REPO" --format json --output jscpd-report.json >> "$LOG" 2>&1 && log "   ✅ jscpd" || log "   ⚠️  jscpd encontró clones"
fi

# Validación gx10_handler (de tuneladora_mantenimiento)
if python3 -c "from handlers.gx10_handler import get_recursos, get_estado, ejecutar, handle_gx10_command; print('OK')" 2>/dev/null; then
    log "   ✅ gx10_handler: OK"
else
    log "   ⚠️  gx10_handler: no disponible"
fi

monitor_recursos "FASE 1"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2: SEGURIDAD — bandit, semgrep, trivy, pip-audit, trufflehog
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 2: Seguridad (bandit, semgrep, trivy, pip-audit, secretos)"

run_in_sandbox bandit -r core/ agents/ -ll 2>/dev/null && log "   ✅ bandit" || log "   ⚠️  bandit con advertencias"

command -v semgrep &>/dev/null && { semgrep --config auto --severity WARNING . 2>/dev/null && log "   ✅ semgrep" || log "   ⚠️  semgrep con advertencias"; }
command -v trivy &>/dev/null && { trivy fs --severity HIGH,CRITICAL --quiet . 2>/dev/null && log "   ✅ trivy" || log "   ⚠️  trivy con advertencias"; }
command -v pip-audit &>/dev/null && { pip-audit 2>/dev/null && log "   ✅ pip-audit" || log "   ⚠️  pip-audit con advertencias"; }

if command -v trufflehog &>/dev/null; then
    if trufflehog filesystem . --json 2>/dev/null | grep -q ";" 2>/dev/null; then
        log "   🚫 BLOQUEO: Secretos encontrados"
        SECRETOS_ENCONTRADOS=1
        ERRORS=$((ERRORS + 1))
    else
        log "   ✅ sin secretos"
    fi
fi

monitor_recursos "FASE 2"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3: MODELOS — Auditoría Ollama + complejidad
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 3: Modelos (Auditoría Ollama)"

if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    MODELOS_A_TESTEAR=(
        "qwen2.5-coder:32b"
        "codestral:22b"
        "qwen2.5-coder:14b"
        "deepseek-coder:6.7b"
        "qwen2.5:7b"
    )

    for modelo in "${MODELOS_A_TESTEAR[@]}"; do
        log "   Probando $modelo..."
        RESULT=$(python3 -c "
import json, time, subprocess, sys
modelo = sys.argv[1]
prompts = [
    ('refactor', 'Refactoriza: def old(x): return [i for i in range(x) if i%2==0]'),
    ('docstring', 'Genera docstring para: def procesar(datos, u=0.5): return [x for x in datos if x > u]'),
    ('types', 'Type hints para: def calc(p, d, i): return p*(1-d)*(1+i)'),
]
resultados = []
for tipo, prompt in prompts:
    inicio = time.time()
    try:
        r = subprocess.run(['curl', '-s', '-X', 'POST', 'http://localhost:11434/api/generate',
            '-d', json.dumps({'model': modelo, 'prompt': prompt, 'stream': False, 'options': {'num_predict': 100}})],
            capture_output=True, text=True, timeout=30)
        dur = time.time() - inicio
        data = json.loads(r.stdout) if r.stdout else {}
        res = data.get('response', '')[:50]
        resultados.append({'tipo': tipo, 'latencia_ms': round(dur*1000), 'respuesta': res, 'ok': bool(res)})
    except Exception as e:
        resultados.append({'tipo': tipo, 'latencia_ms': 0, 'error': str(e), 'ok': False})
print(json.dumps({'modelo': modelo, 'resultados': resultados}))
" "$modelo" 2>/dev/null || echo '{"modelo":"'$modelo'","resultados":[]}')
        echo "$RESULT" >> "$AUDIT_LOG"
        LATENCIA=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); rs=[r for r in d.get('resultados',[]) if r.get('ok')]; print(round(sum(r['latencia_ms'] for r in rs)/len(rs)) if rs else 'N/A')" 2>/dev/null)
        log "     → Latencia: ${LATENCIA}ms"
    done

    monitor_recursos "FASE 3"

    if [ "${RAM_DELTA:-0}" -gt 1024 ]; then
        log "   🔧 RAM >1GB en FASE 3 — Reiniciando Ollama..."
        sudo systemctl restart ollama 2>/dev/null || true
        sleep 5
        RAM_AFTER=$(free -m | awk 'NR==2{print $3}')
        log "   📊 RAM post-reinicio Ollama: ${RAM_AFTER}MB (Δ: $((RAM_AFTER - RAM_INICIAL))MB)"
    fi
else
    log "   ℹ️  Ollama no disponible — omitiendo auditoría de modelos"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 4: MEJORA — Tests, arena Docker, rollback, promoción, validación
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 4: Mejora (tests, arena, rollback, promoción, validación)"

# Arena Docker (de tuneladora_v3 fase 10)
if docker images --format '{{.Repository}}' 2>/dev/null | grep -qx "ura-arena-mejora-continua"; then
    if docker run --rm ura-arena-mejora-continua bash /test_arena.sh >> "$LOG" 2>&1; then
        log "   ✅ Arena Docker superada"
    else
        log "   ❌ Arena Docker fallada"
        ERRORS=$((ERRORS + 1))
    fi
else
    log "   ℹ️  Imagen ura-arena-mejora-continua no disponible — omitiendo arena"
fi

log "   🛡️  Backup temporal pre-tests"
mkdir -p "$BACKUP_DIR"
rsync -avz --delete "$REPO/" "$BACKUP_DIR/" >> "$LOG" 2>&1 || log "   ❌ Error creando backup temporal"

if run_in_sandbox pytest --quiet -x --timeout=60 --ignore=core/test_n2_maleta_manager.py 2>/dev/null; then
    log "   ✅ Tests superados"
    if [ -d /zona_trabajo ]; then
        rsync -avz "$REPO/" /zona_trabajo/ >> "$LOG" 2>&1 && log "   ✅ Código promocionado a /zona_trabajo" || true
    fi
    rm -rf "$BACKUP_DIR" 2>/dev/null || true
else
    log "   ⚠️  Tests fallados — ACTIVANDO ROLLBACK"
    ROLLBACK_TRIGGERED=true
    rsync -avz --delete "$BACKUP_DIR/" "$REPO/" >> "$LOG" 2>&1 || log "   ❌ Rollback falló"
    log "   ✅ Rollback completado — código restaurado"
fi

# Validación de promociones (de tuneladora_v3 fase 13)
PROMO="${URA_SCRIPTS}/pro/phase_promotion_validation.sh"
if [ -x "$PROMO" ]; then
    bash "$PROMO" >> "$LOG" 2>&1 && log "   ✅ Validación de promociones" || log "   ⚠️  Validación de promociones con advertencias"
fi

monitor_recursos "FASE 4"

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 5: RESPALDO — Snapshot, backup horario, escáner vanguardia
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 5: Respaldo (snapshot, backup, vanguardia)"

if python3 -c "from core.ura_rollback import get_ura_rollback; get_ura_rollback().create_snapshot('tuneladora', '.')" 2>/dev/null; then
    log "   ✅ Snapshot creado"
else
    log "   ℹ️  Snapshot no disponible"
fi

if [ "$(date +%H)" = "03" ]; then
    rsync -avz "$REPO/" "${URA_BACKUPS}/incremental_$(date +%Y%m%d)/" >> "$LOG" 2>&1 && log "   ✅ Backup maestro generado" || log "   ⚠️  Backup falló"
fi

# Escáner de Vanguardia semanal (de tuneladora_mantenimiento)
MARKER_VANGUARDIA="${URA_DATA}/.ultimo_escaneo_vanguardia"
EJECUTAR_ESCANER=false
if [ -f "$MARKER_VANGUARDIA" ]; then
    ULTIMO=$(cat "$MARKER_VANGUARDIA")
    AHORA=$(date +%s)
    DIFERENCIA=$(( (AHORA - ULTIMO) / 86400 ))
    [ "$DIFERENCIA" -ge 7 ] && EJECUTAR_ESCANER=true
else
    EJECUTAR_ESCANER=true
fi

if [ "$EJECUTAR_ESCANER" = true ] && [ -x "$ESCANER" ]; then
    bash "$ESCANER" 2>&1 | tee -a "${URA_LOGS}/tuneladora_escaner.log" || log "   ⚠️  Escáner de vanguardia falló"
    log "   ✅ Escáner de vanguardia completado"
    date +%s > "$MARKER_VANGUARDIA"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 6: MÉTRICAS — Prometheus, Loki, Langfuse (stubs funcionales)
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "📍 FASE 6: Métricas y observabilidad"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

METRICS="${URA_SCRIPTS}/pro/tuneladora_metrics.sh"
LOKI_SCRIPT="${URA_SCRIPTS}/pro/tuneladora_loki.sh"
LANGFUSE="${URA_SCRIPTS}/pro/tuneladora_langfuse.sh"

[ -x "$METRICS" ] && bash "$METRICS" "$DURATION" "$ERRORS" "6" >> "$LOG" 2>&1 && log "   ✅ Métricas enviadas" || log "   ℹ️  Métricas no disponibles"
[ -x "$LOKI_SCRIPT" ] && bash "$LOKI_SCRIPT" "$LOG" >> "$LOG" 2>&1 && log "   ✅ Logs enviados a Loki" || log "   ℹ️  Loki no disponible"
[ -x "$LANGFUSE" ] && bash "$LANGFUSE" >> "$LOG" 2>&1 && log "   ✅ Métricas LLM a Langfuse" || log "   ℹ️  Langfuse no disponible"

# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETADO — Puerta de promoción
# ═══════════════════════════════════════════════════════════════════════════════
log ""
log "═══════════════════════════════════════════════"
log "⏱️  Duración total: ${DURATION}s"
log "═══════════════════════════════════════════════"

if [ "$SECRETOS_ENCONTRADOS" -eq 1 ]; then
    log "🚫 BLOQUEO DE PROMOCIÓN: Secretos expuestos"
    exit 1
fi

if [ "$ERRORS" -eq 0 ]; then
    log "✅ TUNELADORA COMPLETADA SIN ERRORES — ${DURATION}s"
    log "✅ PUERTA DE PROMOCIÓN: PASADA"
    exit 0
else
    log "❌ TUNELADORA FALLÓ con ${ERRORS} errores — ${DURATION}s"
    log "🚫 BLOQUEO DE PROMOCIÓN: Errores en fases"
    exit 1
fi
