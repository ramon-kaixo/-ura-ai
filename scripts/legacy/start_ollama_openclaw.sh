#!/bin/bash
# Script para iniciar Ollama en puerto separado para OpenClaw
# Evita conflictos con la instancia de Ollama que usa URA

OLLAMA_PORT=11435
OLLAMA_HOME="$HOME/.ollama-openclaw"
TOSHIBA_BACKUP="/Volumes/TOSHIBA_NUEVO/URA/ollama_openclaw_backup"

# Crear directorio para OpenClaw Ollama
mkdir -p "$OLLAMA_HOME"
mkdir -p "$TOSHIBA_BACKUP"

# Iniciar Ollama en puerto separado
echo "Iniciando Ollama para OpenClaw en puerto $OLLAMA_PORT..."
OLLAMA_HOST=127.0.0.1:$OLLAMA_PORT OLLAMA_MODELS="$OLLAMA_HOME" /Applications/Ollama.app/Contents/Resources/ollama serve &

# Guardar PID
echo $! > /tmp/ollama_openclaw.pid

echo "Ollama OpenClaw iniciado en puerto $OLLAMA_PORT"
echo "Backup automático configurado en: $TOSHIBA_BACKUP"
