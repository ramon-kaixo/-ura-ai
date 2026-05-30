#!/bin/bash
# Script de instalación de Ollama en ASUS GX10
echo "Instalando Ollama en ASUS GX10..."

# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Configurar Ollama para escuchar en todas las interfaces (no solo localhost)
# Crear servicio systemd con OLLAMA_HOST=0.0.0.0
sudo systemctl stop ollama 2>/dev/null || true

# Crear archivo de configuración
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_PORT=11434"
EOF

# Recargar systemd y reiniciar Ollama
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama

# Esperar a que Ollama inicie
echo "Esperando a que Ollama inicie..."
sleep 5

# Verificar que Ollama está corriendo
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama instalado y corriendo en 0.0.0.0:11434"
    
    # Abrir puerto 11434 en firewall
    sudo ufw allow 11434/tcp
    sudo ufw --force enable
    
    echo "✅ Puerto 11434 abierto en firewall"
    
    # Mostrar IP para conexión remota
    echo "----------------------------------------"
    echo "LISTO. Conéctate desde tu Mac usando:"
    echo "export OLLAMA_HOST=$(hostname -I | awk '{print $1}'):11434"
    echo "----------------------------------------"
else
    echo "❌ Error: Ollama no respondió"
    exit 1
fi
