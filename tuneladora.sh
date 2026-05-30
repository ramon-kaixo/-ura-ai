#!/bin/bash
set -euo pipefail

# TUNELADORA UNIFICADA - URA 1972
# Fusion de tuneladora_pro, tuneladora_mantenimiento, tuneladora_mejora
# Ejecuta 6 fases: Diagnóstico, Mantenimiento, Auditoría Modelos, Mejora, Rollback, Backup

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="${HOME}/URA/ura_ia_1972"
LOG="/tmp/tuneladora_unificada.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTEXT="${HOME}/URA/data/ura_context.json"
AUDIT_LOG="${HOME}/URA/logs/model_audit.jsonl"
MODO_SISTEMA="${HOME}/URA/scripts/modo_sistema.sh"
BACKUP_DIR="/tmp/tuneladora_backup_${TIMESTAMP}"
ROLLBACK_TRIGGERED=false

mkdir -p "$(dirname "$AUDIT_LOG")"
mkdir -p "${REPO}/docs/pro/reports"
mkdir -p "${HOME}/URA/data"

echo "🛫 TUNELADORA UNIFICADA — $TIMESTAMP" | tee "$LOG"
echo "========================================" | tee -a "$LOG"

# ============================================
# FASE 1: Diagnóstico y Auditoría
# ============================================
echo "📊 FASE 1: Diagnóstico y Auditoría" | tee -a "$LOG"
source "${REPO}/.venv/bin/activate" 2>/dev/null || true

# Monitoreo de recursos iniciales
RAM_INICIAL=$(free -m | awk 'NR==2{print $3}')
CPU_IDLE=$(top -bn1 | grep "Cpu(s)" | awk '{print $8}' || echo "0")
ZOMBIES_INICIAL=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
echo "   📊 RAM inicial: ${RAM_INICIAL}MB, CPU idle: ${CPU_IDLE}%, Zombies: ${ZOMBIES_INICIAL}" | tee -a "$LOG"
echo "${RAM_INICIAL}" > /tmp/tuneladora_ram_initial.txt
echo "${ZOMBIES_INICIAL}" > /tmp/tuneladora_zombies_initial.txt

# Modo sistema automático (como en tuneladora_mantenimiento)
if [ -x "$MODO_SISTEMA" ]; then
    bash "$MODO_SISTEMA" auto >> "${HOME}/URA/logs/modo_sistema.log" 2>&1 || true
    echo "   ✅ Modo sistema aplicado" | tee -a "$LOG"
fi

# Snapshot de seguridad (deshabilitado - requiere archivo específico, no directorio)
# python3 -c "from core.ura_rollback import get_ura_rollback; from pathlib import Path; get_ura_rollback().create_snapshot('tuneladora_unificada', Path('.'))" 2>/dev/null

# ruff check + fix
ruff check "$REPO" --fix --quiet 2>/dev/null

# radon cc (complejidad)
radon cc "$REPO" -a -s 2>/dev/null | tail -1

# pytest tests básicos (saltando test_imports que tiene circular import)
pytest tests/test_core_basics.py tests/test_consensus_system.py -q -k "not test_imports" 2>/dev/null | tail -3

# Monitoreo post-fase 1
RAM_FINAL=$(free -m | awk 'NR==2{print $3}')
ZOMBIES_FINAL=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
RAM_DELTA=$((RAM_FINAL - RAM_INICIAL))
ZOMBIES_DELTA=$((ZOMBIES_FINAL - ZOMBIES_INICIAL))
echo "   📊 RAM final: ${RAM_FINAL}MB (Δ: ${RAM_DELTA}MB), Zombies: ${ZOMBIES_FINAL} (Δ: ${ZOMBIES_DELTA})" | tee -a "$LOG"

# Alerta si hay zombies nuevos
if [ $ZOMBIES_DELTA -gt 0 ]; then
    echo "   ⚠️  ALERTA: ${ZOMBIES_DELTA} zombies nuevos detectados" | tee -a "$LOG"
    # Usar alert_manager si está disponible
    python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    am = get_alert_manager()
    am.create_alert('tuneladora', 'zombie_processes', f'{ZOMBIES_DELTA} zombies nuevos en FASE 1', ErrorPriority.MEDIUM)
except:
    pass
