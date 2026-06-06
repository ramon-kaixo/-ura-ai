#!/usr/bin/env bash
# launch-agents.sh — OpenClaw orchestrador de agentes sandbox
# Lanza un agente Docker por cada archivo nuevo en la cola
# Cada agente corre en --network none --read-only
set -euo pipefail

COLA_DIR="$HOME/.nervioso/ura_search/cola"
OUTPUT_DIR="$HOME/.nervioso/ura_search/procesado"
AGENT_IMAGE="ura-agent:latest"
LOG_FILE="$HOME/.nervioso/ura_search/agent.log"

mkdir -p "$OUTPUT_DIR"
exec >> "$LOG_FILE" 2>&1

echo "[$(date)] === INICIO CICLO AGENTES ==="

# Recorrer cada categoría en la cola
for cat_dir in "$COLA_DIR"/*/; do
    categoria=$(basename "$cat_dir")
    [ "$categoria" = "*" ] && break
    echo "[$(date)] Procesando categoria: $categoria"

    # Buscar archivos .html sin procesar (sin su .meta.json correspondiente en OUTPUT)
    for html_file in "$cat_dir"/*.html; do
        [ -f "$html_file" ] || continue
        base=$(basename "$html_file" .html)
        meta_file="$cat_dir/$base.meta.json"
        output_file="$OUTPUT_DIR/$categoria/$base.json"

        # Si ya está procesado, saltar
        [ -f "$output_file" ] && continue

        mkdir -p "$OUTPUT_DIR/$categoria"

        echo "[$(date)]   → $categoria/$base.html"

        # Lanzar agente en Docker sandbox
        docker run --rm --network none --read-only \
            -v "$html_file":/input.txt:ro \
            -v "$OUTPUT_DIR/$categoria":/output \
            "$AGENT_IMAGE" \
            --categoria "$categoria" \
            --input /input.txt \
            --output "/output/$base.json" \
            > /dev/null 2>&1 || echo "  ⚠️  Error procesando $base"

        echo "[$(date)]     ✓ $base.json"
    done
done

echo "[$(date)] === FIN CICLO AGENTES ==="
