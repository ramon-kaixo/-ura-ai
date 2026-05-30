#!/bin/bash
# code_review_night.sh — Automatización nocturna: Kimi-Dev revisa código URA
# Ejecutar en el GX10 a las 2 AM via cron

set -e

URA_DIR="/mnt/mac/URA/ura_ia_1972"
MODEL_DIR="$HOME/models/kimi-dev"
GGUF_FILE="$MODEL_DIR/Kimi-Dev-72B-Q8_0.gguf"
REPO_DIR="$HOME/ik_llama.cpp"
LOG_DIR="$HOME/logs/kimi_review"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)

mkdir -p "$LOG_DIR"

echo "[$(date)] === Iniciando code_review_night ===" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

# ── 1. Liberar RAM ─────────────────────────────────────────
echo "[1/5] Parando modelos Ollama..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
ollama stop qwen3:32b 2>/dev/null || true
ollama stop deepseek-r1:70b 2>/dev/null || true
ollama stop codestral:22b 2>/dev/null || true
ollama stop qwen2.5-coder:32b 2>/dev/null || true
sleep 5

FREE_RAM=$(free -h | awk '/Mem:/ {print $7}')
echo "  RAM libre: $FREE_RAM" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

# ── 2. Verificar modelo ──────────────────────────────────────
if [ ! -f "$GGUF_FILE" ]; then
    echo "  ERROR: Modelo no encontrado en $GGUF_FILE" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
    echo "  Ejecuta primero gx10_kimi_dev_setup.sh"
    exit 1
fi

# ── 3. Iniciar servidor Kimi-Dev ─────────────────────────────
echo "[2/5] Iniciando Kimi-Dev server..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
pkill -f "llama-server.*kimi" 2>/dev/null || true
sleep 2

cd "$REPO_DIR"
./build/bin/llama-server \
    -m "$GGUF_FILE" \
    --host 0.0.0.0 \
    --port 8080 \
    -ngl 99 \
    --ctx-size 4096 \
    > "$LOG_DIR/server_$TIMESTAMP.log" 2>&1 &

SERVER_PID=$!
sleep 10

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "  ERROR: Servidor no arranco" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
    exit 1
fi
echo "  Servidor OK (PID: $SERVER_PID)" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

# ── 4. Ejecutar revisión de código ───────────────────────────
echo "[3/5] Revisando código URA..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

# Enviar archivos Python al modelo para revisión
if [ -d "$URA_DIR" ]; then
    find "$URA_DIR" -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" \
        -not -path "*/archive/*" -not -path "*/backup/*" | while read f; do
        echo "  Revisando: $(basename $f)" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

        curl -s http://localhost:8080/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{
                \"model\": \"kimi-dev\",
                \"messages\": [
                    {\"role\": \"system\", \"content\": \"You are a senior code reviewer. Review this Python file for bugs, security issues, performance problems, and code quality. Be concise.\"},
                    {\"role\": \"user\", \"content\": \"Review this code:\\n\\n\$(cat $f | head -500)\"}
                ],
                \"temperature\": 0.1,
                \"max_tokens\": 500
            }" >> "$LOG_DIR/review_$TIMESTAMP.jsonl" 2>/dev/null

        echo "" >> "$LOG_DIR/review_$TIMESTAMP.jsonl"
    done
else
    echo "  URA_DIR no accesible: $URA_DIR" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
    echo "  Saltando revisión de código." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
fi

# ── 5. Generar informe resumen ───────────────────────────────
echo "[4/5] Generando informe..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
FILES_REVIEWED=$(grep -c "Revisando:" "$LOG_DIR/review_$TIMESTAMP.log" 2>/dev/null || echo 0)
echo "  Archivos revisados: $FILES_REVIEWED" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"

# ── 6. Limpiar y restaurar ───────────────────────────────────
echo "[5/5] Apagando Kimi-Dev y restaurando modelos..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
pkill -f "llama-server.*kimi" 2>/dev/null || true
sleep 3

echo "  Reiniciando qwen3:32b..." | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
ollama run qwen3:32b "ping" 2>/dev/null &
sleep 2

echo "" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
echo "[$(date)] === code_review_night completado ===" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
echo "  Log: $LOG_DIR/review_$TIMESTAMP.log" | tee -a "$LOG_DIR/review_$TIMESTAMP.log"
