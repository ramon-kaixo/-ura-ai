#!/bin/bash
set -euo pipefail
# test_regression.sh — Tests de regresion para buzos clave
MALETA="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/buzos/maleta.json"
BUZOS_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/buzos"
OUTPUT_DIR="/tmp/ura_regression"
PASS=0; FAIL=0
mkdir -p "$OUTPUT_DIR"

echo "🧪 Tests de Regresion — $(date)"
echo "═══════════════════════════════════"

# Lista de buzos y campos esperados (bash 3.2 compatible)
test_buzo() {
    local name="$1" fields="$2"
    local script="${BUZOS_DIR}/buzo_${name}.sh"
    local out="${OUTPUT_DIR}/regression_${name}.json"
    printf "   ▶️  %-20s" "$name"
    [ ! -f "$script" ] && echo "⏩ no existe" && return
    if timeout 30 bash "$script" "$MALETA" "$out" 2>/dev/null; then
        if jq -e 'type == "array" and length > 0' "$out" >/dev/null 2>&1; then
            local ok=true
            for f in $(echo "$fields" | tr ',' ' '); do
                jq -e ".[0] | has(\"$f\")" "$out" >/dev/null 2>&1 || { ok=false; break; }
            done
            if [ "$ok" = true ]; then
                echo "✅ $(jq 'length' "$out") items"
                PASS=$((PASS + 1))
            else
                echo "🔴 estructura"
                FAIL=$((FAIL + 1))
            fi
        else
            echo "🟡 sin datos"
        fi
    else
        echo "🔴 timeout/error"
        FAIL=$((FAIL + 1))
    fi
}

test_buzo "tendencias" "titulo,url"
test_buzo "modelos" "modelo,ubicacion"
test_buzo "red" "ip,metrica"
test_buzo "economia" "titulo,url"
test_buzo "bares_espana" "ciudad,nombre"
test_buzo "practicas" "titulo,url"

echo "═══════════════════════════════════"
echo "   ✅ $PASS pasados  🔴 $FAIL fallados"
exit $FAIL
