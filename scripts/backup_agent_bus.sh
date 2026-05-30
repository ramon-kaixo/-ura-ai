#!/bin/bash
set -euo pipefail
# Buscar agent_bus.db en ubicaciones comunes
ORIGEN=""
for p in "/opt/ura/data/agent_bus.db" "$HOME/agent_bus.db" "$HOME/URA/ura_ia_1972/data/agent_bus.db" "/tmp/agent_bus.db"; do
    if [ -f "$p" ]; then
        ORIGEN="$p"
        break
    fi
done

if [ -z "$ORIGEN" ]; then
    echo "$(date) - agent_bus.db no encontrado en ninguna ubicacion" >> /opt/ura/logs/backup_agent_bus.log
    exit 0
fi

DEST_DIR="/opt/ura/backups"
mkdir -p "$DEST_DIR"
DESTINO="$DEST_DIR/agent_bus_$(date +%Y%m%d_%H%M%S).db"

cp "$ORIGEN" "$DESTINO"
OC=$(sqlite3 "$ORIGEN" "SELECT count(*) FROM agents" 2>/dev/null || echo 0)
BC=$(sqlite3 "$DESTINO" "SELECT count(*) FROM agents" 2>/dev/null || echo 0)
if [ "$OC" != "$BC" ]; then
    echo "$(date) - ERROR: Backup inconsistente ($OC vs $BC)" >> /opt/ura/logs/backup_agent_bus.log
    /opt/ura/scripts/notificar.sh "Backup de Agent Bus inconsistente" 2>/dev/null || true
else
    echo "$(date) - Backup verificado: $OC agentes" >> /opt/ura/logs/backup_agent_bus.log
fi

find "$DEST_DIR" -name "agent_bus_*.db" -mtime +7 -delete
