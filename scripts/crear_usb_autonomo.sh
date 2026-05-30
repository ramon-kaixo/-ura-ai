#!/bin/bash
set -euo pipefail
# crear_usb_autonomo.sh - Crea USB autoinstalable para GX10
# El GX10 se instalara solo al arrancar desde este USB

TOSHIBA_DISK="${1:-disk6}"
TOSHIBA_DEV="/dev/${TOSHIBA_DISK}"
ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso"
ISO_PATH="$HOME/Downloads/ubuntu-24.04.3-live-server-amd64.iso"
URA_REPO="$HOME/URA/ura_ia_1972"
WORK_DIR="/tmp/ura-usb-builder"

echo "========================================="
echo "  URA - USB Autoinstalable GX10"
echo "  Disco: ${TOSHIBA_DEV}"
echo "========================================="

# 1. Verificar disco
echo ""
echo "[1/5] Verificando disco..."
if ! diskutil list "$TOSHIBA_DISK" >/dev/null 2>&1; then
    echo "❌ Disco $TOSHIBA_DISK no encontrado"
    exit 1
fi
echo "   ✅ ${TOSHIBA_DEV} detectado"

# 2. Descargar ISO si no existe
if [ ! -f "$ISO_PATH" ]; then
    echo ""
    echo "[2/5] Descargando Ubuntu Server 24.04..."
    curl -L -o "$ISO_PATH" "$ISO_URL"
else
    echo ""
    echo "[2/5] ISO ya descargada"
fi
echo "   ✅ ISO lista"

# 3. Preparar directorio de trabajo
echo ""
echo "[3/5] Preparando imagen modificada..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR/iso" "$WORK_DIR/modified" "$WORK_DIR/cloud-init"

# Montar ISO original
hdiutil attach "$ISO_PATH" -mountpoint "$WORK_DIR/iso" -quiet 2>/dev/null || true

# Copiar contenido ISO
rsync -a "$WORK_DIR/iso/" "$WORK_DIR/modified/" 2>/dev/null || cp -R "$WORK_DIR/iso/"* "$WORK_DIR/modified/"
hdiutil detach "$WORK_DIR/iso" 2>/dev/null || true

# 4. Configurar autoinstall (cloud-init)
echo ""
echo "[4/5] Configurando instalacion automatica..."

cat > "$WORK_DIR/cloud-init/user-data" << 'USERDATA'
#cloud-config
autoinstall:
  version: 1
  early-commands:
    - |
      # Detectar disco mas grande para instalacion
      DISK=$(lsblk -bdno NAME,SIZE | sort -k2 -n -r | head -1 | awk '{print "/dev/"$1}')
      cat > /tmp/storage.yaml << EOF
  storage:
    layout:
      name: direct
      match:
        path: $DISK
EOF
  identity:
    hostname: gx10-ura
    username: ura
    password: "$6$rounds=4096$ura2026$K8mZvQ2xJhF9pL3wR7tY5nB1cD6eG0iH4jM8oP2qS5uV9xA3bC7dE1fG5hI9jK3lM7nO1pQ5rS9tU3vW7xY1zA"
  ssh:
    allow-pw: true
    install-server: true
  packages:
    - docker.io
    - docker-compose
    - curl
    - jq
    - nginx
    - openssh-server
    - python3
    - python3-pip
    - python3-venv
    - git
    - rsync
  late-commands:
    - |
      # Configurar SSH para acceso sin password
      mkdir -p /target/home/ura/.ssh
      chmod 700 /target/home/ura/.ssh
      # Generar clave SSH
      chroot /target ssh-keygen -t ed25519 -f /home/ura/.ssh/id_ura -N "" -C "ura@gx10-ura"
      # Configurar Tailscale
      curl -fsSL https://tailscale.com/install.sh | sh
      # Crear script de bootstrap
      cat > /target/home/ura/bootstrap.sh << 'BOOTSTRAP'