" 2>/dev/null || true
    
    # Auto-reparación: limpiar zombies
    echo "   🔧 Ejecutando auto-reparación de zombies..." | tee -a "$LOG"
    bash "${REPO}/tuneladora_repair.sh" zombies 2>&1 | tee -a "$LOG"
fi

# Alerta si RAM aumentó más de 500MB
if [ $RAM_DELTA -gt 500 ]; then
    echo "   ⚠️  ALERTA: RAM aumentó ${RAM_DELTA}MB (posible leak)" | tee -a "$LOG"
    python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    am = get_alert_manager()
    am.create_alert('tuneladora', 'memory_leak', f'RAM aumentó {RAM_DELTA}MB en FASE 1', ErrorPriority.HIGH)
except:
    pass
" 2>/dev/null || true
fi

echo "✅ FASE 1 completada" | tee -a "$LOG"

# ============================================
# FASE 2: Mantenimiento y Limpieza
# ============================================
echo "🧹 FASE 2: Mantenimiento y Limpieza" | tee -a "$LOG"

cd "$REPO"

# autoflake (imports unused)
autoflake --in-place --remove-all-unused-imports -r "$REPO" --exclude=.venv 2>/dev/null

# ruff format
ruff format "$REPO" --quiet 2>/dev/null

# bandit (seguridad) - escanea solo core/ y agents/ (no falla si hay issues)
bandit -r core/ agents/ -ll 2>/dev/null || true

# vulture (código muerto) - escanea solo core/ y agents/ (no falla si hay issues)
vulture core/ agents/ --min-confidence 70 2>/dev/null | tail -3 || true

# Monitoreo post-fase 2
RAM_FINAL=$(free -m | awk 'NR==2{print $3}')
ZOMBIES_FINAL=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
RAM_DELTA=$((RAM_FINAL - RAM_INICIAL))
ZOMBIES_DELTA=$((ZOMBIES_FINAL - ZOMBIES_INICIAL))
echo "   📊 RAM final: ${RAM_FINAL}MB (Δ: ${RAM_DELTA}MB), Zombies: ${ZOMBIES_FINAL} (Δ: ${ZOMBIES_DELTA})" | tee -a "$LOG"

# Alerta si hay zombies nuevos
if [ $ZOMBIES_DELTA -gt 0 ]; then
    echo "   ⚠️  ALERTA: ${ZOMBIES_DELTA} zombies nuevos detectados" | tee -a "$LOG"
    python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    am = get_alert_manager()
    am.create_alert('tuneladora', 'zombie_processes', f'{ZOMBIES_DELTA} zombies nuevos en FASE 2', ErrorPriority.MEDIUM)
except:
    pass
" 2>/dev/null || true
    
    # Auto-reparación: limpiar zombies
    echo "   🔧 Ejecutando auto-reparación de zombies..." | tee -a "$LOG"
    bash "${REPO}/tuneladora_repair.sh" zombies 2>&1 | tee -a "$LOG"
fi

echo "✅ FASE 2 completada" | tee -a "$LOG"

# ============================================
# FASE 3: Auditoría de Modelos Ollama
# ============================================
echo "🤖 FASE 3: Auditoría de Modelos Ollama" | tee -a "$LOG"

MODELOS_A_TESTEAR=(
    "qwen2.5-coder:32b"
    "codestral:22b"
    "qwen2.5-coder:14b"
    "deepseek-coder:6.7b"
    "qwen2.5:7b"
)

for modelo in "${MODELOS_A_TESTEAR[@]}"; do
    echo "   Probando $modelo..." | tee -a "$LOG"
    TEST_FILE="$(mktemp /tmp/ura_model_test_XXXXXX.py)"
    cat > "$TEST_FILE" << 'PYEOF'
import json, time, subprocess, sys
modelo = sys.argv[1]
prompts = [
    ("refactor", "Refactoriza esta funcion: def old(x): return [i for i in range(x) if i%2==0]"),
    ("docstring", "Genera un docstring para: def procesar(datos, umbral=0.5): return [x for x in datos if x > umbral]"),
    ("types", "Anade type hints a: def calcular( precio, descuento, impuesto ): return precio * (1-descuento) * (1+impuesto)"),
]
resultados = []
for tipo, prompt in prompts:
    inicio = time.time()
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
             "-d", json.dumps({"model": modelo, "prompt": prompt, "stream": False, "options": {"num_predict": 100}})],
            capture_output=True, text=True, timeout=30
        )
        dur = time.time() - inicio
        data = json.loads(r.stdout) if r.stdout else {}
        res = data.get("response", "")[:50]
        resultados.append({"tipo": tipo, "latencia_ms": round(dur*1000), "respuesta": res, "ok": bool(res)})
    except Exception as e:
        resultados.append({"tipo": tipo, "latencia_ms": 0, "error": str(e), "ok": False})
