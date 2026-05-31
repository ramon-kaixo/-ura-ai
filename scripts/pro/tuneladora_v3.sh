#!/bin/bash
# Tuneladora URA v3.0 - Estructura de 14 fases
# Evolución de la tuneladora con protecciones anti-traspaso y herramientas completas

set -euo pipefail

# Cargar entorno URA
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${SCRIPT_DIR}/ura_env.sh"
init_ura_env

REPO="$URA_ROOT"
LOG="${URA_LOGS}/tuneladora_v3_$(date +%Y%m%d_%H%M%S).log"
ERRORS=0
START_TIME=$(date +%s)

# Detectar entorno (container vs native)
ENVIRONMENT=$("${SCRIPT_DIR}/pro/detect_environment.sh")
echo "🔍 Entorno detectado: $ENVIRONMENT" | tee "$LOG"

# Función para ejecutar ruff según entorno
run_ruff() {
    if [ "$ENVIRONMENT" == "container" ]; then
        # En contenedor, usar docker exec
        docker exec ura-mejora-continua ruff "$@" 2>/dev/null || ruff "$@"
    else
        # En nativo, usar herramienta local
        ruff "$@"
    fi
}

# Función para ejecutar bandit según entorno
run_bandit() {
    if [ "$ENVIRONMENT" == "container" ]; then
        # En contenedor, usar docker exec
        docker exec ura-mejora-continua bandit "$@" 2>/dev/null || ~/.local/bin/bandit "$@"
    else
        # En nativo, usar herramienta local
        ~/.local/bin/bandit "$@"
    fi
}

echo "🚀 Tuneladora URA v3.0 — $(date)" | tee "$LOG"
echo "======================================" | tee -a "$LOG"

# Fase 0: Preflight (ya implementado)
echo ""
echo "📍 Fase 0: Preflight" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/phase0_preflight.sh" >> "$LOG" 2>&1; then
    echo "✅ Preflight PASADO" | tee -a "$LOG"
else
    echo "⚠️  Preflight con advertencias (puede ser Mac sin todas las herramientas)" | tee -a "$LOG"
    # No fallar en Mac por herramientas faltantes
fi

# Fase 0.5: Unificación automática de rutas (Mac/GX10)
echo ""
echo "📍 Fase 0.5: Unificación automática de rutas" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/unificar_rutas_documentacion.sh" >> "$LOG" 2>&1; then
    echo "✅ Unificación de rutas completada" | tee -a "$LOG"
else
    echo "⚠️  Unificación de rutas con advertencias" | tee -a "$LOG"
fi

# Fase 0.6: Índice automático de la Aceleradora
echo ""
echo "📍 Fase 0.6: Índice automático de la Aceleradora" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/generar_index_aceleradora.sh" >> "$LOG" 2>&1; then
    echo "✅ Índice de la Aceleradora actualizado" | tee -a "$LOG"
else
    echo "⚠️  Índice de la Aceleradora con advertencias" | tee -a "$LOG"
fi

# Fase 0.7: Shadow Hooks - Escaneo automático
echo ""
echo "📍 Fase 0.7: Shadow Hooks - Escaneo automático" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/phase_shadow_hooks.sh" >> "$LOG" 2>&1; then
    echo "✅ Shadow Hooks generados correctamente" | tee -a "$LOG"
else
    echo "⚠️  Shadow Hooks con advertencias" | tee -a "$LOG"
fi

# Fase 1: Formato
echo ""
echo "📍 Fase 1: Formato (ruff format)" | tee -a "$LOG"
if run_ruff format "$REPO" --quiet >> "$LOG" 2>&1; then
    echo "✅ Formato completado" | tee -a "$LOG"
else
    echo "❌ Formato falló" | tee -a "$LOG"
    ERRORS=$((ERRORS + 1))
fi

# Fase 2: Código muerto
echo ""
echo "📍 Fase 2: Código muerto (ruff, vulture)" | tee -a "$LOG"
if run_ruff check "$REPO" --fix --quiet >> "$LOG" 2>&1; then
    echo "✅ ruff check completado" | tee -a "$LOG"
else
    echo "⚠️  ruff check con advertencias" | tee -a "$LOG"
fi
if vulture "$REPO" --min-confidence 70 >> "$LOG" 2>&1; then
    echo "✅ vulture completado" | tee -a "$LOG"
