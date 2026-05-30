#!/bin/bash
# openclaw_disciplina.sh – Modo ejecutor estricto. Sin rodeos, solo acciones.
# Uso: bash openclaw_disciplina.sh <comando>
# Comandos: estado, herramientas, limpiar, test, volumen, camaras, sistema, ayuda

set -euo pipefail

COMANDO="$*"
REPO="${HOME}/URA/ura_ia_1972"
MCP="http://127.0.0.1:9091"

case "$1" in
    estado)
        echo "=== SISTEMA ==="
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d '{"name":"sistema","arguments":{}}' | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        echo "=== CAMARAS ==="
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d '{"name":"camaras","arguments":{}}' | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    herramientas|tools)
        curl -s "$MCP/mcp/tools" | python3 -m json.tool
        ;;
    volumen)
        NIVEL="${2:-50}"
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d "{\"name\":\"volumen\",\"arguments\":{\"nivel\":$NIVEL}}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    abrir)
        APP="${2:-Safari}"
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d "{\"name\":\"abrir_app\",\"arguments\":{\"nombre\":\"$APP\"}}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    cerrar)
        APP="${2:-Safari}"
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d "{\"name\":\"cerrar_app\",\"arguments\":{\"nombre\":\"$APP\"}}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    camaras)
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d '{"name":"camaras","arguments":{}}' | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    sistema)
        curl -s "$MCP/mcp/call" -H "Content-Type: application/json" \
          -d '{"name":"sistema","arguments":{}}' | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('resultado','error'))"
        ;;
    limpiar)
        docker system prune -f --filter "until=24h" 2>/dev/null || true
        echo "OK: docker prune ejecutado"
        ;;
    test)
        bash "$0" estado
        bash "$0" herramientas | head -5
        bash "$0" volumen 50
        bash "$0" camaras
        echo "TEST COMPLETADO"
        ;;
    ayuda|help)
        echo "Comandos: estado, herramientas, volumen N, abrir APP, cerrar APP, camaras, sistema, limpiar, test"
        ;;
    *)
        echo "Comando no reconocido: $1"
        echo "Usa: bash openclaw_disciplina.sh help"
        exit 1
        ;;
esac
