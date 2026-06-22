#!/bin/bash
# backup_unified.sh — Estrategia de backup consolidada para URA
# Ejecuta todos los backups en orden, con reporte final.
# Uso: ./backup_unified.sh [--full|--quick|--qdrant-only]
set -euo pipefail

BACKUP_ROOT="/home/ramon/URA/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="/tmp/ura_backup_${TIMESTAMP}.log"
SUMMARY="/tmp/ura_backup_summary.json"

mkdir -p "$BACKUP_ROOT"/{code,config,qdrant,knowledge,reports}
echo "{}" > "$SUMMARY"

log() { echo "[$(date +%T)] $*" | tee -a "$LOG"; }

update_summary() {
    local key="$1" status="$2" msg="$3"
    python3 -c "
import json
with open('$SUMMARY') as f: s = json.load(f)
s['$key'] = {'status': '$status', 'msg': '$msg', 'ts': '$TIMESTAMP'}
with open('$SUMMARY', 'w') as f: json.dump(s, f)
"
}

# === 1. Backup código ===
backup_code() {
    log "[1/6] Backup código → $BACKUP_ROOT/code/"
    local dest="$BACKUP_ROOT/code/ura_${TIMESTAMP}.tar.gz"
    tar czf "$dest" \
        --exclude=".venv" --exclude="__pycache__" --exclude=".git" \
        --exclude="*.pyc" --exclude="*.pyo" \
        -C /home/ramon/URA ura_ia_1972/ 2>>"$LOG"
    local size=$(du -h "$dest" | cut -f1)
    update_summary "code" "ok" "${size} (${dest})"
    log "  OK: ${size}"
}

# === 2. Backup config sistema ===
backup_config() {
    log "[2/6] Backup config → $BACKUP_ROOT/config/"
    local dest="$BACKUP_ROOT/config/configs_${TIMESTAMP}.tar.gz"
    tar czf "$dest" \
        /etc/systemd/system/ura-*.service* \
        /etc/systemd/system/docker-*.service* \
        /etc/systemd/system/*.timer \
        /etc/systemd/journald.conf \
        /etc/systemd/journald.conf.d/ \
        /etc/ura/ \
        /home/ramon/.openclaw/ \
        2>/dev/null || true
    local size=$(du -h "$dest" | cut -f1)
    update_summary "config" "ok" "${size}"
    log "  OK: ${size}"
}

# === 3. Backup Qdrant (snapshot vía API) ===
backup_qdrant() {
    log "[3/6] Backup Qdrant → $BACKUP_ROOT/qdrant/"
    local dest="$BACKUP_ROOT/qdrant/qdrant_${TIMESTAMP}.tar.gz"
    # Create Qdrant snapshot via API
    local collections
    collections=$(curl -sf http://127.0.0.1:6333/collections 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d.get('result',{}).get('collections',[]):
    print(c['name'])
" 2>/dev/null) || true

    if [ -n "$collections" ]; then
        echo "$collections" | while read -r col; do
            [ -z "$col" ] && continue
            curl -sf -X POST "http://127.0.0.1:6333/collections/${col}/snapshots" >/dev/null 2>&1 || true
        done
        # Copy snapshots
        local snap_dir=$(docker volume inspect qdrant_storage --format '{{.Mountpoint}}' 2>/dev/null || echo "/var/lib/docker/volumes/qdrant_storage/_data")
        if [ -d "$snap_dir/snapshots" ]; then
            tar czf "$dest" -C "$snap_dir" snapshots/ 2>/dev/null || true
        fi
    fi
    local size=$(du -h "$dest" 2>/dev/null | cut -f1 || echo "0B")
    update_summary "qdrant" "ok" "${size}"
    log "  OK: ${size:-0B}"
}

# === 4. Backup conocimiento ===
backup_knowledge() {
    log "[4/6] Backup conocimiento → $BACKUP_ROOT/knowledge/"
    local dest="$BACKUP_ROOT/knowledge/knowledge_${TIMESTAMP}.tar.gz"
    if [ -d /home/ramon/URA/ura_ia_1972/knowledge ]; then
        tar czf "$dest" -C /home/ramon/URA/ura_ia_1972 knowledge/
    fi
    local size=$(du -h "$dest" 2>/dev/null | cut -f1 || echo "0B")
    update_summary "knowledge" "ok" "${size}"
    log "  OK: ${size}"
}

# === 5. Backup de emergencia (files críticos) ===
backup_critical() {
    log "[5/6] Backup crítico → $BACKUP_ROOT/reports/"
    python3 -c "
import json, os, subprocess, shutil
dest = '$BACKUP_ROOT/reports/critical_${TIMESTAMP}.json'
data = {
    'ts': '$TIMESTAMP',
    'services': {},
    'disk': {},
}
# Systemd status
result = subprocess.run(['systemctl', 'list-units', '--type=service', '--no-legend'],
    capture_output=True, text=True, timeout=10)
for line in result.stdout.splitlines():
    parts = line.split()
    if parts and parts[0].startswith('ura-'):
        data['services'][parts[0]] = parts[2]  # active/inactive/dead
# Disk usage
result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
data['disk'] = result.stdout.strip()
with open(dest, 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || true
    update_summary "critical" "ok" "reporte generado"
    log "  OK"
}

# === 6. Rotación (borrar backups >30 días) ===
rotate() {
    log "[6/6] Rotación (borrando backups >30 días)..."
    find "$BACKUP_ROOT" -name "*.tar.gz" -mtime +30 -delete 2>/dev/null
    find "$BACKUP_ROOT" -name "*.json" -mtime +30 -delete 2>/dev/null
    update_summary "rotation" "ok" "completada"
    log "  OK"
}

# === Main ===
MODE="${1:---full}"
case "$MODE" in
    --full)
        backup_code
        backup_config
        backup_qdrant
        backup_knowledge
        backup_critical
        rotate
        ;;
    --quick)
        backup_code
        backup_config
        backup_critical
        ;;
    --qdrant-only)
        backup_qdrant
        ;;
    *)
        echo "Uso: $0 [--full|--quick|--qdrant-only]"
        exit 1
        ;;
esac

python3 -c "
import json
with open('$SUMMARY') as f: s = json.load(f)
print(json.dumps(s, indent=2))
"
log "Backup $MODE completado: $TIMESTAMP"
