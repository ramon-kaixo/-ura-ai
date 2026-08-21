#!/bin/bash
# Sandbox de mutación URA: prueba el gate en un clon aislado antes del entorno real.
# Uso: bash scripts/sandbox_mutation.sh [--rapido]
#   --rapido: solo 1 módulo (path_setup) para validar el entorno en ~1 min.

set -u
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SANDBOX="/tmp/ura_mutation_sandbox"
RAPIDO="${1:-}"

echo "[sandbox] Exportando árbol de trabajo en $SANDBOX ..."
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX"
tar -C "$RAIZ" --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='.coverage*' --exclude='coverage' --exclude='htmlcov' \
    -cf - . | tar -xf - -C "$SANDBOX" || {
    echo "ERROR: no se pudo exportar el árbol de trabajo"; exit 1;
}

echo "[sandbox] Creando venv limpio e instalando dependencias de mutación ..."
python3 -m venv "$SANDBOX/.venv-mutacion"
"$SANDBOX/.venv-mutacion/bin/pip" install -q \
    pytest pytest-gremlins pytest-rerunfailures pytest-timeout pytest-instafail coverage || {
    echo "ERROR: instalación en sandbox falló"; exit 1;
}

TARGETS="core/guardian_disco.py,core/stealth_fetcher.py,core/guardians/ast_sentinel.py,core/path_setup.py,core/mochila/status_endpoint.py,core/mochila/vram_scheduler.py,core/mochila/providers/base.py"
TESTS="tests/unit/test_ast_sentinel.py tests/unit/test_cold_refactor.py tests/unit/test_core_guardians_mochila_cobertura.py tests/unit/test_guardian_disco.py tests/unit/test_guardian_middleware_path.py tests/unit/test_mochila_adapter_cobertura.py tests/unit/test_mochila_infra.py tests/unit/test_mochila_provider_ollama.py tests/unit/test_mochila_providers_clonados.py tests/unit/test_mochila_providers_openrouter_gemini.py tests/unit/test_mochila_routes_models_status.py tests/unit/test_mochila_vram_scheduler.py tests/unit/test_path_setup.py tests/unit/test_stealth_fetcher.py"
if [ "$RAPIDO" = "--rapido" ]; then
    TARGETS="core/path_setup.py"
    TESTS="tests/unit/test_path_setup.py tests/unit/test_guardian_middleware_path.py"
fi

echo "[sandbox] Ejecutando gate de mutación aislado ..."
export PYTEST_GREMLINS_MAP_TIMEOUT=3600
PYTHONPATH="$RAIZ/scripts/pro" "$SANDBOX/.venv-mutacion/bin/python" -m pytest -q \
    -p pytest_gremlins_ura_patch --gremlins --gremlin-executor=subprocess \
    --gremlin-targets="$TARGETS" --gremlin-report=json $TESTS
RC=$?

if [ $RC -eq 0 ]; then
    echo "[sandbox] SANDBOX OK — entorno validado; procede gate real."
else
    echo "[sandbox] SANDBOX FALLÓ (rc=$RC) — NO lanzar gate real hasta corregir."
fi
exit $RC
