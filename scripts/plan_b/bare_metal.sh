#!/bin/bash
set -euo pipefail
# Plan B — Ejecutar URA sin Docker (solo .venv + herramientas)
echo "🖥️ Plan B: Modo bare-metal (sin Docker)"
cd "${HOME}/URA/ura_ia_1972"
source .venv/bin/activate

# Verificar herramientas locales
for cmd in ruff pytest bandit radon vulture; do
    command -v "$cmd" >/dev/null && echo "  ✅ $cmd" || echo "  ⚠️  $cmd no instalado"
done

# Tuneladora sin Docker
ruff check . --fix --quiet 2>/dev/null || true
ruff format . --quiet 2>/dev/null || true
pytest tests/test_core_basics.py tests/test_consensus_system.py -q 2>/dev/null || true

echo "✅ Modo bare-metal: análisis completado"
