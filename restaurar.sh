#!/bin/bash
cd /home/ramon/URA/ura_ia_1972 || exit 1
ARCHIVOS=(
  mochila_engine.py prompt_injector.py
  core/__init__.py core/guardians/__init__.py core/guardians/ast_sentinel.py
  core/sandbox/__init__.py core/sandbox/docker_orchestrator.py
  core/cleaner/__init__.py core/cleaner/cold_refactor.py
  cli/__init__.py cli/gatekeeper.py
  scripts/pro/gui_bridge.py scripts/pro/ejecutor_api.py scripts/sync_hetzner.sh
  run_tuneladora.py instalar_cron.sh
  test_mochila.py test_ast_sentinel.py test_prompt_injector.py
)
R=0
for f in "${ARCHIVOS[@]}"; do
  if [ ! -f "$f" ]; then
    sudo chattr -i "$f" 2>/dev/null || true
    git show HEAD:"$f" > "$f" 2>/dev/null && ((R++))
  fi
  sudo chattr +i "$f" 2>/dev/null || true
done
# Keep ura-edit and self unlocked for editing
sudo chattr -i ura-edit restaurar.sh 2>/dev/null || true
[ $R -gt 0 ] && echo "[$(date)] Restaurados $R archivos" >> /tmp/ura_restore.log
exit 0
