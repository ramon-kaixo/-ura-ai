#!/usr/bin/env bash
# ============================================================
# Network Failover — URA GX10
# Configura rutas con métricas estáticas para failover determinista.
# Ethernet enP7s7 (métrica 100) > Tailscale (200) > Wi-Fi wlP9s9 (300)
# Se ejecuta cada 5 minutos via systemd timer para re-aplicar si se pierden rutas.
# ============================================================
set -e

echo "Configurando failover de red con métricas estáticas..."

# Interfaces reales detectadas desde ifconfig
ETH="enP7s7"
TAILSCALE="tailscale0"
WIFI="wlP9s9"
GATEWAY="10.164.1.1"
WIFI_GATEWAY="192.168.1.1"
MAC_LAN="10.164.1.0/24"

echo "  Interfaces: ETH=$ETH TAIL=$TAILSCALE WIFI=$WIFI"

# Ruta principal: Ethernet (métrica 100 — prioridad máxima)
ip route replace "$MAC_LAN" dev "$ETH" metric 100 2>/dev/null && \
    echo "  ✅ Ethernet (metric 100)"
ip route replace default via "$GATEWAY" dev "$ETH" metric 100 2>/dev/null || true

# Ruta secundaria: Tailscale VPN (métrica 200)
ip route replace "$MAC_LAN" dev "$TAILSCALE" metric 200 2>/dev/null && \
    echo "  ✅ Tailscale (metric 200)" || echo "  ⚠ Tailscale no disponible"

# Ruta terciaria: Wi-Fi (métrica 300)
ip route replace "$MAC_LAN" dev "$WIFI" metric 300 2>/dev/null && \
    echo "  ✅ Wi-Fi (metric 300)" || echo "  ⚠ Wi-Fi no disponible"
ip route replace default via "$WIFI_GATEWAY" dev "$WIFI" metric 300 2>/dev/null || true

echo ""
echo "Rutas activas hacia $MAC_LAN:"
ip route show | grep -E "$ETH|$TAILSCALE|$WIFI" | grep "$MAC_LAN" || echo "  (ninguna)"

echo ""
echo "Ruta por defecto:"
ip route show default | head -3

echo ""
echo "Failover listo. Kernel elige métrica más baja. Si Ethernet cae → Tailscale → Wi-Fi."

# ────────────────────────────────────────────────────────────
# También verificar y reparar Tailscale si está caído
# ────────────────────────────────────────────────────────────
if ! tailscale status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); peers=[p for p in d.get('Peer',{}).values() if p.get('Online')]; exit(0 if len(peers)>0 else 1)" 2>/dev/null; then
    echo "⚠ Tailscale sin peers — reintentando..."
    systemctl restart tailscaled 2>/dev/null || true
    sleep 3
    tailscale up --accept-routes --exit-node=hetzner-escudo --exit-node-allow-lan-access 2>/dev/null || true
fi

# ────────────────────────────────────────────────────────────
# Verificar conexión a Mac (Ethernet o Tailscale)
# ────────────────────────────────────────────────────────────
if ! ping -c 1 -W 2 ${TERMINAL_HOST:-10.164.1.26} >/dev/null 2>&1; then
    if ping -c 1 -W 2 100.123.81.101 >/dev/null 2>&1; then
        echo "⚠ Mac alcanzable solo por Tailscale (Ethernet caído)"
    else
        echo "⚠ Mac NO alcanzable"
    fi
fi
