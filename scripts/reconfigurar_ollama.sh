#!/bin/bash
echo "=== Creando copia de seguridad del servicio Ollama ==="
sudo cp /etc/systemd/system/ollama.service /etc/systemd/system/ollama.service.bak

echo "=== Modificando el servicio Ollama para establecer variables globales de persistencia ==="
sudo sed -i "/\[Service\]/a Environment=OLLAMA_KEEP_ALIVE=0\nEnvironment=OLLAMA_NUM_PARALLEL=1" /etc/systemd/system/ollama.service

echo "=== Recargando el daemon de systemd para aplicar cambios ==="
sudo sudo systemctl daemon-reload

echo "=== Reiniciando servicio Ollama con nuevas configuraciones ==="
sudo sudo systemctl restart ollama.service

echo "=== Verificando estado del servicio después de reinicio ==="
sudo systemctl status ollama.service --no-pager
