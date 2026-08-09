#!/usr/bin/env bash
# pytest-delta — valida SOLO los tests relacionados con los archivos staged.
# Pre-commit hook (PLAN mutmut v5, F3): evita pasar archivos de código a
# pytest (que recolectaría 0 tests y bloquearía el commit con exit 5).
#
# Reglas de mapeo archivo -> tests:
#   test_*.py            -> el propio archivo
#   motor/core/x.py      -> tests de motor/core (motor/tests/) + tests/unit afines
#   core/x.py, knowledge/ -> tests/unit afines
# Sin tests relacionados -> se omite (no bloquea). Uso: pre-commit pasa los
# archivos staged como argumentos.

set -uo pipefail

REPO="/home/ramon/URA/ura_ia_1972"
PYTEST="$REPO/.venv/bin/python -m pytest"

if [ $# -eq 0 ]; then
    echo "pytest-delta: sin archivos staged — omitido"
    exit 0
fi

SELECTED=()
for f in "$@"; do
    case "$f" in
        */test_*.py)
            SELECTED+=("$f")
            ;;
        motor/core/*)
            SELECTED+=("motor/tests/test_motor_llm_state.py" "motor/tests/test_config.py" "tests/unit/test_core_lockfile_state.py")
            ;;
        motor/intelligence/*)
            SELECTED+=("tests/unit/test_agents_telemetry.py" "motor/tests/test_motor_llm_obs_state.py")
            ;;
        core/*|knowledge/*)
            SELECTED+=("tests/unit/test_properties.py" "tests/unit/test_hypothesis.py" "tests/unit/test_rules_hypothesis.py")
            ;;
    esac
done

if [ ${#SELECTED[@]} -eq 0 ]; then
    echo "pytest-delta: sin tests relacionados con los archivos tocados — omitido"
    exit 0
fi

# Deduplicar y filtrar los que existen
TARGETS=()
for t in "${SELECTED[@]}"; do
    if [ -f "$REPO/$t" ]; then
        TARGETS+=("$t")
    fi
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "pytest-delta: tests mapeados no existen en disco — omitido"
    exit 0
fi

echo "pytest-delta: corriendo ${#TARGETS[@]} test(s) relacionados"
cd "$REPO"
HYPOTHESIS_PROFILE=dev $PYTEST "${TARGETS[@]}" -q --tb=short -p no:cacheprovider
