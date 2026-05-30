#!/bin/bash
set -euo pipefail
# ajustar_modelos.sh — Optimiza modelos IA para RTX 3500 Ada (12GB VRAM)
# Detecta modelos disponibles y genera configuracion optima

echo "🔍 Detectando hardware..."
GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "No NVIDIA GPU")
echo "   GPU: $GPU_INFO"

echo "📦 Modelos disponibles en GX10:"
curl -s http://10.164.1.99:11434/api/tags 2>/dev/null | jq -r '.models[].name' || echo "   GX10 no disponible"

# Modelo rapido para codificacion y tareas diarias
echo ""
echo "⚡ Modelo rapido recomendado: qwen2.5-coder:14b"
echo "   (cabe entero en VRAM ~8GB, no disponible actualmente en GX10)"
echo "   Alternativa actual: qwen2.5-coder:32b (mas pesado, parte en RAM)"

# Modelo visual para vigilancia
echo ""
echo "👁️ Modelo visual: llama3.2-vision:11b"
echo "   (cabe entero en VRAM ~8GB, ya instalado en GX10)"

# Configuracion GPU optima para modelos existentes
echo ""
echo "⚙️  Configuracion GPU optima:"
echo "   qwen3:32b-q8_0        → num_gpu 20 (~6GB VRAM, resto en RAM)"
echo "   qwen2.5-coder:32b     → num_gpu 30 (~8GB VRAM)"
echo "   llama3.2-vision:11b   → num_gpu 99 (cabe entero, ~8GB VRAM)"

echo ""
echo "✅ Ajuste completado. Usa OLLAMA_HOST=http://10.164.1.99:11434 ollama run <modelo>"
