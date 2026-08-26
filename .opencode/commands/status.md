Verifica el estado de todos los servicios de URA en GX10.

Ejecuta: `ssh ramon@100.72.103.12 'systemctl is-active ollama model-router ura-api opencode opencode-web 2>/dev/null; echo "---"; curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(f\"Ollama: {len(json.load(sys.stdin).get(\"models\",[]))} modelos\")"'`

Muestra el estado de cada servicio y el número de modelos disponibles.
Si algún servicio está inactivo, intenta reiniciarlo.
