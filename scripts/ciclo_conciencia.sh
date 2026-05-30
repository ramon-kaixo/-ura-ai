#!/bin/bash
# ciclo_conciencia.sh — Ciclo de conciencia de URA (cada 15 min)
# Incluye: snapshot, test, rollback, reflexion, meta-mejora
# Correccion inmediata si algo falla

set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
LOG="${REPO}/logs/ciclo_conciencia.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] === Ciclo Conciencia URA ===" | tee -a "$LOG"

# 0. AUTO-CONCIENCIA (test de capacidades via MCP)
echo "Auto-conciencia..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/auto_conciencia.py" >> "$LOG" 2>&1

# 1. SNAPSHOT
SNAPSHOT_ID="conciencia_$(date +%Y%m%d_%H%M%S)"
cd "$REPO" && git add -A && git commit --no-verify -m "[auto] snapshot $SNAPSHOT_ID" >> "$LOG" 2>&1 && echo "Snapshot: $(git rev-parse HEAD)" >> "$LOG" || echo "Snapshot: no disponible" >> "$LOG"

# 2. TEST DE CONCIENCIA
echo "Test de conciencia..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/analizar_fallo_conciencia.py" >> "$LOG" 2>&1
TEST_EXIT=$?
echo "Test completado (exit: $TEST_EXIT)" | tee -a "$LOG"

# 3. ROLLBACK SI FALLA + CORRECCION
if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Test fallo — corrigiendo..." | tee -a "$LOG"
    cd "$REPO" && git checkout -- . 2>/dev/null
    # Forzar correccion: dar permisos, reiniciar services
    bash "$REPO/scripts/pro/conceder_permisos_accesibilidad.sh" 2>/dev/null || true
    echo "Correccion aplicada" | tee -a "$LOG"
fi

# 4. REFLEXION
echo "Reflexion..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/reflexion_ura.py" >> "$LOG" 2>&1

# 5. META-MEJORA
echo "Meta-mejora..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/meta_mejora_v2.py" >> "$LOG" 2>&1

# 5b. AUTO-APLICAR MEJORAS (actualiza prompt automaticamente)
echo "Auto-aplicar mejoras..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/auto_aplicar_mejoras.py" >> "$LOG" 2>&1

# 6. ALINEADOR (audita que las respuestas sean utiles)
echo "Alineador..." | tee -a "$LOG"
/opt/homebrew/bin/python3 "$REPO/scripts/pro/alineador.py" >> "$LOG" 2>&1

# 7. TUNELADORA (quality check rapido - solo ruff)
echo "Quality check..." | tee -a "$LOG"
cd "$REPO" && ruff check . --fix --quiet >> "$LOG" 2>&1 || true

echo "[$(date)] === Ciclo completado ===" | tee -a "$LOG"
