#!/usr/bin/env python3
"""
core/model_config.py - Configuración de Ollama
Soporta host remoto para arquitectura distribuida Mac ↔ ASUS
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Configuración de Ollama - soporta variable de entorno OLLAMA_HOST
# Ejemplo: export OLLAMA_HOST=100.x.x.x:11434
OLLAMA_HOST_ENV = os.environ.get("OLLAMA_HOST", "")
if OLLAMA_HOST_ENV:
    # Si OLLAMA_HOST incluye puerto (ej: "100.x.x.x:11434")
    if ":" in OLLAMA_HOST_ENV:
        OLLAMA_HOST, OLLAMA_PORT = OLLAMA_HOST_ENV.rsplit(":", 1)
        OLLAMA_PORT = int(OLLAMA_PORT)
    else:
        OLLAMA_HOST = OLLAMA_HOST_ENV
        OLLAMA_PORT = 11434
else:
    # Fallback a localhost
    OLLAMA_HOST = "localhost"
    OLLAMA_PORT = 11434

OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

# Modelos disponibles
AVAILABLE_MODELS = [
    "llama3:latest",
    "llama3.2:3b",
    "qwen2.5:3b-instruct",
    "mxbai-embed-large:latest",
    "llava:latest",
]

# Modelo por defecto
DEFAULT_MODEL = "llama3.2:3b"

# Modelo para embeddings
EMBEDDING_MODEL = "mxbai-embed-large:latest"

# Modelo para visión
VISION_MODEL = "llava:latest"


def get_active_model() -> str:
    """Devuelve el modelo activo para uso general"""
    return DEFAULT_MODEL
