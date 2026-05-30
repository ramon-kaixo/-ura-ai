#!/bin/bash
# firmar_evento.sh - Firma un evento con HMAC-SHA256
set -euo pipefail

SECRET="${URA_TOKEN:-}"
EVENTO="$1"

if [ -z "$SECRET" ]; then
    echo "Error: URA_TOKEN no definido" >&2
    exit 1
fi

if [ -z "$EVENTO" ]; then
    echo "Uso: firmar_evento.sh '<json_evento>'" >&2
    exit 1
fi

FIRMA=$(echo -n "$EVENTO" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
echo "$FIRMA"
