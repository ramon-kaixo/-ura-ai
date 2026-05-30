#!/bin/bash
# asignar_tags_tailscale.sh - Asigna etiquetas automaticas basadas en el SO del nodo
set -euo pipefail

TAILSCALE_API_KEY="${TAILSCALE_API_KEY:-}"
TAILNET="${TAILNET:-example.com}"

if [ -z "$TAILSCALE_API_KEY" ]; then
    echo "Error: TAILSCALE_API_KEY no definida"
    exit 1
fi

for node in $(tailscale status --json | jq -r '.Peer[]? | "\(.HostName):\(.OS)"' 2>/dev/null); do
    hostname="${node%%:*}"
    os="${node##*:}"
    tag=""
    case "$os" in
        linux)   tag="tag:linux" ;;
        macos)   tag="tag:macos" ;;
        windows) tag="tag:windows" ;;
        *)       tag="tag:other" ;;
    esac
    if [ -n "$tag" ]; then
        curl -sf -H "Authorization: Bearer $TAILSCALE_API_KEY" \
            -X POST "https://api.tailscale.com/api/v2/tailnet/$TAILNET/devices/${hostname}/tags" \
            -d "{\"tags\": [\"$tag\"]}" 2>/dev/null || true
        echo "Etiqueta $tag asignada a $hostname"
    fi
done
