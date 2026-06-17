#!/bin/bash
# p2p_asus.sh — Enlace directo ASUS ⬌ Mac (subred /30)
# NO hace restart de systemd-networkd (evita caída de red).
# Uso: bash deploy/p2p_asus.sh
# Requiere: cable Ethernet conectado entre ASUS y Mac

set -euo pipefail
MY_IP="10.164.2.2"
PEER_IP="10.164.2.1"
IFACE="enlace-p2p"

echo "=== [1/3] Eliminar .link peligroso (evita rename que cuelgue systemd-networkd) ==="
sudo rm -f /etc/systemd/network/10-enlace-directo.link
echo "  OK"

echo "=== [2/3] Crear .network (configuración P2P persistente) ==="
sudo tee /etc/systemd/network/10-enlace-directo.network > /dev/null << 'NETWORK'
[Match]
Name=enxa0cec8f833f0

[Network]
Address=10.164.2.2/30
LinkLocalAddressing=no
IPv6AcceptRA=no
NETWORK
echo "  OK"

echo "=== [3/3] Aplicar configuración SIN restart global ==="
# 1. Verificar que la interfaz existe
if ! ip link show "$IFACE" &>/dev/null; then
    echo "  ERROR: Interfaz $IFACE no encontrada"
    echo "  Conecta el cable USB-Ethernet y verifica con: ip link show"
    exit 1
fi

# 2. Verificar que el cable está conectado (carrier detect)
CARRIER=$(cat /sys/class/net/"$IFACE"/carrier 2>/dev/null || echo 0)
if [ "$CARRIER" != "1" ]; then
    echo "  AVISO: Cable no detectado (carrier=0). La config se aplicará cuando conectes el cable."
    echo "  Después de conectar, ejecuta: sudo networkctl reconfigure $IFACE"
else
    echo "  Cable detectado (carrier=1). Aplicando configuración..."
    sudo networkctl reconfigure "$IFACE" 2>&1 || echo "  networkctl falló, intentando ip link..."
    sudo ip link set "$IFACE" up 2>/dev/null || true
    sudo ip addr add "$MY_IP/30" dev "$IFACE" 2>/dev/null || true
fi

echo "=== Validación ==="
sleep 1
if ping -c 2 -W 2 "$PEER_IP" &>/dev/null; then
    echo "  P2P OK: $PEER_IP responde"
else
    echo "  P2P: $PEER_IP no responde. ¿Mac configurado?"
    echo "  En Mac: sudo bash scripts/pro/persist_p2p_mac.sh"
fi

echo ""
echo "=== Resumen ==="
echo "  Interfaz: $IFACE"
echo "  IP: $MY_IP/30"
echo "  Peer: $PEER_IP"
echo "  Config: /etc/systemd/network/10-enlace-directo.network"
