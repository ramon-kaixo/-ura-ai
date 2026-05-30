#!/bin/bash
set -euo pipefail
# vault.sh — Cifra y descifra config/.env con GPG (simetrico)
VAULT_DIR="${HOME}/URA/ura_ia_1972/config"
PLAIN="${VAULT_DIR}/.env"
ENCRYPTED="${VAULT_DIR}/.env.gpg"
TEMP="/tmp/ura_env_$$"
PASS="${VAULT_PASSPHRASE:-}"

command -v gpg >/dev/null 2>&1 || { echo "Instalar: brew install gnupg"; exit 1; }

case "${1:-}" in
    encrypt)
        [ ! -f "$PLAIN" ] && { echo "No existe $PLAIN"; exit 1; }
        if [ -n "$PASS" ]; then
            gpg --symmetric --passphrase "$PASS" --batch --output "$ENCRYPTED" "$PLAIN"
        else
            gpg --symmetric --output "$ENCRYPTED" "$PLAIN"
        fi
        chmod 600 "$ENCRYPTED"
        echo "OK config/.env.gpg"
        ;;
    decrypt)
        [ ! -f "$ENCRYPTED" ] && { echo "No existe $ENCRYPTED"; exit 1; }
        if [ -n "$PASS" ]; then
            gpg --decrypt --passphrase "$PASS" --batch --output "$TEMP" "$ENCRYPTED" 2>/dev/null
        else
            gpg --decrypt --output "$TEMP" "$ENCRYPTED" 2>/dev/null
        fi
        chmod 600 "$TEMP"
        echo "$TEMP"
        ;;
    *)
        echo "Uso: VAULT_PASSPHRASE='...' vault.sh encrypt | decrypt"
        exit 1
        ;;
esac
