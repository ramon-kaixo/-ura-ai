#!/bin/bash
# Montar URA en Mac via SSHFS
# Uso: bash scripts/pro/mac_mount.sh
# Prerrequisito: brew install macfuse sshfs

ASUS_IP="${1:-10.164.1.99}"
MNT="/Volumes/URA"

echo "Montando ramon@$ASUS_IP:/home/ramon/URA en $MNT..."
mkdir -p "$MNT"
sshfs "ramon@$ASUS_IP:/home/ramon/URA" "$MNT" \
    -o allow_other,defer_permissions,volname=URA,reconnect,ServerAliveInterval=15

if [ $? -eq 0 ]; then
    echo "OK: $MNT montado"
    echo "Desmontar: umount $MNT"
else
    echo "ERROR: No se pudo montar"
    echo "Verifica: brew install macfuse sshfs"
fi
