#!/bin/bash
# restaurar.sh — restaura archivos críticos desde git si desaparecen
cd /home/ramon/URA/ura_ia_1972

ARCHIVOS=(
  "mochila_engine.py"
  "prompt_injector.py"
  "core/guardians/ast_sentinel.py"
  "core/guardians/__init__.py"
  "core/sandbox/docker_orchestrator.py"
  "core/sandbox/__init__.py"
  "core/cleaner/cold_refactor.py"
  "core/cleaner/__init__.py"
  "core/__init__.py"
  "cli/gatekeeper.py"
  "cli/__init__.py"
  "scripts/pro/gui_bridge.py"
  "scripts/pro/ejecutor_api.py"
  "scripts/sync_hetzner.sh"
  "run_tuneladora.py"
  "instalar_cron.sh"
  "test_mochila.py"
  "test_ast_sentinel.py"
  "test_prompt_injector.py"
)

RESTAURADOS=0
for f in "${ARCHIVOS[@]}"; do
  if [ ! -f "$f" ]; then
    git show HEAD:"$f" > "$f" 2>/dev/null && ((RESTAURADOS++))
  fi
done

[ $RESTAURADOS -gt 0 ] && echo "[$(date)] Restaurados $RESTAURADOS archivos" >> /tmp/ura_restore.log
exit 0
