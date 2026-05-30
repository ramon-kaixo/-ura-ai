#!/bin/bash
# ciclo_mejora_6h.sh – Orquesta los 5 agentes de mejora continua cada 6 horas
set -e

LOG="/opt/ura/logs/mejora_continua/ciclo.log"
echo "[$(date)] === Inicio ciclo de mejora continua (6h) ===" | tee -a "$LOG"
/opt/ura/scripts/notificar.sh "🔄 Ciclo de mejora continua iniciado"

# 0. Asegurar entorno Python
/opt/ura/scripts/ensure_environment.sh >> "$LOG" 2>&1

# 0a. SNAPSHOT PRE-TEST (guardar estado actual)
SNAPSHOT_ID="pre_conciencia_$(date +%Y%m%d_%H%M%S)"
echo "[$(date)] Snapshot pre-test: $SNAPSHOT_ID" | tee -a "$LOG"
cd /Users/ramonesnaola/URA/ura_ia_1972 && git add -A && git commit --no-verify -m "snapshot $SNAPSHOT_ID" >> "$LOG" 2>&1 && SNAPSHOT_HASH=$(git rev-parse HEAD) && echo "Snapshot: $SNAPSHOT_HASH" >> "$LOG" || echo "Snapshot no disponible (git)" >> "$LOG"

# 0b. Test de conciencia (autoevaluación URA)
echo "[$(date)] Test de conciencia URA..." | tee -a "$LOG"
/opt/homebrew/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/analizar_fallo_conciencia.py >> "$LOG" 2>&1
TEST_EXIT=$?
echo "[$(date)] Test de conciencia completado (exit: $TEST_EXIT)" | tee -a "$LOG"

# 0c. Si el test modifico algo, restaurar estado (rollback)
if [ "$TEST_EXIT" -ne 0 ]; then
    echo "[$(date)] Test fallo — restaurando snapshot..." | tee -a "$LOG"
    cd /Users/ramonesnaola/URA/ura_ia_1972 && git checkout -- . 2>/dev/null && echo "Rollback completado" >> "$LOG"
    # Restaurar prompt de URA si se modifico
    /opt/homebrew/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/ura_self_modify.py leer_prompt | head -3 >> "$LOG" 2>/dev/null
fi

# 0d. Validacion del sistema
/opt/homebrew/bin/python3 /opt/ura/agents/validador_sistema.py >> "$LOG" 2>&1

# 1. Reconstruir sandbox Docker (datos frescos de producción)
/opt/ura/scripts/sandbox_docker.sh >> "$LOG" 2>&1

# 2. Auto-fix de código (ruff --fix en archivos recientes)
/opt/homebrew/bin/python3 /opt/ura/scripts/auto_fix_code.py >> "$LOG" 2>&1

# 3. Análisis estático de código (ruff + bandit + radon + vulture)
/opt/homebrew/bin/python3 /opt/ura/agents/arquitecto_codigo.py >> "$LOG" 2>&1

# 4. Escaneo de dependencias (pip-audit)
/opt/ura/scripts/escanear_dependencias.sh >> "$LOG" 2>&1

# 5. Agente mutador (mejora_continua.py — mutaciones + benchmark + parches)
/opt/homebrew/bin/python3 /opt/ura/agents/mejora_continua.py >> "$LOG" 2>&1

# 6. Recolector de métricas multidimensionales
/opt/homebrew/bin/python3 /opt/ura/scripts/metrics_collector.py >> "$LOG" 2>&1

# 7. Sugeridor RL (entrena modelo con historial de mejoras + versionado)
/opt/homebrew/bin/python3 /opt/ura/agents/rl_suggester.py >> "$LOG" 2>&1

# 8. Canary deployer (tests + parches en bar_san_gregorio)
/opt/homebrew/bin/python3 /opt/ura/agents/canary_deployer.py >> "$LOG" 2>&1

# 9. Despliegue a producción (aplica parches validados)
/opt/homebrew/bin/python3 /opt/ura/agents/deploy_patches.py >> "$LOG" 2>&1

# 10. Git: crear rama con cambios de auto-fix
/opt/ura/scripts/git_auto_branch.sh >> "$LOG" 2>&1

# 11. Reflexion post-accion (URA evalua su desempeno)
echo "[$(date)] Reflexion URA..." | tee -a "$LOG"
/opt/homebrew/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/reflexion_ura.py >> "$LOG" 2>&1

# 12. Meta-mejora (URA sugiere cambios en su propio prompt)
echo "[$(date)] Meta-mejora URA..." | tee -a "$LOG"
/opt/homebrew/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/meta_mejora.py >> "$LOG" 2>&1

/opt/ura/scripts/notificar.sh "✅ Ciclo de mejora continua finalizado"
echo "[$(date)] === Ciclo finalizado ===" | tee -a "$LOG"
