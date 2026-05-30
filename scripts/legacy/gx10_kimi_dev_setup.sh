#!/bin/bash
# gx10_kimi_dev_setup.sh — Instalar Kimi-Dev-72B en el ASUS (GX10)
# Ejecutar en el GX10 como usuario ramon

set -e

MODEL_DIR="$HOME/models/kimi-dev"
MODEL_NAME="Kimi-Dev-72B-Q8_0"
GGUF_URL="https://huggingface.co/mradermacher/Kimi-Dev-72B-GGUF/resolve/main/Kimi-Dev-72B-Q8_0.gguf"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kimi-Dev-72B — Setup para GX10 (ASUS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Liberar RAM ─────────────────────────────────────────
echo "[1/5] Liberando RAM (deteniendo modelos Ollama)..."
ollama stop qwen3:32b 2>/dev/null || echo "  qwen3:32b ya estaba parado"
ollama stop deepseek-r1:70b 2>/dev/null || echo "  deepseek-r1:70b ya estaba parado"
sleep 3

FREE_RAM=$(free -h | awk '/Mem:/ {print $7}')
echo "  RAM libre: $FREE_RAM"
echo ""

# ── 2. Descargar modelo ─────────────────────────────────────
echo "[2/5] Descargando modelo GGUF (73 GB, puede tardar)..."
mkdir -p "$MODEL_DIR"

GGUF_FILE=$(basename "$GGUF_URL")
GGUF_PATH="$MODEL_DIR/$GGUF_FILE"

if [ -f "$GGUF_PATH" ]; then
    echo "  El modelo ya existe: $GGUF_PATH"
    echo "  Tamaño: $(du -h "$GGUF_PATH" | cut -f1)"
else
    echo "  Descargando de HuggingFace..."
    wget -c "$GGUF_URL" -O "$GGUF_PATH" --progress=bar:force 2>&1
    echo "  Descarga completada."
fi
echo ""

# ── 3. Compilar ik_llama.cpp ─────────────────────────────────
echo "[3/5] Clonando y compilando ik_llama.cpp..."

REPO_DIR="$HOME/ik_llama.cpp"
if [ -d "$REPO_DIR" ]; then
    echo "  Repositorio ya existe, actualizando..."
    cd "$REPO_DIR"
    git pull
else
    git clone https://github.com/ikawrakow/ik_llama.cpp "$REPO_DIR"
    cd "$REPO_DIR"
fi

mkdir -p build
cd build

echo "  Ejecutando cmake..."
cmake .. -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -3

echo "  Compilando con $(nproc) núcleos..."
make -j$(nproc) llama-server 2>&1 | tail -5

if [ -f "bin/llama-server" ]; then
    echo "  Compilacion exitosa: build/bin/llama-server"
else
    echo "  ERROR: No se genero llama-server. Revisa la compilacion."
    exit 1
fi
echo ""

# ── 4. Iniciar servidor ──────────────────────────────────────
echo "[4/5] Iniciando servidor llama-server en puerto 8080..."

# Matar instancia previa si existe
pkill -f "llama-server.*kimi" 2>/dev/null || true
sleep 1

cd "$REPO_DIR"
nohup ./build/bin/llama-server \
    -m "$GGUF_PATH" \
    --host 0.0.0.0 \
    --port 8080 \
    -ngl 99 \
    --ctx-size 4096 \
    > "$MODEL_DIR/llama-server.log" 2>&1 &

SERVER_PID=$!
echo "  Servidor iniciado con PID: $SERVER_PID"
sleep 5

# Verificar que arranco
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "  Servidor funcionando correctamente"
else
    echo "  ERROR: El servidor no arranco. Revisa $MODEL_DIR/llama-server.log"
    tail -10 "$MODEL_DIR/llama-server.log"
    exit 1
fi
echo ""

# ── 5. Verificar API ─────────────────────────────────────────
echo "[5/5] Verificando API del servidor..."
sleep 3
curl -s http://localhost:8080/v1/models 2>/dev/null && echo ""
curl -s http://localhost:8080/health 2>/dev/null && echo ""

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup completado!"
echo ""
echo "  Modelo: $GGUF_PATH"
echo "  API:    http://localhost:8080/v1/chat/completions"
echo "  Logs:   $MODEL_DIR/llama-server.log"
echo ""
echo "  Para usar en OpenCode:"
echo "    custom provider → http://<GX10-IP>:8080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
