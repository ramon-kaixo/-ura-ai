#!/bin/bash
set -euo pipefail
# crear_usb_gx10.sh - Crea USB booteable de Ubuntu Server para GX10
# Incluye configuracion post-instalacion automatica

TOSHIBA_DISK="${1:-disk6}"
TOSHIBA_DEV="/dev/${TOSHIBA_DISK}"
ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso"
ISO_PATH="$HOME/Downloads/ubuntu-24.04.3-live-server-amd64.iso"
URA_REPO="$HOME/URA/ura_ia_1972"

echo "========================================="
echo "  URA - USB Ubuntu Server para GX10"
echo "========================================="

# 1. Verificar
if ! diskutil list "$TOSHIBA_DISK" >/dev/null 2>&1; then
    echo "❌ Disco $TOSHIBA_DISK no encontrado"
    exit 1
fi

# 2. Descargar ISO
if [ ! -f "$ISO_PATH" ]; then
    echo "Descargando Ubuntu Server 24.04..."
    curl -L -o "$ISO_PATH" "$ISO_URL"
fi

# 3. Grabar
echo "Grabando al Toshiba..."
diskutil unmountDisk "$TOSHIBA_DEV" 2>/dev/null || true
hdiutil convert "$ISO_PATH" -format UDRW -o /tmp/ubuntu-gx10.img 2>/dev/null || true
sudo dd if=/tmp/ubuntu-gx10.img of="/dev/r${TOSHIBA_DISK}" bs=1m 2>&1 | tail -1
sync
rm -f /tmp/ubuntu-gx10.img

echo ""
echo "✅ USB listo"
echo ""
echo "PASOS:"
echo "1. Conectar Toshiba al GX10"
echo "2. Encender GX10, pulsar F8 para boot menu"
echo "3. Seleccionar Toshiba"
echo "4. Instalar Ubuntu Server (usuario: ura, password: ura2026)"
echo "5. Tras instalar, ejecutar en el GX10:"
echo ""
echo "   bash <(curl -s http://$(ipconfig getifaddr en0 2>/dev/null || echo '10.164.1.17'):8080/bootstrap_gx10.sh)"
echo ""
echo "URA detectara el GX10 automaticamente via Tailscale."
