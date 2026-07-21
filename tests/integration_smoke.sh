#!/usr/bin/env bash
# ============================================================
# Smoke Test — URA Model Router v3.0
# Verifica: version, health, metrics, auto-routing, direct model
# USO: ./tests/integration_smoke.sh
# ============================================================
set -e

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"

ROUTER_URL="http://localhost:11435"
ROUTER_SCRIPT="core/model_router_main.py"
OLLAMA_URL="http://localhost:11434"
PASS=0
FAIL=0

red()   { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        green "  ✓ $desc"
        ((PASS++))
    else
        red "  ✗ $desc"
        ((FAIL++))
    fi
}

echo "============================================"
echo " Smoke Test: URA Model Router"
echo "============================================"

# 0. Verificar imports
echo ""
echo "[0] Verificando imports..."
check "config_manager importa" python3 -c "from core.config_manager import CONFIG; print(CONFIG['role'])"
check "ura_maintenance importa" python3 -c "from mantenimiento.ura_maintenance import MaintenanceOrchestrator"
check "ura_maintenance_remote importa" python3 -c "from mantenimiento.ura_maintenance_remote import validate_ip"

# 1. Ollama health
echo ""
echo "[1] Ollama backend..."
check "Ollama responde" curl -sf "$OLLAMA_URL/api/tags"

# 2. Arrancar router
echo ""
echo "[2] Arrancando router..."
python3 "$ROUTER_SCRIPT" &
ROUTER_PID=$!
sleep 2
check "Router PID existe" kill -0 "$ROUTER_PID" 2>/dev/null

# 3. Version
echo ""
echo "[3] /api/version..."
VERSION=$(curl -sf "$ROUTER_URL/api/version" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")
check "Version es 3.0" [ "$VERSION" = "3.0" ]

# 4. Health
echo ""
echo "[4] /health..."
STATUS=$(curl -sf "$ROUTER_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
check "Status ok" [ "$STATUS" = "ok" ]

# 5. Metrics
echo ""
echo "[5] /metrics..."
check "Métricas contienen model_selection" curl -sf "$ROUTER_URL/metrics" | grep -q "model_selection"

# 6. Auto-routing POST
echo ""
echo "[6] POST /api/chat (auto)..."
RESP=$(curl -sf -X POST "$ROUTER_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"di hola"}]}')
check "Respuesta contiene message" echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'message' in d"

# 7. Direct model POST
echo ""
echo "[7] POST /api/chat (direct)..."
check "Modelo directo responde 200" curl -sf -o /dev/null -w "%{http_code}" -X POST "$ROUTER_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"hola"}]}' | grep -q "200"

# 8. Modelos disponibles
echo ""
echo "[8] Router --models..."
check "Flag --models lista modelos" python3 "$ROUTER_SCRIPT" --models 2>/dev/null | grep -q "qwen"

# 9. Clasificación
echo ""
echo "[9] Router --test..."
check "Flag --test clasifica" python3 "$ROUTER_SCRIPT" --test "analizar un error" 2>/dev/null | grep -q "Tipo:"

# 10. Mantenimiento dry-run
echo ""
echo "[10] ura_maintenance --dry-run..."
check "Dry-run completa" python3 mantenimiento/ura_maintenance.py --dry-run 2>&1 | grep -q "DRY-RUN\|completado\|thresholds\|Espacio"

# Cleanup
echo ""
kill "$ROUTER_PID" 2>/dev/null
wait "$ROUTER_PID" 2>/dev/null

echo ""
echo "============================================"
echo " Resultado: $PASS pasaron, $FAIL fallaron"
echo "============================================"

[ "$FAIL" -eq 0 ] && green "TODOS LOS TESTS PASARON" || red "HAY FALLOS"
exit $FAIL
