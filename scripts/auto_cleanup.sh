#!/bin/bash
set -euo pipefail

# ======================================================================
# TUNELADORA URA-DEVSECOPS-2026 — Pipeline de 7 Rodillos
# CodeRefine Engineering — v3.2 (revisado por Ing. Visor)
# ======================================================================

if [ -f "$HOME/URA/ura_ia_1972/.venv/bin/activate" ]; then
    source "$HOME/URA/ura_ia_1972/.venv/bin/activate"
fi

readonly REPO="${HOME}/URA/ura_ia_1972"
readonly QUARANTINE_BASE="${REPO}/quarantine"
readonly LOG_DIR="${REPO}/logs"
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$QUARANTINE_BASE" "$LOG_DIR"
cd "$REPO"

# ----------------------------------------------------------------------
# CUARENTENA INDUSTRIAL
# ----------------------------------------------------------------------
quarantine_files() {

# ----------------------------------------------------------------------
# SEGURIDAD: Activar sandbox si un rodillo falla
# ----------------------------------------------------------------------
trigger_security_sandbox() {
    local reason="$1"
    echo "🚨 Activando sandbox de Seguridad por: $reason"
    if [ -f "$REPO/sandbox/Seguridad/scripts/run.sh" ]; then
        bash "$REPO/sandbox/Seguridad/scripts/run.sh" --reason="$reason" &
    fi
}

    local reason="$1"
    local dir="${QUARANTINE_BASE}/${TIMESTAMP}_${reason}"
    mkdir -p "$dir"
    for f in $ARCHIVOS; do
        if [ -f "$f" ]; then
            cp "$f" "$dir/"
            chmod 400 "$dir/$(basename "$f")"
        fi
    done
    git checkout -- $ARCHIVOS 2>/dev/null || true
    echo ""
    echo "⛔ CÓDIGO EN CUARENTENA (${reason})"
    echo "   Ubicación: ${dir}"
    echo "   Permisos: 400 (solo lectura)"
    echo ""
}

# ----------------------------------------------------------------------
# ARCHIVOS MODIFICADOS
# ----------------------------------------------------------------------
ARCHIVOS=$(git diff --name-only HEAD 2>/dev/null | grep '\.py$' || true)

if [ -z "$ARCHIVOS" ]; then
    echo "[$(date)] Sin archivos Python modificados. Nada que hacer."
    exit 0
fi

echo ""
echo "=============================================="
echo "  TUNELADORA URA-DEVSECOPS-2026 INICIANDO"
echo "  Archivos: $(echo "$ARCHIVOS" | wc -l | tr -d ' ')"
echo "=============================================="
echo ""

# ======================================================================
# 🛫 RODILLO 0: Pre-vuelo
# ======================================================================
echo "🛫 RODILLO 0: Verificando conflictos..."
if ! python3 "$REPO/scripts/preflight_check.py" $ARCHIVOS; then
    echo "🔴 Rodillo 0: BLOQUEADO"
    quarantine_files "preflight_failure"
    trigger_security_sandbox "Rodillo 0 fallido"
    exit 1
fi
echo "✅ Rodillo 0 completado."
echo ""

# ======================================================================
# 🧼 RODILLO 1: Código muerto
# ======================================================================
echo "🧼 RODILLO 1: Extirpando código muerto..."
for f in $ARCHIVOS; do [ -f "$f" ] && ruff check --fix --quiet "$f" 2>/dev/null; done
for f in $ARCHIVOS; do [ -f "$f" ] && autoflake --in-place --remove-all-unused-imports --remove-unused-variables "$f" 2>/dev/null; done
echo ">>> Refactorización completada."

# ======================================================================
# 🧱 RODILLO 2: Compactación Estructural
# ======================================================================
echo "🧱 RODILLO 2: Compactando estructura..."
for f in $ARCHIVOS; do [ -f "$f" ] && ruff format --quiet "$f" 2>/dev/null; done
for f in $ARCHIVOS; do
    if [ -f "$f" ]; then
        L=$(wc -l < "$f")
        [ "$L" -gt 200 ] && echo "⚠️  $f ($L líneas) — considerar despiece atómico"
    fi
