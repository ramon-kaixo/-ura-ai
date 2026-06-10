#!/bin/bash
# guard_mochila.sh — Restaura archivos mochila borrados por FS bug
# Disparado por ura-mochila-guard.timer cada 5 min
REPO="/home/ramon/URA/ura_ia_1972"
cd "$REPO" || exit 0

MOCHILA_FILES=(
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
)

restored=0
for f in "${MOCHILA_FILES[@]}"; do
  if [ ! -f "$REPO/$f" ]; then
    git checkout HEAD -- "$f" 2>/dev/null
    if [ -f "$REPO/$f" ]; then
      restored=$((restored + 1))
    fi
  fi
done

if [ "$restored" -gt 0 ]; then
  logger -t mochila-guard "Restaurados $restored archivos mochila"
  # Si se restauró mochila_server, reiniciar el servicio
  if [ ! -f "$REPO/core/mochila/mochila_server.py" ] && [ "$restored" -gt 0 ]; then
    sudo systemctl restart ura-mochila.service 2>/dev/null || true
  fi
fi
