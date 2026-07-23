#!/bin/bash
# rescue_hetzner.sh — Recuperación de emergencia para el nodo Hetzner.
# EJECUTAR VIA HETZNER CLOUD CONSOLE (VNC/Rescue) cuando SSH no responde.
# Este script restaura SSH y configura el ambiente URA.
set -euo pipefail

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "=== URA Hetzner Rescue Script ==="

# 1. Verificar que somos root
if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: Ejecutar como root (sudo su -)"
    exit 1
fi

# 2. Restaurar SSH en puerto 2222
log "[1/4] Restaurando SSH en puerto 2222..."
if ! grep -q "^Port 2222" /etc/ssh/sshd_config 2>/dev/null; then
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%s)
    echo "Port 2222" >> /etc/ssh/sshd_config
    echo "PermitRootLogin prohibit-password" >> /etc/ssh/sshd_config
    echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
    log "  → sshd_config actualizado (Port 2222)"
else
    log "  → Port 2222 ya configurado"
fi

# 3. Asegurar que sshd está habilitado y corriendo
log "[2/4] Asegurando sshd...
systemctl enable sshd 2>/dev/null || systemctl enable ssh 2>/dev/null || true
systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || {
    log "  ERROR: No se pudo reiniciar sshd"
    exit 1
}
log "  → sshd activo en puerto 2222"

# 4. Crear usuario ramon y configurar claves
log "[3/4] Configurando usuario ramon..."
if ! id ramon &>/dev/null; then
    useradd -m -s /bin/bash ramon
    usermod -aG sudo ramon
    log "  → Usuario ramon creado"
fi

mkdir -p /home/ramon/.ssh
chmod 700 /home/ramon/.ssh

# Clave pública del watchdog de URA
if ! grep -q "ura-watchdog" /home/ramon/.ssh/authorized_keys 2>/dev/null; then
    cat >> /home/ramon/.ssh/authorized_keys << 'KEYS'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKD2VJo8PQkE6u1XZSsBDBX6sE9l5ERyyEgZYz2tgj2Q ramon@gx10-64c3
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDU8sz50mRh5GFr5jflNPA8cZXtZG4M8BxJFq16Bf94qMgOUq0zZ5vCld1Pe6Rq6sKnSF+6meu5aC9t6JiqbH2bC4bQ+kS7Y9ME8t5jBEGExwXjG1s/KjHhI9q74TA9T4NWBLysBc5vFPBkOY7SFM6UqFqS/6qTnvF6vH7Hm2D+9rVYTrPYidGUISK5AuLCb1VHG+WT5gY7lsDo8lNtxZ4v+PBOKZ3nEDXTBGJGqFLp73oHLBl9F+z/1xPbFHF1HKpP8TtOp+IR7j3z/GYXvVmF2KYtA5UNbkCrzddWVPP0bG5rx0/FRyXjQB57YZ6eJ4GDhQFaHPOTu3sKDYrh/ryNZaqKDVjg+yFsftB11v6nVmS+nrElUKI3vYDnKLPSC/QjI62vjWAr6Yj6sVNMb4OYLQYY0GBCAtDMA7Tf0PC6nSaFnFbA0OAUF4UeF7EHNrj8vwSGLWxND3FBnvo2WxkBLKTCRgP1VPW5rG8WApepRGeA9XYYjy4v3cO+GPE12k= ramon@gx10-64c3
KEYS
    log "  → Clave watchdog añadida"
fi

chmod 600 /home/ramon/.ssh/authorized_keys
chown -R ramon:ramon /home/ramon/.ssh

# 5. Preparar directorios de scraping
log "[4/4] Preparando directorios de scraping..."
mkdir -p /home/ramon/scraping/data
chown -R ramon:ramon /home/ramon/scraping

# 6. Verificar Tailscale
log "[INFO] Verificando Tailscale..."
tailscale status 2>/dev/null && log "  → Tailscale activo" || log "  → Tailscale no activo (no critico)"

log "=== RECUPERACION COMPLETADA ==="
log "SSH: root@178.105.81.83 -p 2222"
log "Luego ejecuta en GX10: bash scripts/pro/deploy_to_hetzner.sh"
