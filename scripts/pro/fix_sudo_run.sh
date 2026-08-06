#!/bin/bash
# fix_sudo_run.sh — Recuperación de /run (montado RO) + sudoers restrictivo
# Ejecutar DESPUÉS de reinicio o cuando sudo funcione
set -euo pipefail

echo "[fix] Remontando /run como RW..."
sudo mount -o remount,rw /run

echo "[fix] Restringiendo sudoers — reemplazando NOPASSWD: ALL por comandos específicos..."
sudo tee /etc/sudoers.d/ura-rescate > /dev/null <<'SUDOERS'
# URA — comandos específicos sin password (restringido desde ALL)
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ura-mochila.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl start ura-*.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop ura-*.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u ura-*.service
ramon ALL=(ALL) NOPASSWD: /sbin/reboot
SUDOERS

sudo visudo -c -f /etc/sudoers.d/ura-rescate && echo "[fix] sudoers OK" || echo "[fix] ERROR en sudoers"

echo "[fix] /run montado:"
findmnt -n -o OPTIONS /run
