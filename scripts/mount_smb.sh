#!/bin/bash
set -euo pipefail
# mount_smb.sh — Monta automaticamente el volumen SMB usando credenciales del Keychain
SMB_SERVER="10.164.1.99"
SMB_USER="barkaixo"
SMB_SHARE="Compartida"
SMB_URL="smb://${SMB_USER}@${SMB_SERVER}/${SMB_SHARE}"
MOUNT_POINT="/Volumes/Compartida"
MAX_RETRIES=5
RETRY_DELAY=10

# Obtener contraseña del Keychain
PASSWORD=$(security find-internet-password -s "$SMB_SERVER" -w 2>/dev/null || true)

# Verificar si ya esta montado
if mount | grep -q "$MOUNT_POINT"; then
    echo "Volumen SMB ya montado en $MOUNT_POINT"
    exit 0
fi

# Intentar montar con osascript (usa las credenciales guardadas en Keychain)
for i in $(seq 1 $MAX_RETRIES); do
    echo "Intento $i/$MAX_RETRIES: montando $SMB_URL..."

    # osascript usa automaticamente las credenciales del Keychain si existen
    osascript -e "try" -e "mount volume \"$SMB_URL\"" -e "end try" 2>/dev/null && {
        sleep 2
        if mount | grep -q "$MOUNT_POINT"; then
            echo "Volumen montado correctamente en $MOUNT_POINT"
            exit 0
        fi
    }

    # Fallback: montaje directo con password del Keychain
    if [ -n "$PASSWORD" ]; then
        mkdir -p "$MOUNT_POINT" 2>/dev/null || true
        if mount_smbfs "//${SMB_USER}:${PASSWORD}@${SMB_SERVER}/${SMB_SHARE}" "$MOUNT_POINT" 2>/dev/null; then
            echo "Volumen montado correctamente en $MOUNT_POINT (mount_smbfs)"
            exit 0
        fi
    fi

    echo "Intento $i fallido. Esperando ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

echo "No se pudo montar el volumen tras $MAX_RETRIES intentos."
exit 1