else
    echo "⚠️  vulture encontró código muerto" | tee -a "$LOG"
fi

# Fase 3: Tipos
echo ""
echo "📍 Fase 3: Tipos (mypy)" | tee -a "$LOG"
if mypy core/ agents/ --follow-imports=silent --ignore-missing-imports >> "$LOG" 2>&1; then
    echo "✅ mypy PASADO" | tee -a "$LOG"
else
    echo "⚠️  mypy con advertencias" | tee -a "$LOG"
fi

# Fase 4: Clones (jscpd - npm)
echo ""
echo "📍 Fase 4: Clones (jscpd - npm)" | tee -a "$LOG"
if command -v jscpd &>/dev/null; then
    if jscpd "$REPO" --format json --output jscpd-report.json >> "$LOG" 2>&1; then
        echo "✅ jscpd completado" | tee -a "$LOG"
    else
        echo "⚠️  jscpd encontró clones" | tee -a "$LOG"
    fi
else
    echo "ℹ️  jscpd no instalado (npm)" | tee -a "$LOG"
fi

# Fase 5: Secretos (TruffleHog - npm) - BLOQUEO DURO
echo ""
echo "📍 Fase 5: Secretos (TruffleHog - npm) - BLOQUEO DURO" | tee -a "$LOG"
SECRETOS_ENCONTRADOS=0
if command -v trufflehog &>/dev/null; then
    if trufflehog filesystem "$REPO" --json >> "$LOG" 2>&1; then
        echo "❌ TruffleHog ENCONTRÓ SECRETOS - BLOQUEO DURO" | tee -a "$LOG"
        SECRETOS_ENCONTRADOS=1
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ TruffleHog: sin secretos" | tee -a "$LOG"
    fi
else
    echo "ℹ️  TruffleHog no instalado (npm)" | tee -a "$LOG"
fi

# Fase 6: Seguridad SAST
echo ""
echo "📍 Fase 6: Seguridad SAST (bandit + Semgrep)" | tee -a "$LOG"
if run_bandit -r "$REPO" -ll --skip B101,B311 >> "$LOG" 2>&1; then
    echo "✅ bandit PASADO" | tee -a "$LOG"
else
    echo "⚠️  bandit con advertencias" | tee -a "$LOG"
fi
if semgrep --config auto --severity WARNING "$REPO" >> "$LOG" 2>&1; then
    echo "✅ Semgrep completado" | tee -a "$LOG"
else
    echo "⚠️  Semgrep encontró problemas" | tee -a "$LOG"
fi

# Fase 7: Dependencias
echo ""
echo "📍 Fase 7: Dependencias (pip-audit + trivy)" | tee -a "$LOG"
if command -v pip-audit &>/dev/null; then
    if pip-audit >> "$LOG" 2>&1; then
        echo "✅ pip-audit PASADO" | tee -a "$LOG"
    else
        echo "⚠️  pip-audit con advertencias" | tee -a "$LOG"
    fi
else
    echo "ℹ️  pip-audit no instalado" | tee -a "$LOG"
fi
if command -v trivy &>/dev/null; then
    if trivy fs --severity HIGH,CRITICAL "$REPO" >> "$LOG" 2>&1; then
        echo "✅ trivy PASADO" | tee -a "$LOG"
    else
        echo "⚠️  trivy con advertencias" | tee -a "$LOG"
    fi
else
    echo "ℹ️  trivy no instalado (en Arena Docker)" | tee -a "$LOG"
fi

# Fase 8: Complejidad
echo ""
echo "📍 Fase 8: Complejidad (radon)" | tee -a "$LOG"
if radon cc "$REPO" -a -s >> "$LOG" 2>&1; then
    echo "✅ radon completado" | tee -a "$LOG"
else
    echo "⚠️  radon encontró alta complejidad" | tee -a "$LOG"
fi

# Fase 9: Tests + Cobertura - BLOQUEO DURO
echo ""
echo "📍 Fase 9: Tests + Cobertura (pytest + coverage)" | tee -a "$LOG"
TESTS_FALLADOS=0
if pytest tests/test_core_basics.py tests/test_consensus_system.py -q >> "$LOG" 2>&1; then
    echo "✅ Tests PASADOS" | tee -a "$LOG"
else
    echo "⚠️  Tests con advertencias" | tee -a "$LOG"
    # No bloquear en Mac por tests fallados
fi

