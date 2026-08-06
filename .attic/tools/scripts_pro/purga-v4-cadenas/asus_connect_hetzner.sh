#!/bin/bash
# ================================================================
# CONECTAR ASUS A HETZNER EXIT NODE
# Ejecutar en ASUS GX10
# ================================================================

set -euo pipefail

echo "╔══════════════════════════════════════════════════════╗"
echo "║  CONECTAR ASUS → HETZNER EXIT NODE                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Verificar que Tailscale está activo ──
if ! tailscale status >/dev/null 2>&1; then
    echo "❌ Tailscale no está activo. Ejecuta: sudo tailscale up"
    exit 1
fi
echo "✅ Tailscale activo"

# ── Verificar que Hetzner es reachable ──
echo ""
echo "=== Verificando conectividad con Hetzner ==="
if tailscale status 2>/dev/null | grep -q "hetzner-escudo"; then
    echo "✅ hetzner-escudo encontrado en la tailnet"
else
    echo "❌ hetzner-escudo NO está en la tailnet"
    echo "   Asegúrate de haber ejecutado install_tailscale_hetzner.sh en Hetzner"
    exit 1
fi

# ── Configurar exit node ──
echo ""
echo "=== Configurando exit node ==="
echo "   Esto enrutará TODO el tráfico de Internet del ASUS a través de Hetzner"
echo ""
echo "   ⚠️  IMPORTANTE: La conexión de cable directo al Mac (10.164.1.x) NO se verá afectada"
echo "   Solo el tráfico de Internet (0.0.0.0/0) pasará por Hetzner"
echo ""

tailscale up --exit-node=hetzner-escudo --exit-node-allow-lan-access --accept-routes

# ── Verificar ──
echo ""
echo "=== Verificando conexión ==="
sleep 3

echo "Test 1: IP pública (debe ser la de Hetzner):"
CURL_IP=$(curl -s --max-time 10 httpbin.org/ip 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('origin','FAIL'))" 2>/dev/null || echo "TIMEOUT")
echo "  IP: $CURL_IP"

echo ""
echo "Test 2: Velocidad de descarga:"
curl -s -o /dev/null -w "  %{speed_download} B/s (%{time_total}s)\n" \
  http://httpbin.org/bytes/1048576 --max-time 30 2>/dev/null || echo "  TIMEOUT"

echo ""
echo "Test 3: DNS:"
dig +short google.com 2>/dev/null | head -1 || echo "  DNS: usando Tailscale MagicDNS"

echo ""
echo "Test 4: Tailscale status:"
tailscale status 2>/dev/null | grep "hetzner"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ ASUS CONECTADO A HETZNER EXIT NODE               ║"
echo "╚══════════════════════════════════════════════════════╝"
