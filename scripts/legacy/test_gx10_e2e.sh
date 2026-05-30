#!/bin/bash
# test_gx10_e2e.sh — Prueba end-to-end del stack completo
# Requiere: GX10 corriendo, Ollama con modelos cargados, router activo

set -e

echo "═══ PRUEBA END-TO-END URA ═══"
echo ""

# Test 1: Router responde
echo "[1] Testeando central_router..."
cd ~/URA/ura_ia_1972
python3 -c "
from core.central_router import CentralRouter
import asyncio

r = CentralRouter()
result = asyncio.run(r.process_request('hola, ¿cómo estás?'))
assert result['intent'] == 'chat'
assert 'Hola' in result['response']
print(f'  ✓ Chat: {result[\"response\"][:50]}')

result2 = asyncio.run(r.process_request('crea una factura'))
assert 'factura' in result2['intent']
print(f'  ✓ Factura: intent={result2[\"intent\"]}')
print('  ✓ central_router OK')
"

# Test 2: Llama router
echo "[2] Testeando llama_router..."
curl -s http://127.0.0.1:8288/v1/models | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  ✓ Modelos disponibles: {[m[\"id\"] for m in data.get(\"data\", [])]}')
"

# Test 3: Ollama
echo "[3] Testeando Ollama..."
curl -s http://127.0.0.1:11434/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  ✓ Modelos Ollama: {[m[\"name\"] for m in data.get(\"models\", [])[:5]]}')
"

# Test 4: Whisper
echo "[4] Testeando Whisper..."
# Crear un archivo de audio de prueba (silencio de 1s)
sox -n -r 16000 -c 1 /tmp/test_silence.wav synth 1 sine 0 2>/dev/null || true
curl -s -X POST http://127.0.0.1:8090/transcribe -F "audio=@/tmp/test_silence.wav" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  ✓ Whisper respondió: {d.get(\"text\", \"(vacío)\")}')
" 2>/dev/null || echo "  ⚠ Whisper no respondió (puede no estar activo)"

# Test 5: Langfuse
echo "[5] Testeando Langfuse..."
curl -s http://127.0.0.1:3000/api/health 2>/dev/null | head -1 || echo "  ⚠ Langfuse no responde en :3000"

echo ""
echo "═══ PRUEBAS COMPLETADAS ═══"
