#!/bin/bash
# Gate de mutation testing URA — pytest-gremlins (sustituye a mutmut).
# Config versionada: pyproject.toml [tool.mutacion]
# Umbral dinámico: docs/udo/mutation_threshold.json (90 -> 95 -> 100)
#
# Score = (zapped + timeout) / (total - pardoned) * 100
#   (timeout cuenta como detectado: los tests nunca pasan con el mutante;
#    pardoned = equivalentes documentados con pragma auditable).
#
# Flujo: gate -> dashboard -> análisis supervivientes.
# Falla si score < objetivo actual; si lo supera, el objetivo sube automáticamente.

set -u
cd "$(dirname "$0")/.."
RAIZ="$(pwd)"
PY=".venv/bin/python"

CONFIG_TOTALS() { :; }

TARGETS="core/guardian_disco.py,core/stealth_fetcher.py,core/guardians/ast_sentinel.py,core/path_setup.py,core/mochila/status_endpoint.py,core/mochila/vram_scheduler.py,core/mochila/providers/base.py"
TEST_FILES="tests/unit/test_ast_sentinel.py tests/unit/test_cold_refactor.py tests/unit/test_core_guardians_mochila_cobertura.py tests/unit/test_guardian_disco.py tests/unit/test_guardian_middleware_path.py tests/unit/test_mochila_adapter_cobertura.py tests/unit/test_mochila_infra.py tests/unit/test_mochila_provider_ollama.py tests/unit/test_mochila_providers_clonados.py tests/unit/test_mochila_providers_openrouter_gemini.py tests/unit/test_mochila_routes_models_status.py tests/unit/test_mochila_vram_scheduler.py tests/unit/test_path_setup.py tests/unit/test_stealth_fetcher.py"
UMBRAL_ESTADO="$RAIZ/docs/udo/mutation_threshold.json"

OBJETIVO=$($PY -c "
import json
try:
    print(json.load(open('$UMBRAL_ESTADO'))['objetivo'])
except Exception:
    print(90)
")

PASOS=(95 100)
SIGUIENTE=100
for p in "${PASOS[@]}"; do
    if [ "$p" -gt "$OBJETIVO" ]; then SIGUIENTE=$p; break; fi
done

echo "[gate] Objetivo actual: ${OBJETIVO}% (siguiente escalón: ${SIGUIENTE}%)"
export PYTEST_GREMLINS_MAP_TIMEOUT=3600
INICIO=$(date +%s)

PYTHONPATH="$RAIZ/scripts/pro" $PY -m pytest -q \
    -p pytest_gremlins_ura_patch \
    --gremlins \
    --gremlin-executor=subprocess \
    --gremlin-targets="$TARGETS" \
    --gremlin-report=json \
    $TEST_FILES || {
    echo "GATE FAIL: pytest gremlins terminó con error (rc≠0)."
    exit 1
}
FIN=$(date +%s); TIEMPO=$((FIN-INICIO))

$PY - <<EOF
import json, sys
from pathlib import Path

resumen = json.load(open("$RAIZ/coverage/gremlins/gremlins.json"))["summary"]
total, zapped = resumen["total"], resumen["zapped"]
survived, timeout = resumen.get("survived", 0), resumen.get("timeout", 0)
pardoned, errores = resumen.get("pardoned", 0), resumen.get("error", 0)
base = max(total - pardoned, 1)
score = round(100.0 * (zapped + timeout) / base, 2)
objetivo = int("${OBJETIVO}")
siguiente = int("${SIGUIENTE}")

print(f"[gate] mutantes={total} zapped={zapped} survived={survived} "
      f"timeout={timeout} pardoned={pardoned} -> score={score}% (objetivo={objetivo}%)")
Path("$RAIZ/docs/udo").mkdir(parents=True, exist_ok=True)
json.dump(resumen, open("$RAIZ/coverage/gremlins/last_summary.json", "w"))
if score < objetivo:
    print(f"GATE FAIL: score {score}% < objetivo {objetivo}%.")
    sys.exit(1)

if score >= siguiente and siguiente > objetivo:
    Path("$UMBRAL_ESTADO").write_text(
        json.dumps({"objetivo": siguiente}, indent=2) + "\n", encoding="utf-8")
    print(f"[gate] ¡Objetivo superado! Umbral sube automáticamente a {siguiente}%.")
sys.exit(0)
EOF
RC_GATE=$?

python3 "$RAIZ/scripts/update_mutation_dashboard.py" \
    --total $($PY -c "import json;print(json.load(open('$RAIZ/coverage/gremlins/last_summary.json'))['total'])") \
    --zapped $($PY -c "import json;print(json.load(open('$RAIZ/coverage/gremlins/last_summary.json'))['zapped'])") \
    --survived $($PY -c "import json;print(json.load(open('$RAIZ/coverage/gremlins/last_summary.json')).get('survived',0))") \
    --timeout $($PY -c "import json;print(json.load(open('$RAIZ/coverage/gremlins/last_summary.json')).get('timeout',0))") \
    --pardoned $($PY -c "import json;print(json.load(open('$RAIZ/coverage/gremlins/last_summary.json')).get('pardoned',0))") \
    --tiempo "$TIEMPO" || true

$PY "$RAIZ/scripts/analyze_survivors.py" --fail-on-unresolved || true

exit $RC_GATE
