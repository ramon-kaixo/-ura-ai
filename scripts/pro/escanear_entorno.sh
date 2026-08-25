#!/bin/bash
# Escanear entorno URA — modelos, máquinas, servicios, estado git.
# Genera JSON con el estado real para parse_pytest_results.py
# Uso: ./scripts/pro/escanear_entorno.sh [ruta_salida_json]

set -uo pipefail
SALIDA="${1:-/tmp/ura_entorno_real_$(date +%Y%m%d).json}"

echo "{" > "$SALIDA"
echo "  \"fecha\": \"$(date +%Y-%m-%dT%H:%M:%S%z)\"," >> "$SALIDA"

# Modelos Ollama
echo "  \"modelos_ollama\": [" >> "$SALIDA"
if curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    names = [m['name'] for m in d.get('models', [])]
    for n in names:
        print(json.dumps(n) + ',')
except Exception:
    pass
" >> "$SALIDA" 2>/dev/null; then
    sed -i '' '$ s/,$//' "$SALIDA" 2>/dev/null || true
fi
echo "  ]," >> "$SALIDA"

# Servicios systemd (si aplica)
echo "  \"servicios\": {" >> "$SALIDA"
if command -v systemctl >/dev/null 2>&1; then
    for s in ura-mochila model-router ura-api; do
        estado=$(systemctl is-active "$s" 2>/dev/null || echo "unknown")
        echo "    \"$s\": \"$estado\"," >> "$SALIDA"
    done
    sed -i '' '$ s/,$//' "$SALIDA" 2>/dev/null || true
else
    echo "    \"systemd\": \"no disponible\"" >> "$SALIDA"
fi
echo "  }," >> "$SALIDA"

# Estado git
SUCIO=false
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then SUCIO=true; fi
echo "  \"git\": {" >> "$SALIDA"
echo "    \"branch\": \"$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\"," >> "$SALIDA"
echo "    \"head\": \"$(git rev-parse --short HEAD 2>/dev/null || echo unknown)\"," >> "$SALIDA"
echo "    \"sucio\": \"$SUCIO\"" >> "$SALIDA"
echo "  }" >> "$SALIDA"

echo "}" >> "$SALIDA"
echo "Entorno escaneado: $SALIDA"
cat "$SALIDA"
