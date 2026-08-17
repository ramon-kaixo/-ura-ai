#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

# Usar el venv si existe (ruff/mypy/pytest/coverage no están garantizados en PATH).
if [ -x "$REPO/.venv/bin/ruff" ]; then
    export PATH="$REPO/.venv/bin:$PATH"
fi

echo "==> Guardián de protocolo (verify_protocol.py)"
python3 scripts/pro/verify_protocol.py

echo "==> Ruff"
ruff check .

echo "==> Mypy (sin caché)"
mypy --no-incremental core motor shared

echo "==> Pytest + Cobertura (una sola corrida; umbral >=80% en módulos nuevos)"
RC="$(mktemp)"
printf '[run]\nsource = motor.core.interfaces, motor.core.web_search, scripts.pro.panel\nbranch = False\nomit =\n    tests/*\n\n[report]\nshow_missing = True\n' > "$RC"
trap 'rm -f "$RC"' EXIT

python3 -m coverage run --rcfile="$RC" -m pytest -q --tb=short
python3 -m coverage report -m --rcfile="$RC"

MODULOS_OK=1
for modulo in \
    "motor/core/interfaces" \
    "motor/core/web_search.py" \
    "scripts/pro/panel.py"; do
    cover=$(python3 -m coverage report --rcfile="$RC" | awk -v m="$modulo" '$1 == m {gsub("%", "", $4); print $4}')
    cover_num="${cover:-0}"
    if awk "BEGIN {exit !($cover_num >= 80)}"; then
        echo "  $modulo: ${cover_num}% OK"
    else
        echo "  $modulo: ${cover_num}% — POR DEBAJO DEL 80%" >&2
        MODULOS_OK=0
    fi
done
if [ "$MODULOS_OK" -ne 1 ]; then
    echo "ERROR: cobertura <80% en módulos nuevos" >&2
    exit 1
fi

echo "==> Todos los gates pasaron"