done
echo "✅ Rodillo 2 completado."
echo ""

# ======================================================================
# ⚔️ RODILLO 3: Anti-conflictos
# ======================================================================
echo "⚔️  RODILLO 3: Escaneando marcas de merge..."
CONFLICTOS=$(grep -rn -E "(<<<<<<<|=======|>>>>>>>)" $ARCHIVOS 2>/dev/null || true)
if [ -n "$CONFLICTOS" ]; then
    echo "🔴 Rodillo 3: MARCAS DE MERGE DETECTADAS"
    echo "$CONFLICTOS"
    quarantine_files "merge_conflict"
    trigger_security_sandbox "Rodillo 3 fallido"
    exit 1
fi
echo "✅ Rodillo 3 completado."
echo ""

# ======================================================================
# 🔬 RODILLO 4: Tests
# ======================================================================
echo "🔬 RODILLO 4: Ejecutando tests..."
PYTEST_CMD="python3 -m pytest tests/test_core_basics.py tests/test_consensus_system.py tests/test_circuit_breaker.py -q -x"
if ! $PYTEST_CMD 2>/dev/null; then
    echo "🔴 Rodillo 4: TESTS FALLIDOS"
    quarantine_files "test_failure"
    trigger_security_sandbox "Rodillo 4 fallido"
    exit 1
fi
echo "✅ Rodillo 4 completado."
echo ""

# ======================================================================
# 💻 RODILLO 5: Concurrencia
# ======================================================================
echo "💻 RODILLO 5: Verificando timeouts..."
TIMEOUT_VIOLATIONS=$(grep -rn -E "requests\.(get|post|put|delete|patch)\(" $ARCHIVOS 2>/dev/null | grep -v "timeout=" || true)
[ -n "$TIMEOUT_VIOLATIONS" ] && echo "⚠️  Llamadas sin timeout:" && echo "$TIMEOUT_VIOLATIONS"
BUSY_LOOPS=$(grep -rn "while True:" $ARCHIVOS 2>/dev/null || true)
if [ -n "$BUSY_LOOPS" ]; then
    C=$(echo "$BUSY_LOOPS" | wc -l | tr -d ' ')
    echo "⚠️  $C bucles 'while True' (verificar sleep/timeout)"
    echo "$BUSY_LOOPS"
fi
echo "✅ Rodillo 5 completado."
echo ""

# ======================================================================
# 🎛️ RODILLO 6: Seguridad
# ======================================================================
echo "🎛️  RODILLO 6: Blindaje perimetral..."
echo "$ARCHIVOS" | xargs -r bandit -f txt -ll 2>/dev/null || true
DEBUG_CHECK=$(grep -rn -E "debug\s*=\s*True|host\s*=\s*['\"]0\.0\.0\.0['\"]" $ARCHIVOS 2>/dev/null || true)
if [ -n "$DEBUG_CHECK" ]; then
    echo "🔴 Rodillo 6: CONFIGURACIÓN INSEGURA (0.0.0.0/debug)"
    echo "$DEBUG_CHECK"
    quarantine_files "security_violation"
    trigger_security_sandbox "Rodillo 6 fallido"
    exit 1
fi
echo "✅ Rodillo 6 completado."
echo ""

# ======================================================================
# 🏁 COMMIT + TAG + LIMPIEZA
# ======================================================================
echo "=============================================="
echo "  TUNELADORA: TODOS LOS RODILLOS SUPERADOS"
echo "=============================================="

find "$QUARANTINE_BASE" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
find "$LOG_DIR" -name "auto_cleanup_*.log" -mtime +30 -delete 2>/dev/null || true

git add $ARCHIVOS
if ! git diff --cached --quiet; then
    git commit -m "tuneladora: QA superado (${TIMESTAMP})" 2>/dev/null || true
    git tag "v${TIMESTAMP}" 2>/dev/null || true
    echo "✅ Commit y tag v${TIMESTAMP}"
else
    echo "✅ Sin cambios. Código ya limpio."
fi
echo ""
