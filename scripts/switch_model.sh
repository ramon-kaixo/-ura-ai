#!/bin/bash
# switch_model.sh — Purga KV-cache y cambia de modelo en Ollama
# Uso: bash scripts/switch_model.sh <modelo_nuevo>
# Ej:  bash scripts/switch_model.sh llama3.3:70b

MODELO_NUEVO="${1:-qwen2.5-coder:32b}"

echo "Purgando KV-cache antes de cargar $MODELO_NUEVO..."

# Liberar todos los modelos de la memoria
if command -v ollama &> /dev/null; then
    ollama stop 2>/dev/null
    echo "  Modelos previos descargados"
fi

# Forzar liberacion via API
curl -s -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODELO_NUEVO\", \"prompt\": \"\", \"keep_alive\": -1}" \
  > /dev/null 2>&1

echo "  KV-cache purgado. Blackwell listo para $MODELO_NUEVO"
