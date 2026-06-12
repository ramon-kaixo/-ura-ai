#!/bin/bash
# OpenClaw Network Lock — Aislamiento de salida WAN via iptables
# Lock: bloquea todo tráfico saliente del proceso openclaw excepto localhost
# Unlock: restaura reglas originales
# Uso: ./openclaw_netlock.sh [lock|unlock|status]

ACTION="${1:-status}"
OPENCLAW_UID=$(id -u ramon)
CHAIN="URA_OPENCLAW"

case "$ACTION" in
  lock)
    echo "🔒 Bloqueando salida WAN de OpenClaw..."
    # Crear cadena
    iptables -N "$CHAIN" 2>/dev/null || iptables -F "$CHAIN"
    # Permitir loopback (Ollama localhost)
    iptables -A "$CHAIN" -o lo -j ACCEPT
    # Permitir Tailscale (MCP)
    iptables -A "$CHAIN" -o tailscale0 -j ACCEPT
    # Permitir establecidas
    iptables -A "$CHAIN" -m state --state ESTABLISHED,RELATED -j ACCEPT
    # Bloquear resto salida
    iptables -A "$CHAIN" -j LOG --log-prefix "OPENCLAW_BLOCK: " --log-limit 5/min
    iptables -A "$CHAIN" -j DROP
    # Insertar al inicio de OUTPUT
    iptables -I OUTPUT 1 -m owner --uid-owner "$OPENCLAW_UID" -j "$CHAIN"
    echo "✅ OpenClaw aislado (solo loopback + Tailscale)"
    ;;
  unlock)
    echo "🔓 Desbloqueando OpenClaw..."
    iptables -D OUTPUT -m owner --uid-owner "$OPENCLAW_UID" -j "$CHAIN" 2>/dev/null || true
    iptables -F "$CHAIN" 2>/dev/null || true
    iptables -X "$CHAIN" 2>/dev/null || true
    echo "✅ OpenClaw desbloqueado"
    ;;
  status)
    if iptables -C OUTPUT -m owner --uid-owner "$OPENCLAW_UID" -j "$CHAIN" 2>/dev/null; then
      echo "🔒 BLOQUEADO — OpenClaw sin acceso WAN"
    else
      echo "🔓 LIBRE — OpenClaw con acceso WAN completo"
    fi
    ;;
  *)
    echo "Uso: $0 [lock|unlock|status]"
    exit 1
    ;;
esac