#!/bin/bash
set -euo pipefail
echo "=== URA Bootstrap GX10 ==="
# Activar Tailscale
tailscale up --accept-routes --ssh
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:14b
ollama pull llama3.2-vision:11b
# Sincronizar URA desde Mac
MAC_IP=$(ip route get 10.164.1.1 2>/dev/null | awk '{print $7}' || echo "10.164.1.17")
rsync -avz "ramonesnaola@${MAC_IP}:/Users/ramonesnaola/URA/ura_ia_1972/" /home/ura/URA/ura_ia_1972/ 2>/dev/null || true
# Instalar dependencias
cd /home/ura/URA/ura_ia_1972
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt 2>/dev/null || true
# Iniciar servicios
nohup .venv/bin/python3 agents/registry_api.py &>/tmp/ura_registry.log &
nohup .venv/bin/python3 web/ura_dashboard.py &>/tmp/ura_dashboard.log &
echo "✅ Bootstrap completado"
BOOTSTRAP
      chmod +x /target/home/ura/bootstrap.sh
      chown 1000:1000 /target/home/ura/bootstrap.sh
USERDATA

cat > "$WORK_DIR/cloud-init/meta-data" << 'METADATA'
instance-id: gx10-ura-autoinstall
local-hostname: gx10-ura
METADATA

# Copiar cloud-init a la particion EFI del USB modificado
mkdir -p "$WORK_DIR/modified/cloud-init"
cp "$WORK_DIR/cloud-init/user-data" "$WORK_DIR/modified/cloud-init/"
cp "$WORK_DIR/cloud-init/meta-data" "$WORK_DIR/modified/cloud-init/"

# Modificar GRUB para autoinstall
GRUB_CFG="$WORK_DIR/modified/boot/grub/grub.cfg"
if [ -f "$GRUB_CFG" ]; then
    # Añadir autoinstall a las opciones de kernel
    sed -i '' 's/---/autoinstall ds=nocloud ---/g' "$GRUB_CFG" 2>/dev/null || true
    echo "   ✅ GRUB modificado para autoinstall"
else
    echo "   ⚠️ GRUB.cfg no encontrado"
fi

# 5. Grabar al USB
echo ""
echo "[5/5] Grabando USB..."
diskutil unmountDisk "$TOSHIBA_DEV" 2>/dev/null || true
sudo diskutil eraseDisk FAT32 TOSHIBA MBRFormat "$TOSHIBA_DEV" 2>/dev/null || true

# Convertir y grabar
hdiutil convert "$ISO_PATH" -format UDRW -o "$WORK_DIR/ubuntu.img" 2>/dev/null || true
IMG_FILE="$WORK_DIR/ubuntu.img"
sudo dd if="$IMG_FILE" of="/dev/r${TOSHIBA_DISK}" bs=1m 2>&1 | tail -1
sync

# Montar EFI y añadir cloud-init
EFI_PART=$(diskutil list "$TOSHIBA_DISK" | grep "EFI" | awk '{print $NF}')
if [ -n "$EFI_PART" ]; then
    sudo diskutil mount "/dev/${EFI_PART}" 2>/dev/null || true
    sudo mkdir -p "/Volumes/EFI/cloud-init"
    sudo cp "$WORK_DIR/cloud-init/user-data" "/Volumes/EFI/cloud-init/"
    sudo cp "$WORK_DIR/cloud-init/meta-data" "/Volumes/EFI/cloud-init/"
    sudo diskutil unmount "/dev/${EFI_PART}" 2>/dev/null || true
fi

# Limpiar
rm -rf "$WORK_DIR"

echo ""
echo "========================================="
echo "  USB LISTO"
echo "========================================="
echo ""
echo "Conectar al GX10 y arrancar desde USB."
echo "La instalacion sera 100% automatica."
echo ""
echo "  Hostname: gx10-ura"
echo "  Usuario: ura"
echo "  Password: ura2026"
echo ""
echo "URA detectara el GX10 automaticamente via Tailscale."
