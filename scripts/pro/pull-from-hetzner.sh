#!/bin/bash
# pull-from-hetzner.sh — Trae un archivo concreto de Hetzner bajo demanda, escaneado
# Uso: pull-from-hetzner.sh <ruta_remota> [categoria]
#   ruta_remota: path en Hetzner (ej: /root/ura_search/data/reporte.pdf)
#   categoria:   subdirectorio en ~/URA/inbox/ (default: "general")
# Flujo:
#   1. SSH a Hetzner → checksum + tamaño
#   2. SCP a /tmp/ de ASUS
#   3. ClamAV scan
#   4. Si limpio → ~/URA/inbox/<categoria>/ con verificación checksum
#   5. Si infectado → ~/URA/quarantine/
#   6. Limpia /tmp
set -uo pipefail

HETZNER_HOST="100.78.49.106"
SSH_USER="ramon_admin"
SSH_KEY="$HOME/.ssh/id_rsa"
SSH_BASE="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
SCP_BASE="scp -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
LOG="/home/ramon/URA/logs/pull_from_hetzner.log"
INBOX="/home/ramon/URA/inbox"
QUARANTINE="/home/ramon/URA/quarantine"
CLAMSCAN="/usr/bin/clamscan"

REMOTE_PATH="${1:-}"
CATEGORY="${2:-general}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Validar argumentos
if [ -z "$REMOTE_PATH" ]; then
    echo "Uso: $0 <ruta_remota> [categoria]"
    echo "  ruta_remota ej: /root/ura_search/data/reporte.pdf"
    echo "  categoria ej: pdfs, imagenes, documentos (default: general)"
    echo "  Las rutas excluidas del backup automático: /root/ura_search/data/ /storage/inbox/"
    exit 1
fi

log "=== Pull ${TIMESTAMP} ==="
log "Archivo: ${REMOTE_PATH}"
log "Categoria: ${CATEGORY}"

# 1. Obtener checksum y tamaño remoto
log "[1/5] Verificando archivo en Hetzner..."
REMOTE_INFO=$($SSH_BASE "$SSH_USER@$HETZNER_HOST" \
    "if [ -f '$REMOTE_PATH' ]; then sha256sum '$REMOTE_PATH' | cut -d' ' -f1; stat --format='%s' '$REMOTE_PATH'; else echo 'NOT_FOUND'; fi" 2>&1)

if echo "$REMOTE_INFO" | grep -q "NOT_FOUND\|Connection refused\|Host key verification failed"; then
    log "ERROR: Archivo no encontrado o Hetzner inalcanzable"
    log "${REMOTE_INFO}"
    exit 1
fi

REMOTE_HASH=$(echo "$REMOTE_INFO" | head -1)
REMOTE_SIZE=$(echo "$REMOTE_INFO" | tail -1)
log "  SHA256: ${REMOTE_HASH}"
log "  Tamaño: $(numfmt --to=iec $REMOTE_SIZE)"

# 2. SCP a /tmp/
log "[2/5] Descargando a /tmp/..."
LOCAL_TMP="/tmp/ura_pull_${TIMESTAMP}_$(basename "$REMOTE_PATH")"

if ! $SCP_BASE "${SSH_USER}@${HETZNER_HOST}:${REMOTE_PATH}" "$LOCAL_TMP" >> "$LOG" 2>&1; then
    log "ERROR: SCP falló"
    exit 2
fi
log "  Descargado: $(stat --format='%s' "$LOCAL_TMP" 2>/dev/null) bytes"

# 3. Verificar checksum tras descarga
LOCAL_HASH=$(sha256sum "$LOCAL_TMP" | cut -d' ' -f1)
if [ "$REMOTE_HASH" != "$LOCAL_HASH" ]; then
    log "ERROR: Checksum mismatch (remoto=${REMOTE_HASH} != local=${LOCAL_HASH})"
    rm -f "$LOCAL_TMP"
    exit 3
fi
log "  Checksum OK"

# 4. ClamAV scan
log "[3/5] Escaneando con ClamAV..."
if ! $CLAMSCAN --quiet --no-summary "$LOCAL_TMP" >> "$LOG" 2>&1; then
    log "⚠ INFECTADO: moviendo a cuarentena"
    mkdir -p "$QUARANTINE/${CATEGORY}"
    mv "$LOCAL_TMP" "$QUARANTINE/${CATEGORY}/$(basename "$REMOTE_PATH").${TIMESTAMP}.quarantine"
    log "  Destino: ${QUARANTINE}/${CATEGORY}/"
    log "=== FIN (infectado) ==="
    exit 4
fi
log "  ClamAV: LIMPIO"

# 5. Mover a inbox
log "[4/5] Moviendo a inbox..."
mkdir -p "$INBOX/${CATEGORY}"
mv "$LOCAL_TMP" "$INBOX/${CATEGORY}/$(basename "$REMOTE_PATH")"
log "  Destino: ${INBOX}/${CATEGORY}/$(basename "$REMOTE_PATH")"
log "  SHA256: ${REMOTE_HASH}"

log "[5/5] Limpieza /tmp"
rm -f "$LOCAL_TMP" 2>/dev/null

log "=== FIN (ok) ==="
exit 0