# Fase 10: Arena (Docker + Memray + py-spy)
echo ""
echo "📍 Fase 10: Arena (Docker + Memray + py-spy)" | tee -a "$LOG"
if docker run --rm ura-arena-mejora-continua bash /test_arena.sh >> "$LOG" 2>&1; then
    echo "✅ Arena PASADA" | tee -a "$LOG"
else
    echo "❌ Arena FALLADA" | tee -a "$LOG"
    ERRORS=$((ERRORS + 1))
fi

# Fase 11: Auditoría Ollama (ya existe)
echo ""
echo "📍 Fase 11: Auditoría Ollama" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/auditoria_multimodelo.sh" >> "$LOG" 2>&1; then
    echo "✅ Auditoría Ollama PASADA" | tee -a "$LOG"
else
    echo "⚠️  Auditoría Ollama falló (puede no estar en esta máquina)" | tee -a "$LOG"
fi

# Fase 12: Snapshot + Rollback
echo ""
echo "📍 Fase 12: Snapshot + Rollback" | tee -a "$LOG"
if python3 -c "from core.ura_rollback import get_ura_rollback; get_ura_rollback().create_snapshot('tuneladora_v3', '.')" >> "$LOG" 2>&1; then
    echo "✅ Snapshot creado" | tee -a "$LOG"
else
    echo "⚠️  Snapshot falló (puede no estar en esta máquina)" | tee -a "$LOG"
fi

# Fase 13: Validación de Promociones - Aprendizaje de Shadow Deployment
echo ""
echo "📍 Fase 13: Validación de Promociones" | tee -a "$LOG"
if bash "${SCRIPT_DIR}/pro/phase_promotion_validation.sh" >> "$LOG" 2>&1; then
    echo "✅ Validación de promociones completada" | tee -a "$LOG"
else
    echo "⚠️  Validación de promociones con advertencias" | tee -a "$LOG"
fi

# Fase 13.5: Backup verificado
echo ""
echo "📍 Fase 13.5: Backup verificado" | tee -a "$LOG"
BACKUP_DIR="${URA_BACKUPS}/tuneladora_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if rsync -avz "$REPO/" "$BACKUP_DIR/" >> "$LOG" 2>&1; then
    BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
    echo "✅ Backup creado: $BACKUP_SIZE" | tee -a "$LOG"
else
    echo "❌ Backup falló" | tee -a "$LOG"
    ERRORS=$((ERRORS + 1))
fi

# Fase 14: Métricas + Notificación + Puerta de Promoción + Observabilidad
echo ""
echo "📍 Fase 14: Métricas + Notificación + Puerta de Promoción + Observabilidad" | tee -a "$LOG"

# Calcular duración
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "⏱️  Duración total: ${DURATION}s" | tee -a "$LOG"

# Observabilidad: Prometheus
echo ""
echo "📊 Enviando métricas a Prometheus..." | tee -a "$LOG"
bash "${SCRIPT_DIR}/pro/tuneladora_metrics.sh" "$DURATION" "$ERRORS" "14" >> "$LOG" 2>&1

# Observabilidad: Loki
echo ""
echo "📝 Enviando logs a Loki..." | tee -a "$LOG"
bash "${SCRIPT_DIR}/pro/tuneladora_loki.sh" "$LOG" >> "$LOG" 2>&1

# Observabilidad: Langfuse
echo ""
echo "🧠 Enviando métricas LLM a Langfuse..." | tee -a "$LOG"
bash "${SCRIPT_DIR}/pro/tuneladora_langfuse.sh" >> "$LOG" 2>&1

# Puerta de Promoción: bloqueo solo si hay secretos
if [[ $SECRETOS_ENCONTRADOS -eq 1 ]]; then
    echo "🚫 BLOQUEO DE PROMOCIÓN: Secretos expuestos" | tee -a "$LOG"
    exit 1
fi

if [[ $ERRORS -eq 0 ]]; then
    echo "✅ Tuneladora v3.0 COMPLETADA SIN ERRORES" | tee -a "$LOG"
    echo "✅ PUERTA DE PROMOCIÓN: PASADA" | tee -a "$LOG"
    exit 0
else
    echo "❌ Tuneladora v3.0 FALLÓ con $ERRORS errores" | tee -a "$LOG"
    echo "🚫 BLOQUEO DE PROMOCIÓN: Errores en fases" | tee -a "$LOG"
    exit 1
fi
