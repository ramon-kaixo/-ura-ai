#!/bin/bash
# persist_p2p_mac.sh — Enlace directo Mac → ASUS (subred /30)
# Detecta automáticamente la interfaz USB-C Ethernet activa.
# Idempotente: seguro de ejecutar múltiples veces.
# Uso: sudo bash scripts/pro/persist_p2p_mac.sh

set -euo pipefail
LOG="/var/log/ura-p2p-mac.log"
MY_IP="10.164.2.1"
PEER_IP="10.164.2.2"
MASK="255.255.255.252"
IFACE=""

log() { echo "$(date +%Y-%m-%dT%H:%M:%S) $*" | tee -a "$LOG"; }

log "=== P2P Mac — inicio ==="

# Detectar interfaz USB-C Ethernet activa (en5/en6/en7)
IFACE=""
for cand in en5 en6 en7; do
    st=$(ifconfig "$cand" 2>/dev/null | grep "status: active" || true)
    if [ -n "$st" ]; then
        IFACE="$cand"
        break
    fi
done

if [ -z "$IFACE" ]; then
    log "ERROR: No se detectó interfaz USB-C Ethernet activa"
    log "Conecta el cable entre Mac y ASUS y vuelve a ejecutar"
    exit 1
fi

log "Interfaz detectada: $IFACE"

# Asignar IP estática (efímera hasta reinicio)
if ifconfig "$IFACE" | grep -q "inet $MY_IP"; then
    log "IP $MY_IP ya asignada en $IFACE"
else
    sudo ifconfig "$IFACE" inet "$MY_IP" netmask "$MASK" && log "IP $MY_IP asignada a $IFACE"
fi

# Crear script de reactivación post-suspensión
cat > /tmp/ura-p2p-resume.sh << 'SCRIPT'
#!/bin/bash
# Reactivar enlace P2P tras wake from sleep
for cand in en5 en6 en7; do
    st=$(ifconfig "$cand" 2>/dev/null | grep "status: active" || true)
    if [ -n "$st" ]; then
        if ! ifconfig "$cand" | grep -q "inet 10.164.2."; then
            ifconfig "$cand" inet 10.164.2.1 netmask 255.255.255.252
            logger "URA P2P: reactivado $cand tras sleep"
        fi
        break
    fi
done
SCRIPT
chmod +x /tmp/ura-p2p-resume.sh

# Registrar script de reactivación post-suspensión (best-effort)
sudo cp /tmp/ura-p2p-resume.sh /Library/Scripts/ura-p2p-resume.sh 2>/dev/null || true
if command -v sleepwatcher &>/dev/null; then
    log "sleepwatcher detectado"
else
    log "Sin sleepwatcher: tras suspensión, ejecuta: sudo bash scripts/pro/persist_p2p_mac.sh"
fi

# Ping de validación
if ping -c 2 -t 2 "$PEER_IP" &>/dev/null; then
    log "VALIDACION OK: $PEER_IP responde (latencia media $(ping -c 3 -t 2 "$PEER_IP" 2>&1 | tail -1 | awk -F/ '{print $5}') ms)"
else
    log "VALIDACION: $PEER_IP no responde. ¿Cable conectado y ASUS configurado?"
fi

log "=== P2P Mac — fin ==="
