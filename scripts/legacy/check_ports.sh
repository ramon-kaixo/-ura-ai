#!/bin/bash

# URA - Script de Verificación de Puertos
# Verifica puertos críticos y reporta estado

URA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_CMD="${URA_DIR}/.venv/bin/python3"

echo "=== URA - Verificación de Puertos ==="
echo ""

# Verificar puertos críticos
echo "Verificando puertos críticos..."
echo ""

# Ollama
echo "Ollama (11434):"
lsof -i :11434 2>/dev/null || echo "  Puerto libre"
echo ""

# Redis
echo "Redis (6379):"
lsof -i :6379 2>/dev/null || echo "  Puerto libre"
echo ""

# WebSocket
echo "WebSocket (8765):"
lsof -i :8765 2>/dev/null || echo "  Puerto libre"
echo ""

# Usar port_registry para verificación detallada
echo "=== Verificación detallada con port_registry ==="
echo ""
${PYTHON_CMD} ${URA_DIR}/core/port_registry.py --list
echo ""

# Mostrar puertos libres
echo "=== Puertos libres disponibles ==="
echo ""
${PYTHON_CMD} ${URA_DIR}/core/port_registry.py --free
echo ""