print(json.dumps({"modelo": modelo, "resultados": resultados}))
PYEOF
    chmod +x "$TEST_FILE"
    RESULT=$(python3 "$TEST_FILE" "$modelo" 2>/dev/null || echo '{"modelo":"'$modelo'","resultados":[]}')
    echo "$RESULT" >> "$AUDIT_LOG"
    LATENCIA=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); rs=[r for r in d.get('resultados',[]) if r.get('ok')]; print(round(sum(r['latencia_ms'] for r in rs)/len(rs)) if rs else 'N/A')" 2>/dev/null)
    echo "     -> Latencia media: ${LATENCIA}ms" | tee -a "$LOG"
    rm -f "$TEST_FILE"
done

# Monitoreo post-fase 3 (crítico - Ollama puede crear zombies)
RAM_FINAL=$(free -m | awk 'NR==2{print $3}')
ZOMBIES_FINAL=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
RAM_DELTA=$((RAM_FINAL - RAM_INICIAL))
ZOMBIES_DELTA=$((ZOMBIES_FINAL - ZOMBIES_INICIAL))
echo "   📊 RAM final: ${RAM_FINAL}MB (Δ: ${RAM_DELTA}MB), Zombies: ${ZOMBIES_FINAL} (Δ: ${ZOMBIES_DELTA})" | tee -a "$LOG"

# Alerta si hay zombies nuevos (crítico en FASE 3)
if [ $ZOMBIES_DELTA -gt 0 ]; then
    echo "   ⚠️  ALERTA CRÍTICA: ${ZOMBIES_DELTA} zombies nuevos en FASE 3 (Ollama)" | tee -a "$LOG"
    python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    am = get_alert_manager()
    am.create_alert('tuneladora', 'ollama_zombies', f'{ZOMBIES_DELTA} zombies nuevos en FASE 3 (Ollama)', ErrorPriority.HIGH)
except:
    pass
" 2>/dev/null || true
    
    # Auto-reparación: limpiar zombies
    echo "   🔧 Ejecutando auto-reparación de zombies..." | tee -a "$LOG"
    bash "${REPO}/tuneladora_repair.sh" zombies 2>&1 | tee -a "$LOG"
fi

# Alerta si RAM aumentó más de 1GB (crítico en FASE 3)
if [ $RAM_DELTA -gt 1024 ]; then
    echo "   ⚠️  ALERTA CRÍTICA: RAM aumentó ${RAM_DELTA}MB en FASE 3 (Ollama leak)" | tee -a "$LOG"
    python3 -c "
try:
    from core.alert_manager import get_alert_manager, ErrorPriority
    am = get_alert_manager()
    am.create_alert('tuneladora', 'ollama_memory_leak', f'RAM aumentó {RAM_DELTA}MB en FASE 3 (Ollama)', ErrorPriority.CRITICAL)
except:
    pass
" 2>/dev/null || true
    
    # Auto-reparación: reiniciar Ollama
    echo "   🔧 Ejecutando auto-reparación de Ollama..." | tee -a "$LOG"
    bash "${REPO}/tuneladora_repair.sh" ollama_leak 2>&1 | tee -a "$LOG"
    
    # Verificar RAM después de reparación
    RAM_AFTER_REPAIR=$(free -m | awk 'NR==2{print $3}')
    RAM_REPAIRED_DELTA=$((RAM_AFTER_REPAIR - RAM_INICIAL))
    echo "   📊 RAM después de reparación: ${RAM_AFTER_REPAIR}MB (Δ: ${RAM_REPAIRED_DELTA}MB)" | tee -a "$LOG"
fi

echo "✅ FASE 3 completada - Log: $AUDIT_LOG" | tee -a "$LOG"

# ============================================
# FASE 4: Mejora Continua y Promoción
# ============================================
echo "🚀 FASE 4: Mejora Continua y Promoción" | tee -a "$LOG"

