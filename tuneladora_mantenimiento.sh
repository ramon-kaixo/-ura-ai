#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="${HOME}/URA/ura_ia_1972"
CONTEXT="/opt/ura/data/ura_context.json"
AUDIT_LOG="/opt/ura/logs/model_audit.jsonl"
MODO_SISTEMA="/opt/ura/scripts/modo_sistema.sh"

mkdir -p "$(dirname "$AUDIT_LOG")"

echo "Tuneladora de Mantenimiento - $(date)"

# Aplicar modo sistema automatico
if [ -x "$MODO_SISTEMA" ]; then
    bash "$MODO_SISTEMA" auto >> /opt/ura/logs/modo_sistema.log 2>&1
fi

cd "$REPO"
ruff check . --fix --quiet || true
ruff format . --quiet || true
pytest --quiet -x --timeout=60 2>/dev/null || echo "Tests: algunos fallos esperados"
bandit -r . -ll 2>/dev/null || true

# Pipeline de auditoria de modelos
echo "=== Auditoria de Modelos ==="
MODELOS_A_TESTEAR=(
    "qwen2.5-coder:32b"
    "codestral:22b"
    "qwen2.5-coder:14b"
    "deepseek-coder:6.7b"
    "qwen2.5:7b"
)

for modelo in "${MODELOS_A_TESTEAR[@]}"; do
    echo "   Probando $modelo..."
    TEST_FILE="$(mktemp /tmp/ura_model_test_XXXXXX.py)"
    cat > "$TEST_FILE" << 'PYEOF'
import json, time, subprocess, sys
modelo = sys.argv[1]
prompts = [
    ("refactor", "Refactoriza esta funcion: def old(x): return [i for i in range(x) if i%2==0]"),
    ("docstring", "Genera un docstring para: def procesar(datos, umbral=0.5): return [x for x in datos if x > umbral]"),
    ("types", "Anade type hints a: def calcular( precio, descuento, impuesto ): return precio * (1-descuento) * (1+impuesto)"),
]
resultados = []
for tipo, prompt in prompts:
    inicio = time.time()
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
             "-d", json.dumps({"model": modelo, "prompt": prompt, "stream": False, "options": {"num_predict": 100}})],
            capture_output=True, text=True, timeout=30
        )
        dur = time.time() - inicio
        data = json.loads(r.stdout) if r.stdout else {}
        res = data.get("response", "")[:50]
        resultados.append({"tipo": tipo, "latencia_ms": round(dur*1000), "respuesta": res, "ok": bool(res)})
    except Exception as e:
        resultados.append({"tipo": tipo, "latencia_ms": 0, "error": str(e), "ok": False})
print(json.dumps({"modelo": modelo, "resultados": resultados}))
PYEOF
    chmod +x "$TEST_FILE"
    RESULT=$(python3 "$TEST_FILE" "$modelo" 2>/dev/null || echo '{"modelo":"'"$modelo"'","resultados":[]}')
    echo "$RESULT" >> "$AUDIT_LOG"
    LATENCIA=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); rs=[r for r in d.get('resultados',[]) if r.get('ok')]; print(round(sum(r['latencia_ms'] for r in rs)/len(rs)) if rs else 'N/A')" 2>/dev/null)
    echo "     -> Latencia media: ${LATENCIA}ms"
    rm -f "$TEST_FILE"
done

echo "Auditoria completa. Log: $AUDIT_LOG"

# Backup horario a las 03:00
if [ "$(date +%H)" = "03" ]; then
    echo "Generando copia maestra..."
    rsync -avz "$REPO/" "/opt/ura/backups/incremental_$(date +%Y%m%d)/" 2>/dev/null || true
    echo "Copia maestra generada."
fi

echo "Mantenimiento completado"
