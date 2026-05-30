#!/bin/bash
# Script de configuración para VM OpenClaw en UTM
# NOTA: Este script asume que la VM ya está creada en UTM
# Para crear la VM, sigue las instrucciones en README_N3_VM.md

set -e

TOSHIBA_PATH="/Volumes/TOSHIBA_NUEVO"
PROJECT_PATH="/Users/ramonesnaola/URA/ura_ia_1972"
TRAINING_DIR="$TOSHIBA_PATH/URA_entrenamiento"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar Toshiba conectado
check_toshiba() {
    log_info "Verificando disco Toshiba..."
    if [ ! -d "$TOSHIBA_PATH" ]; then
        log_error "Disco Toshiba no encontrado en $TOSHIBA_PATH"
        log_info "Por favor, conecta el disco Toshiba e intenta de nuevo."
        exit 1
    fi
    log_info "Toshiba encontrado: $TOSHIBA_PATH"
}

# Crear directorio de entrenamiento
create_training_dir() {
    log_info "Creando directorio de entrenamiento..."
    mkdir -p "$TRAINING_DIR"
    mkdir -p "$TRAINING_DIR/respuestas"
    mkdir -p "$TRAINING_DIR/decompose_cache"
    log_info "Directorio creado: $TRAINING_DIR"
}

# Generar archivo .env
generate_env() {
    log_info "Generando archivo .env..."
    cat > "$PROJECT_PATH/.env" << EOF
# Configuración OpenClaw VM
VLLM_URL=http://192.168.64.100:5000
OPENCLAW_VM_IP=192.168.64.100
OPENCLAW_VM_PORT=5000

# Rutas Toshiba
TOSHIBA_PATH=$TOSHIBA_PATH
TRAINING_DIR=$TRAINING_DIR
EOF
    log_info "Archivo .env generado en $PROJECT_PATH/.env"
}

# Crear archivo cloud-init para VM
create_cloud_init() {
    log_info "Creando archivo cloud-init..."
    cat > "$PROJECT_PATH/cloud-init.yaml" << 'EOF'
#cloud-config
package_update: true
package_upgrade: true

packages:
  - curl
  - git
  - python3-pip
  - npm
  - python3-venv

runcmd:
  # Instalar Ollama
  - curl -fsSL https://ollama.com/install.sh | sh
  # Descargar modelo
  - ollama pull qwen2.5:7b
  # Instalar OpenClaw
  - npm install -g openclaw
  # Crear directorio para API
  - mkdir -p /opt/openclaw_api
  # Crear servicio systemd
  - |
    cat > /etc/systemd/system/openclaw-api.service << 'SERVICE'
    [Unit]
    Description=OpenClaw API Server
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/opt/openclaw_api
    ExecStart=/usr/bin/python3 /opt/openclaw_api/server.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    SERVICE
  # Habilitar servicio
  - systemctl daemon-reload
  - systemctl enable openclaw-api.service
  - systemctl start openclaw-api.service
EOF
    log_info "Archivo cloud-init creado en $PROJECT_PATH/cloud-init.yaml"
}

# Crear servidor API para OpenClaw (para copiar en VM)
create_api_server() {
    log_info "Creando servidor API OpenClaw..."
    mkdir -p "$PROJECT_PATH/vm_files"
    cat > "$PROJECT_PATH/vm_files/server.py" << 'EOF'
#!/usr/bin/env python3
"""
Servidor API simple para OpenClaw en VM
Expone endpoints /search y /health
"""

import asyncio
import subprocess
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="OpenClaw API")

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "openclaw-api"}

@app.get("/search")
async def search(q: str):
    """
    Ejecuta búsqueda en OpenClaw.

    Args:
        q: Query de búsqueda

    Returns:
        JSON con respuesta de OpenClaw
    """
    try:
        # Ejecutar OpenClaw
        cmd = ["openclaw", "agent", "--agent", "main", "--message", q, "--json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"OpenClaw error: {stderr.decode()}"
            )

        result = json.loads(stdout.decode())
        return JSONResponse(content=result)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="OpenClaw timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
EOF
    log_info "Servidor API creado en $PROJECT_PATH/vm_files/server.py"
}

# Mostrar instrucciones
show_instructions() {
    log_info "=========================================="
    log_info "Configuración preparada"
    log_info "=========================================="
    echo ""
    log_info "Pasos manuales requeridos:"
    echo ""
    echo "1. Crear VM en UTM:"
    echo "   - Abre UTM"
    echo "   - Crea nueva VM -> Ubuntu Server 24.04 LTS"
    echo "   - 8 GB RAM, 4 CPUs"
    echo "   - Red: Host-Only (IP fija 192.168.64.100)"
    echo "   - Importa cloud-init.yaml en la configuración de la VM"
    echo ""
    echo "2. Configurar carpeta compartida:"
    echo "   - En UTM VM settings -> Shared Directories"
    echo "   - Añade $TRAINING_DIR -> /mnt/toshiba"
    echo ""
    echo "3. Copiar servidor API a VM:"
    echo "   - scp $PROJECT_PATH/vm_files/server.py root@192.168.64.100:/opt/openclaw_api/"
    echo ""
    echo "4. Iniciar VM y verificar:"
    echo "   - curl http://192.168.64.100:5000/health"
    echo ""
    log_info "Una vez completado, ejecuta: bash scripts/start_training.sh"
}

# Main
main() {
    log_info "Iniciando configuración OpenClaw VM..."
    echo ""

    check_toshiba
    create_training_dir
    generate_env
    create_cloud_init
    create_api_server

    show_instructions
}

main
