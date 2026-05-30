#!/bin/bash
# Script de arranque de OpenClaw vía Ollama

# Actualizar Ollama por si acaso
brew upgrade ollama

# Lanzar OpenClaw usando la integración oficial
ollama launch openclaw -- --gateway --port 18789
