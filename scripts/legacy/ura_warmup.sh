#!/bin/bash
# Precalienta qwen3 en GX10 para evitar latencia de primera carga.
# Útil tras reinicio o después de 5min de inactividad (KEEP_ALIVE=5m).
GX10="10.164.1.99"
echo "🔥 Precalentando qwen3:32b en GX10..."
curl -s --max-time 120 -X POST "http://${GX10}:11434/api/generate" \
  -d '{"model":"qwen3:32b-q8_0","prompt":"OK","stream":false,"options":{"num_predict":1}}' \
  > /dev/null && echo "✅ qwen3 listo" || echo "❌ Falló warmup"
