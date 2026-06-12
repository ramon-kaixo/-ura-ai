#!/bin/bash
# OpenClaw Network Lock — Aislamiento WAN via iptables + cgroup v2
# Apunta SOLO al proceso openclaw.service (no afecta otros procesos de ramon)
ACTION="${1:-status}"
CHAIN="URA_OPENCLAW"
OPENCLAW_CG="/system.slice/openclaw.service"

case "$ACTION" in
  lock)
    echo "🔒 Bloqueando salida WAN de OpenClaw..."
    sudo iptables -N "$CHAIN" 2>/dev/null || sudo iptables -F "$CHAIN"
    sudo iptables -F "$CHAIN"
    sudo iptables -A "$CHAIN" -o lo -j ACCEPT
    sudo iptables -A "$CHAIN" -o tailscale0 -j ACCEPT
    sudo iptables -A "$CHAIN" -m state --state ESTABLISHED,RELATED -j ACCEPT
    sudo iptables -A "$CHAIN" -j LOG --log-prefix "OPENCLAW_BLOCK: "
    sudo iptables -A "$CHAIN" -j DROP
    sudo iptables -I OUTPUT 1 -m cgroup --path "$OPENCLAW_CG" -j "$CHAIN"
    echo "✅ OpenClaw aislado (solo Ollama + Tailscale)"
    ;;
  unlock)
    echo "🔓 Desbloqueando..."
    sudo iptables -D OUTPUT -m cgroup --path "$OPENCLAW_CG" -j "$CHAIN" 2>/dev/null || true
    sudo iptables -F "$CHAIN" 2>/dev/null || true
    sudo iptables -X "$CHAIN" 2>/dev/null || true
    echo "✅ OpenClaw desbloqueado"
    ;;
  status)
    if sudo iptables -C OUTPUT -m cgroup --path "$OPENCLAW_CG" -j "$CHAIN" 2>/dev/null; then
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
