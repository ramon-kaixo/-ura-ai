#!/bin/bash
# ================================================================
# INSTALAR TAILSCALE EN HETZNER — Copiar/pegar en Hetzner Cloud Console
# ================================================================
# Uso: 
#   1. Abrir Hetzner Cloud Console (https://console.hetzner.com)
#   2. Seleccionar el servidor de 16GB
#   3. Abrir "Console" (acceso root directo)
#   4. Pegar TODO este script y ejecutar
# ================================================================
# Propietario: Ramon Esnaola
# Licencia:    K0513893926
# Email:       barkaixo@gmail.com
# DNS:         hetzner-escudo
# ================================================================

set -euo pipefail

echo "╔══════════════════════════════════════════════════════╗"
echo "║  INSTALACIÓN TAILSCALE — HETZNER ESCUDO              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Paso 1: Actualizar sistema ──
echo "=== Paso 1/6: Actualizar sistema ==="
apt-get update -qq && apt-get upgrade -y -qq
echo "  ✅ Sistema actualizado"

# ── Paso 2: Instalar Tailscale ──
echo ""
echo "=== Paso 2/6: Instalar Tailscale ==="
curl -fsSL https://tailscale.com/install.sh | sh
echo "  ✅ Tailscale instalado"

# ── Paso 3: Activar IP forwarding (necesario para exit node) ──
echo ""
echo "=== Paso 3/6: Activar IP forwarding ==="
echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
echo 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.conf
sysctl -p /etc/sysctl.conf
echo "  ✅ IP forwarding activado"

# ── Paso 4: Conectar a la tailnet ──
echo ""
echo "=== Paso 4/6: Conectar Tailscale ==="
tailscale up --hostname=hetzner-escudo --advertise-exit-node --accept-routes
echo ""
echo "  ⚠️  IMPORTANTE: Abre este enlace en tu navegador para autenticar:"
echo "     https://login.tailscale.com/admin/machines"
echo "     Busca 'hetzner-escudo' → ... → Edit route settings → ✅ Exit Node"
echo ""
echo "  Pulsa ENTER después de aprobar el exit node en el dashboard..."
read -r

# ── Paso 5: Configurar iptables (firewall + NAT para exit node) ──
echo ""
echo "=== Paso 5/6: Configurar firewall iptables ==="

# Encontrar interfaz de red principal
IFACE=$(ip route show default | awk '/default/ {print $5}')
echo "  Interfaz principal detectada: $IFACE"

# Reglas de NAT para exit node
iptables -t nat -A POSTROUTING -o "$IFACE" -j MASQUERADE
iptables -A FORWARD -i tailscale0 -o "$IFACE" -j ACCEPT
iptables -A FORWARD -i "$IFACE" -o tailscale0 -m state --state ESTABLISHED,RELATED -j ACCEPT

# Guardar reglas
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent 2>/dev/null || true
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
echo "  ✅ Firewall configurado (NAT para exit node)"

# ── Paso 6: Filtrado de tráfico (whitelist) ──
echo ""
echo "=== Paso 6/6: Filtrado de tráfico (solo puertos necesarios) ==="

# Limpiar reglas forward existentes (mantener NAT)
iptables -F FORWARD 2>/dev/null || true

# Permitir tráfico establecido
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# Permitir salida desde tailscale a Internet (solo puertos seguros)
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p tcp --dport 80   -j ACCEPT  # HTTP
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p tcp --dport 443  -j ACCEPT  # HTTPS
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p udp --dport 53   -j ACCEPT  # DNS
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p tcp --dport 22   -j ACCEPT  # SSH
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p tcp --dport 11434 -j ACCEPT # Ollama
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p udp --dport 1194 -j ACCEPT # OpenVPN
iptables -A FORWARD -i tailscale0 -o "$IFACE" -p tcp --dport 8080 -j ACCEPT # Alt HTTP

# Bloquear todo lo demás
iptables -A FORWARD -i tailscale0 -o "$IFACE" -j DROP

# Guardar
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
echo "  ✅ Filtrado aplicado (HTTP/HTTPS/DNS/SSH/Ollama)"

# ── Verificación ──
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ INSTALACIÓN COMPLETADA                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Verificación:"
echo "  Hostname:   $(hostname)"
echo "  Tailscale:  $(tailscale status 2>/dev/null | head -1 || echo 'revisar dashboard')"
echo "  IP:         $(tailscale ip -4 2>/dev/null || echo 'pendiente')"
echo ""
echo "Próximo paso: En ASUS ejecutar:"
echo "  tailscale up --exit-node=hetzner-escudo --exit-node-allow-lan-access"
echo "  curl httpbin.org/ip  # Debe mostrar la IP de Hetzner"
