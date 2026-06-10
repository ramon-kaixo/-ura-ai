#!/bin/bash
# sync_alemania.sh — Sincroniza recolección de Alemania → ASUS
# Uso: bash sync_alemania.sh [hetzner_ip] [ssh_user]

HETZNER="${1:-10.164.1.249}"
SSH_USER="${2:-ramon}"
REMOTE_DIR="/data/recoleccion_tecnica"
LOCAL_DIR="/home/ramon/.nervioso/biblioteca"

mkdir -p "$LOCAL_DIR"

echo "=== SYNC ALEMANIA → ASUS ==="
echo "Origen:  $SSH_USER@$HETZNER:$REMOTE_DIR"
echo "Destino: $LOCAL_DIR"
echo ""

# Check connectivity
if ping -c 1 -W 2 "$HETZNER" > /dev/null 2>&1; then
    echo "✅ $HETZNER responde"
else
    echo "❌ $HETZNER no responde — abortando"
    exit 1
fi

# Rsync
rsync -avzP \
    --include="*.html" --include="*.pdf" --include="*.md" --include="*.txt" \
    --include="*.zip" --include=".done" \
    --exclude="*" \
    "$SSH_USER@$HETZNER:$REMOTE_DIR/" "$LOCAL_DIR/"

echo ""
echo "=== SYNC COMPLETADO ==="
du -sh "$LOCAL_DIR"
ls "$LOCAL_DIR" | wc -l | xargs echo "Archivos:"
