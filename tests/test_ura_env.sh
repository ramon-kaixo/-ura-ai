#!/bin/bash
# Test de ura_env.sh - Verifica que detecta correctamente la máquina

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/scripts/ura_env.sh"
init_ura_env

echo "=== Test URA Environment ==="

# Test 1: URA_ROOT está definido
if [[ -z "$URA_ROOT" ]]; then
    echo "❌ FAIL: URA_ROOT no está definido"
    exit 1
fi
echo "✅ URA_ROOT definido: $URA_ROOT"

# Test 2: URA_ROOT existe
if [[ ! -d "$URA_ROOT" ]]; then
    echo "❌ FAIL: URA_ROOT no existe: $URA_ROOT"
    exit 1
fi
echo "✅ URA_ROOT existe"

# Test 3: Subdirectorios definidos
for var in URA_AGENTS URA_SCRIPTS URA_CONFIG URA_DATA URA_LOGS; do
    if [[ -z "${!var}" ]]; then
        echo "❌ FAIL: $var no está definido"
        exit 1
    fi
    echo "✅ $var definido: ${!var}"
done

# Test 4: Subdirectorios cuelgan de URA_ROOT
if [[ "$URA_AGENTS" != "$URA_ROOT/agents" ]]; then
    echo "❌ FAIL: URA_AGENTS no cuelga de URA_ROOT"
    exit 1
fi
echo "✅ Subdirectorios cuelgan de URA_ROOT"

# Test 5: En Mac, URA_ROOT debe ser /Users/...
if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ "$URA_ROOT" != /Users/* ]]; then
        echo "❌ FAIL: En Mac, URA_ROOT debe ser /Users/*"
        exit 1
    fi
    echo "✅ En Mac, URA_ROOT correcto"
fi

echo ""
echo "=== Todos los tests pasaron ==="
