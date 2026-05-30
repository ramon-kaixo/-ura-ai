#!/bin/bash
# Script de instalación de dependencias del sistema URA

echo "Instalando dependencias del sistema..."

# Redis
if ! command -v redis-server &> /dev/null; then
    echo "Instalando Redis..."
    brew install redis
fi

# Docker
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker..."
    brew install docker
fi

echo "✅ Dependencias del sistema instaladas"