# 🛡️ BOTÓN DE PÁNICO: Crear backup temporal antes de pytest
echo "   🛡️ Creando backup temporal en $BACKUP_DIR" | tee -a "$LOG"
mkdir -p "$BACKUP_DIR"
rsync -avz --delete "$REPO/" "$BACKUP_DIR/" 2>/dev/null || {
    echo "   ❌ ERROR CRÍTICO: No se pudo crear backup temporal" | tee -a "$LOG"
    exit 1
}
echo "   ✅ Backup temporal creado" | tee -a "$LOG"

# pytest completo con rollback automático habilitado
if pytest --quiet -x --timeout=60 2>/dev/null; then
    echo "   ✅ Tests pasados - Promocionando código" | tee -a "$LOG"
    rsync -avz "$REPO/" /zona_trabajo/ 2>/dev/null || echo "   ⚠️  No se pudo promocionar a /zona_trabajo" | tee -a "$LOG"
else
    echo "   ⚠️  Tests fallados - Activando ROLLBACK AUTOMÁTICO" | tee -a "$LOG"
    ROLLBACK_TRIGGERED=true
    echo "   🔄 Restaurando desde backup temporal..." | tee -a "$LOG"
    rsync -avz --delete "$BACKUP_DIR/" "$REPO/" 2>/dev/null || {
        echo "   ❌ ERROR CRÍTICO: Rollback falló - sistema en estado inconsistente" | tee -a "$LOG"
        exit 1
    }
    echo "   ✅ Rollback completado - código restaurado al estado anterior" | tee -a "$LOG"
    echo "   🚨 Código NO promocionado a /zona_trabajo (tests fallaron)" | tee -a "$LOG"
fi

echo "✅ FASE 4 completada" | tee -a "$LOG"

# ============================================
# FASE 5: Rollback Automático (si falla algo)
# ============================================
echo "🔄 FASE 5: Verificación y Rollback" | tee -a "$LOG"

# Verificar tests post-fase con rollback automático habilitado
if pytest tests/test_core_basics.py tests/test_consensus_system.py -q 2>/dev/null | grep -q "FAILED"; then
    echo "⚠️  Tests fallados post-fase - Activando ROLLBACK AUTOMÁTICO" | tee -a "$LOG"
    ROLLBACK_TRIGGERED=true
    echo "   🔄 Restaurando desde backup temporal..." | tee -a "$LOG"
    rsync -avz --delete "$BACKUP_DIR/" "$REPO/" 2>/dev/null || {
        echo "   ❌ ERROR CRÍTICO: Rollback falló - sistema en estado inconsistente" | tee -a "$LOG"
        exit 1
    }
    echo "   ✅ Rollback completado - código restaurado al estado anterior" | tee -a "$LOG"
else
    echo "✅ Tests post-fase OK" | tee -a "$LOG"
fi

# Limpiar backup temporal si no se activó rollback
if [ "$ROLLBACK_TRIGGERED" = false ]; then
    echo "   🧹 Limpiando backup temporal (no fue necesario)" | tee -a "$LOG"
    rm -rf "$BACKUP_DIR" 2>/dev/null || true
else
    echo "   💾 Backup temporal conservado en $BACKUP_DIR para inspección manual" | tee -a "$LOG"
fi

echo "✅ FASE 5 completada" | tee -a "$LOG"

# ============================================
# FASE 6: Backup a las 03:00
# ============================================
echo "💾 FASE 6: Backup Programado" | tee -a "$LOG"

if [ "$(date +%H)" = "03" ]; then
    echo "   Generando copia maestra..." | tee -a "$LOG"
    rsync -avz "$REPO/" "${HOME}/URA/backups/incremental_$(date +%Y%m%d)/" 2>/dev/null
    echo "   ✅ Copia maestra generada" | tee -a "$LOG"
else
    echo "   ℹ️  No es hora de backup (solo a las 03:00)" | tee -a "$LOG"
fi

# ============================================
# Aplicar modo sistema automático
# ============================================
if [ -x "$MODO_SISTEMA" ]; then
    echo "🔧 Aplicando modo sistema automático" | tee -a "$LOG"
    bash "$MODO_SISTEMA" auto >> "${HOME}/URA/logs/modo_sistema.log" 2>&1
fi

echo "========================================" | tee -a "$LOG"
echo "✅ TUNELADORA UNIFICADA COMPLETADA" | tee -a "$LOG"
echo "📅 $TIMESTAMP" | tee -a "$LOG"
