#!/bin/bash
# restaurar.sh — Restaura archivos criticos borrados por el FS bug
# Ejecutar como ExecStartPre en servicios systemd o manualmente
# Uso: bash scripts/restaurar.sh

REPO="/home/ramon/URA/ura_ia_1972"
cd "$REPO" || exit 1

log() { echo "[restaurar] $*"; }
ERR=0

# Archivos con chattr +i que deben existir siempre
CRITICOS=(
  "AGENTS.md"
  "PLAN_MAESTRO.md"
  "requirements.txt"
  "mochila_engine.py"
  "memoria_fallos.py"
  "memoria_movimiento.py"
  "prompt_injector.py"
  "ura-audit"
  "ura-contexto"
  ".analisis.sh"
  "core/guardian_openclaw.py"
  "core/change_guardian.py"
  "core/guardians/ast_sentinel.py"
  "core/sandbox/docker_orchestrator.py"
  "core/cleaner/cold_refactor.py"
  "core/utils/anonymizer.py"
  "core/code_indexer.py"
  "core/open_claw_coordinador.py"
  "core/open_claw_reporte.py"
  "cli/gatekeeper.py"
  "cli/__init__.py"
  "config/settings.json"
  "app/main.py"
  "app/capturador.py"
  "app/gestor_archivos.py"
  "app/flujo_constante.py"
  "app/motor_flujo.py"
  "scripts/pro/ejecutor_api.py"
  "scripts/pro/captura_virtual.py"
  "scripts/pro/guardian_tmpfs.sh"
  "scripts/pro/auditoria_comite.sh"
  "scripts/pro/ura_ojos.sh"
  "scripts/pro/uitars_gx10.py"
  "tests/test_properties.py"
  "tests/test_unit.py"
  "tests/test_anonymizer.py"
  "tests/test_seguridad_paths.py"
  "docs/CONTEXTO_SESION_2026-06-09.md"
  "$HOME/.openclaw/openclaw.json"
  "core/mochila/__init__.py"
  "core/mochila/circuit_breaker.py"
  "core/mochila/cost_tracker.py"
  "core/mochila/mochila_server.py"
  "core/mochila/rate_limiter.py"
  "core/mochila/router.py"
  "core/mochila/tools.py"
  "core/mochila/providers/__init__.py"
  "core/mochila/providers/base.py"
  "core/mochila/providers/gemini.py"
  "core/mochila/providers/ollama.py"
  "core/mochila/providers/openrouter.py"
  "tests/test_mochila.py"
  "core/memoria/__init__.py"
  "core/memoria/detector.py"
  "core/memoria/ficha.py"
  "core/memoria/ingesto.py"
)

for f in "${CRITICOS[@]}"; do
  full="$REPO/$f"
  if [ ! -f "$full" ]; then
    log "FALTANTE: $f — restaurando desde git..."
    git checkout HEAD -- "$f" 2>/dev/null
    if [ -f "$full" ]; then
      log "  restaurado OK"
      sudo chattr +i "$full" 2>/dev/null
    else
      log "  ERROR: no se pudo restaurar (buscar en commits anteriores)"
      git log --oneline -- "$f" 2>/dev/null | head -3 || true
      ERR=1
    fi
  fi
done

# Restaurar archivos trackeados que falten (no solo criticos)
git ls-files 2>/dev/null | while IFS= read -r tf; do
  if [ ! -f "$REPO/$tf" ]; then
    log "FALTANTE NO CRITICO: $tf — restaurando..."
    git checkout HEAD -- "$tf" 2>/dev/null && sudo chattr +i "$REPO/$tf" 2>/dev/null
  fi
done

log "restaurar.sh completado. Errores: $ERR"
exit $ERR
