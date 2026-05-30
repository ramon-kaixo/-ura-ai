#!/bin/bash
# buzo_tailscale_discovery.sh - Descubre nuevos nodos en Tailscale
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
KNOWN_NODES_FILE="${REPO}/data/nodos_conocidos.json"
EVENTOS_DIR="${REPO}/data/registry/eventos"
FALLIDOS_DIR="${REPO}/data/registry/fallidos"
mkdir -p "$EVENTOS_DIR" "$FALLIDOS_DIR"

# Punto 5: Seguridad del registry
chmod 700 "$EVENTOS_DIR" 2>/dev/null || true

# Archivo temporal unico
TEMP_STATUS=$(mktemp /tmp/tailscale_status.XXXXXX.json)
trap 'rm -f "$TEMP_STATUS"' EXIT

tailscale status --json > "$TEMP_STATUS" 2>/dev/null || { echo "Tailscale no disponible"; exit 0; }

# Cargar nodos conocidos
[ -f "$KNOWN_NODES_FILE" ] || echo '{"nodos":[]}' > "$KNOWN_NODES_FILE"
known=$(jq -r '.nodos[].id' "$KNOWN_NODES_FILE" 2>/dev/null || true)

current_nodes=$(jq -r '.Peer[]? | "\(.HostName):\(.TailscaleIPs[0] // "unknown")"' "$TEMP_STATUS" 2>/dev/null || true)

for node in $current_nodes; do
    hostname="${node%%:*}"
    ip="${node##*:}"

    [ "$ip" = "unknown" ] && continue

    # Ya conocido?
    if echo "$known" | grep -qx "$hostname"; then
        old_ip=$(jq -r --arg hn "$hostname" '.nodos[] | select(.id==$hn) | .ip' "$KNOWN_NODES_FILE" 2>/dev/null || true)
        if [ "$old_ip" != "$ip" ] && [ -n "$old_ip" ]; then
            timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
            ev_file="${EVENTOS_DIR}/modificado_${hostname}_${timestamp}.json"
            cat > "$ev_file" << EOF
{"type": "nodo_modificado", "timestamp": "$timestamp", "nodo": {"hostname": "$hostname", "ip_anterior": "$old_ip", "ip_nuevo": "$ip"}}
EOF
            jq --arg hn "$hostname" --arg ip "$ip" '(.nodos[] | select(.id==$hn) | .ip) = $ip' "$KNOWN_NODES_FILE" > tmp.json && mv tmp.json "$KNOWN_NODES_FILE"
        fi
        continue
    fi

    # Nuevo nodo: verificar conectividad
    if ! ping -c1 -W2 "$ip" >/dev/null 2>&1; then
        echo "Nodo $hostname ($ip) no responde ping, se omite."
        continue
    fi

    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    ev_file="${EVENTOS_DIR}/nuevo_nodo_${hostname}_${timestamp}.json"
    so=$(jq -r --arg hn "$hostname" '.Peer[] | select(.HostName==$hn) | .OS // "unknown"' "$TEMP_STATUS" 2>/dev/null || echo "unknown")
    cat > "$ev_file" << EOF
{"type": "nuevo_nodo", "timestamp": "$timestamp", "nodo": {"hostname": "$hostname", "ip": "$ip", "os": "$so"}}
EOF

    # Registrar
    jq --arg hn "$hostname" --arg ip "$ip" '.nodos += [{"id":$hn, "ip":$ip, "descubierto":true, "desplegado":false, "last_seen":"'"$timestamp"'"}]' "$KNOWN_NODES_FILE" > tmp.json && mv tmp.json "$KNOWN_NODES_FILE"
    echo "Nuevo nodo descubierto: $hostname ($ip) - $so"
done

# Punto 1: Generar auth key efimera para nodos que no estan en Tailscale
MAC_IP="${MAC_IP:-$(ifconfig | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | head -1)}"
ALL_HOSTNAMES=$(jq -r '.Peer[]? | .HostName' "$TEMP_STATUS" 2>/dev/null || true)
for known_host in $(echo "$known"); do
    if ! echo "$ALL_HOSTNAMES" | grep -qx "$known_host"; then
        timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        AUTH_KEY=$(tailscale auth-key create --ephemeral --json 2>/dev/null | jq -r '.key' 2>/dev/null || echo "")
        if [ -n "$AUTH_KEY" ]; then
            BOOTSTRAP_URL="http://${MAC_IP}:8080/bootstrap.sh?key=${AUTH_KEY}"
            evento_file="${EVENTOS_DIR}/pendiente_tailscale_${known_host}_${timestamp}.json"
            cat > "$evento_file" << EOF
{"type": "nodo_pendiente_tailscale", "timestamp": "$timestamp", "nodo": {"hostname": "$known_host"}, "bootstrap_url": "$BOOTSTRAP_URL"}
EOF
            echo "Auth key generada para $known_host: $BOOTSTRAP_URL"
        fi
    fi
done

# Punto 7: Limpieza de nodos ausentes
LIMPIAR_SCRIPT="${REPO}/scripts/limpiar_nodos_ausentes.sh"
if [ -f "$LIMPIAR_SCRIPT" ]; then
    bash "$LIMPIAR_SCRIPT" 2>/dev/null || true
fi
