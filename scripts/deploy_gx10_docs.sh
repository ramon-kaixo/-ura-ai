#!/bin/bash
# deploy_gx10_docs.sh - Despliega el sistema de documentacion en el GX10
# Ejecutar EN el GX10 (via SSH o terminal local)
# bash deploy_gx10_docs.sh
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
echo -e "${GREEN}=== GX10 - Sistema de documentacion ===${NC}"

# 1. Directorios
mkdir -p /opt/ura/scripts /opt/ura/docs /opt/ura_data/videos /opt/ura_data/transcripciones /opt/ura_data/chroma_docs
touch /opt/ura_data/videos_procesados.json
echo "[]" > /opt/ura_data/videos_procesados.json

# 2. Instalar dependencias
echo -e "${YELLOW}[1/5] Instalando dependencias...${NC}"
pip3 install yt-dlp openai-whisper chromadb sentence-transformers flask 2>&1 | tail -3

# 3. Scripts
echo -e "${YELLOW}[2/5] Creando scripts...${NC}"

cat > /opt/ura/scripts/buzo_videos_gx10.sh << 'SHEOF'
#!/bin/bash
# buzo_videos_gx10.sh - Descarga + transcribe + indexa en GX10
LISTA="/opt/ura/docs/video_lista.txt"
VIDEOS_DIR="/opt/ura_data/videos"
TRANSCRIPCIONES="/opt/ura_data/transcripciones"
PROCESADOS="/opt/ura_data/videos_procesados.json"
LOG="/opt/ura/logs/buzo_videos_gx10.log"

export PATH="$PATH:/home/ramon/.local/bin"
mkdir -p "$VIDEOS_DIR" "$TRANSCRIPCIONES" "$(dirname "$LOG")"

echo "[$(date)] Inicio" >> "$LOG"

while IFS= read -r url; do
    url=$(echo "$url" | xargs)
    [ -z "$url" ] && continue
    if jq -e "index(\"$url\")" "$PROCESADOS" > /dev/null 2>&1; then continue; fi
    echo "  Descargando $url" >> "$LOG"
    yt-dlp -f bestaudio --extract-audio --audio-format mp3 \
        --output "$VIDEOS_DIR/%(title)s.%(ext)s" "$url" >> "$LOG" 2>&1 || continue
    for audio in "$VIDEOS_DIR"/*.mp3; do
        [ ! -f "$audio" ] && continue
        python3 /opt/ura/scripts/transcribir_video_gx10.py "$audio" >> "$LOG" 2>&1
        rm -f "$audio"
        mv "$(echo "$audio" | sed 's/\.mp3$/.txt/' | sed 's|/videos/|/transcripciones/|')" "$TRANSCRIPCIONES/" 2>/dev/null || true
    done
    echo "$url" >> "$PROCESADOS"
done < "$LISTA"
echo "[$(date)] Fin" >> "$LOG"
SHEOF

cat > /opt/ura/scripts/transcribir_video_gx10.py << 'PYEOF'
#!/usr/bin/env python3
"""transcribir_video_gx10.py - Whisper con GPU si disponible."""
import sys, os, whisper, torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Usando dispositivo: {device}", flush=True)
model = whisper.load_model("base", device=device)

def transcribir(audio_path):
    result = model.transcribe(audio_path)
    txt_path = audio_path.replace(".mp3", ".txt").replace("/videos/", "/transcripciones/")
    os.makedirs(os.path.dirname(txt_path), exist_ok=True)
    with open(txt_path, "w") as f:
        f.write(f"Fuente: {os.path.basename(audio_path)}\n{result['text']}\n")
    print(f"Transcripcion: {txt_path}", flush=True)
    os.system(f"python3 /opt/ura/scripts/indexar_video_gx10.py '{txt_path}'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: transcribir_video_gx10.py <audio.mp3>")
        sys.exit(1)
    transcribir(sys.argv[1])
PYEOF

cat > /opt/ura/scripts/indexar_video_gx10.py << 'PYEOF'
#!/usr/bin/env python3
"""indexar_video_gx10.py - Indexa en ChromaDB local del GX10."""
import sys, os, chromadb

CHROMA_PATH = "/opt/ura_data/chroma_docs"
client = chromadb.PersistentClient(CHROMA_PATH)
try:
    coleccion = client.get_collection("documentacion")
except:
    coleccion = client.create_collection("documentacion")

def indexar(txt_path):
    if not os.path.exists(txt_path):
        return
    with open(txt_path) as f:
        texto = f.read()
    nombre = os.path.basename(txt_path)
    try:
        coleccion.add(documents=[texto], metadatas=[{"nombre": nombre, "tipo": "video", "ruta": txt_path}], ids=[nombre])
        print(f"Indexado: {nombre}")
    except Exception as e:
        print(f"Error indexando {nombre}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        indexar(sys.argv[1])
PYEOF

cat > /opt/ura/gx10_api.py << 'PYEOF'
#!/usr/bin/env python3
"""gx10_api.py - API REST para consultar ChromaDB de documentacion."""
from flask import Flask, request, jsonify
import chromadb

app = Flask(__name__)
client = chromadb.PersistentClient("/opt/ura_data/chroma_docs")
try:
    coleccion = client.get_collection("documentacion")
    print(f"Coleccion lista: {coleccion.count()} fragmentos")
except:
    coleccion = client.create_collection("documentacion")
    print("Coleccion creada (vacia)")

@app.route("/buscar")
def buscar():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "falta parametro q"}), 400
    results = coleccion.query(query_texts=[q], n_results=3)
    docs = results["documents"][0] if results.get("documents") else []
    return jsonify({"consulta": q, "resultados": docs})

@app.route("/health")
def health():
    return jsonify({"status": "online", "fragmentos": coleccion.count()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8083)
PYEOF

chmod +x /opt/ura/scripts/buzo_videos_gx10.sh /opt/ura/scripts/transcribir_video_gx10.py /opt/ura/scripts/indexar_video_gx10.py /opt/ura/gx10_api.py

# 4. Cron semanal
echo -e "${YELLOW}[3/5] Programando cron...${NC}"
(crontab -l 2>/dev/null | grep -v "buzo_videos_gx10\|gx10_api"
echo "0 5 * * 0 bash /opt/ura/scripts/buzo_videos_gx10.sh"
echo "@reboot /usr/bin/python3 /opt/ura/gx10_api.py &"
) | crontab -

# 5. Iniciar API
echo -e "${YELLOW}[4/5] Iniciando API de documentacion...${NC}"
nohup python3 /opt/ura/gx10_api.py > /tmp/gx10_api.log 2>&1 &

echo -e "${GREEN}[5/5] Instalacion completada${NC}"
echo "API: http://$(hostname):8083/buscar?q=openclaw"
echo "Logs: /opt/ura/logs/buzo_videos_gx10.log"
