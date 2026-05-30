#!/bin/bash
# setup_ssh_gx10.sh - Configura acceso SSH sin password del Mac al GX10
set -euo pipefail

SSH_DIR="$HOME/.ssh"
KEY_FILE="${SSH_DIR}/id_ura_gx10"
GX10_IP="${1:-10.164.1.99}"
GX10_USER="${2:-root}"

echo "=== Configuracion SSH Mac -> GX10 ==="

# 1. Generar clave si no existe
if [ ! -f "$KEY_FILE" ]; then
    echo "Generando par de claves SSH..."
    ssh-keygen -t ed25519 -C "ura@gx10" -f "$KEY_FILE" -N ""
    echo "   Clave generada: $KEY_FILE"
else
    echo "   Clave existente: $KEY_FILE"
fi

# 2. Copiar clave publica al GX10
echo "Copiando clave publica a ${GX10_USER}@${GX10_IP}..."
echo "   (Se pedira la contraseña del GX10 una ultima vez)"
ssh-copy-id -i "${KEY_FILE}.pub" "${GX10_USER}@${GX10_IP}"

# 3. Configurar alias SSH
echo "Configurando alias SSH..."
cat >> "$SSH_DIR/config" << EOF

Host gx10
    HostName ${GX10_IP}
    User ${GX10_USER}
    IdentityFile ${KEY_FILE}
    StrictHostKeyChecking no
    ConnectTimeout 5
EOF

# 4. Probar conexion
echo "Probando conexion..."
if ssh gx10 "echo OK" 2>/dev/null; then
    echo "   ✅ Conexion SSH sin password configurada correctamente"
else
    echo "   ❌ Fallo en la prueba de conexion"
    exit 1
fi

echo "=== Listo. URA puede gestionar el GX10 remotamente ==="
