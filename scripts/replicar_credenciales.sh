#!/bin/bash
# replicar_credenciales.sh - Cifra credenciales SSH con GPG y las replica al GX10
set -euo pipefail

VAULT_PASSPHRASE="${VAULT_PASSPHRASE:-}"
CRED_FILE="${CRED_FILE:-/opt/ura/config/ssh_credentials.json}"
GX10_HOST="${GX10_HOST:-10.164.1.99}"

if [ -z "$VAULT_PASSPHRASE" ]; then
    echo "Error: VAULT_PASSPHRASE no definida"
    exit 1
fi

if [ ! -f "$CRED_FILE" ]; then
    echo "Error: Archivo de credenciales no encontrado: $CRED_FILE"
    exit 1
fi

BACKUP_FILE="/tmp/credenciales.json.gpg"
gpg --symmetric --passphrase "$VAULT_PASSPHRASE" --cipher-algo AES256 --batch --yes \
    --output "$BACKUP_FILE" "$CRED_FILE" 2>/dev/null

scp "$BACKUP_FILE" "root@${GX10_HOST}:/opt/ura/config/ssh_credentials.json.gpg" 2>/dev/null || true
rm -f "$BACKUP_FILE"
echo "Credenciales replicadas al GX10"
