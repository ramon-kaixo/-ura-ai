#!/bin/bash
# backup_gx10_configs.sh — Backup configuración crítica de GX10 a Mac
# Systemd units, iptables, custom bins, etc. — lo que está FUERA del repo.
# Ejecutar: cron sugerido 0 4 * * * (despues del backup_to_mac.sh)
set -uo pipefail

MAC_USER="ramonesnaola"
MAC_IP="100.123.81.101"
SSH_KEY="/home/ramon/.ssh/id_backup_mac"
MAC_DIR="/Users/ramonesnaola/URA/backups_gx10_configs"
LOG="/home/ramon/URA/logs/backup_gx10_configs.log"
TMPDIR="/tmp/ura_backup_$$"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
ARCHIVE="gx10_configs_${TIMESTAMP}.tar.gz"
RC=0

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

mkdir -p "$TMPDIR/etc/systemd" "$TMPDIR/etc/iptables" "$TMPDIR/etc/logrotate" "$TMPDIR/etc/cloud" "$TMPDIR/etc/ssh" "$TMPDIR/usr/local/bin" "$TMPDIR/home/cron" "$TMPDIR/home/config"
trap "rm -rf $TMPDIR" EXIT

log "=== Backup configs ${TIMESTAMP} ==="

cp -r /etc/systemd/system/ura-*.service "$TMPDIR/etc/systemd/" 2>/dev/null || log "WARN: no ura-*.service"
cp -r /etc/systemd/system/ura-*.timer "$TMPDIR/etc/systemd/" 2>/dev/null || true
cp /etc/systemd/system/openclaw.service "$TMPDIR/etc/systemd/" 2>/dev/null || true
cp /etc/systemd/system/opencode.service "$TMPDIR/etc/systemd/" 2>/dev/null || true

sudo iptables-save > "$TMPDIR/etc/iptables/rules.v4" 2>/dev/null || log "WARN: iptables-save falló"
sudo ip6tables-save > "$TMPDIR/etc/iptables/rules.v6" 2>/dev/null || true

cp /etc/logrotate.d/ura* /etc/logrotate.d/gb10* "$TMPDIR/etc/logrotate/" 2>/dev/null || true
cp /etc/cloud/cloud.cfg.d/99-ura-*.cfg "$TMPDIR/etc/cloud/" 2>/dev/null || true
ls -la /usr/local/bin/ura-* > "$TMPDIR/usr/local/bin/MANIFEST.txt" 2>/dev/null || true
crontab -l > "$TMPDIR/home/cron/crontab_ramon.txt" 2>/dev/null || true
[ -d /home/ramon/.config/opencode ] && cp -r /home/ramon/.config/opencode/*.json* "$TMPDIR/home/config/" 2>/dev/null || true
cp /etc/sysctl.conf "$TMPDIR/etc/" 2>/dev/null || true
cp -r /etc/sysctl.d/ "$TMPDIR/etc/" 2>/dev/null || true
cat /proc/cmdline > "$TMPDIR/etc/cmdline.txt" 2>/dev/null || true

echo "=== TIMESTAMP: $TIMESTAMP ===" > "$TMPDIR/README.txt"
echo "Creado por: backup_gx10_configs.sh" >> "$TMPDIR/README.txt"
hostname >> "$TMPDIR/README.txt"
uname -a >> "$TMPDIR/README.txt"

tar czf "/tmp/$ARCHIVE" -C "$TMPDIR" . 2>&1

if ! ping -c 1 -W 5 "$MAC_IP" >/dev/null 2>&1; then
    log "ERROR: Mac ($MAC_IP) no alcanzable"
    rm -f "/tmp/$ARCHIVE"
    exit 1
fi

scp -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new \
    "/tmp/$ARCHIVE" "${MAC_USER}@${MAC_IP}:${MAC_DIR}/" >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    SIZE=$(du -h "/tmp/$ARCHIVE" | cut -f1)
    log "OK ${SIZE} → ${MAC_DIR}/${ARCHIVE}"
    ssh -i "$SSH_KEY" "${MAC_USER}@${MAC_IP}" \
        "ls -1t ${MAC_DIR}/gx10_configs_* 2>/dev/null | tail -n +15 | xargs -r rm" >> "$LOG" 2>&1 || true
else
    log "ERROR: scp falló"
fi

rm -f "/tmp/$ARCHIVE"
log "=== Fin ==="
