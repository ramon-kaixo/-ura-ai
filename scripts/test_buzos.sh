#!/bin/bash
set -euo pipefail
# test_buzos.sh — Test estructural de los 21 buzos del Enjambre
MALETA="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/buzos/maleta.json"
BUZOS_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/buzos"
OUTPUT_DIR="/tmp/ura_test_buzos"
PASS=0; FAIL=0
mkdir -p "$OUTPUT_DIR"

echo "🧪 Test estructural de buzos — $(date)"
echo "═══════════════════════════════════════"

for buzo_script in "$BUZOS_DIR"/buzo_*.sh; do
    buzo_name=$(basename "$buzo_script" .sh)
    output_file="${OUTPUT_DIR}/test_${buzo_name}.json"
    printf "   ▶️  %-30s" "$buzo_name"
    if timeout 30 bash "$buzo_script" "$MALETA" "$output_file" 2>/dev/null; then
        if jq -e 'type == "array"' "$output_file" >/dev/null 2>&1; then
            COUNT=$(jq 'length' "$output_file" 2>/dev/null || echo 0)
            echo "✅ JSON ($COUNT)"
            PASS=$((PASS + 1))
        else
            echo "🔴 JSON invalido"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "🔴 timeout/error"
        FAIL=$((FAIL + 1))
    fi
done
echo "═══════════════════════════════════════"
echo "   ✅ $PASS pasados | 🔴 $FAIL fallados"
[ "$FAIL" -eq 0 ] || exit 1
