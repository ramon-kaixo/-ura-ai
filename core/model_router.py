#!/usr/bin/env python3
"""
core/model_router.py - Router de inferencia híbrido Mac ↔ GX10.

Decide qué backend usar según la tarea:
- Local Mac: tareas rápidas, baja latencia (< 500ms), modelos pequeños
- Remoto GX10: contexto largo, razonamiento, modelos grandes
"""

import os
import requests
from typing import Literal

LOCAL_BASE = "http://localhost:11434"
REMOTE_BASE = os.environ.get("OLLAMA_HOST", "http://10.164.1.99:11434")
if not REMOTE_BASE.startswith("http"):
    REMOTE_BASE = f"http://{REMOTE_BASE}"

# Mapa de modelos por backend
LOCAL_MODELS = {
    "fast": "qwen2.5:3b-instruct",  # tareas rápidas
    "vision": "llava:latest",  # visión local (si existe)
    "embed": "mxbai-embed-large:latest",
}
REMOTE_MODELS = {
    "default": "qwen3:32b-q8_0",  # razonamiento general (rápido, ~6s)
    "large": "qwen3:32b-q8_0",  # fallback: mistral-large incompatible (161GB req)
    "long_context": "qwen3:32b-q8_0",  # contexto largo (32k tokens probados)
    "deep": "qwen3:32b-q8_0",  # fallback: mistral-large incompatible
}

# GX10: 121 GB RAM. Solo qwen3:32b-q8_0 (34 GB) funciona.
# mistral-large requiere 161 GiB → físicamente imposible.

ModelKind = Literal["fast", "default", "large", "long_context", "vision", "embed", "deep"]


def _is_alive(base: str, timeout: int = 2) -> bool:
    try:
        r = requests.get(f"{base}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def select_backend(kind: ModelKind = "default") -> tuple[str, str]:
    """Devuelve (base_url, modelo) según tipo de tarea y disponibilidad."""
    # Tareas locales preferidas
    if kind in ("fast", "vision", "embed"):
        if _is_alive(LOCAL_BASE):
            return LOCAL_BASE, LOCAL_MODELS[kind]
        # Fallback a remoto
        return REMOTE_BASE, REMOTE_MODELS.get("default", "qwen3:32b-q8_0")

    # Tareas remotas (GX10)
    if _is_alive(REMOTE_BASE):
        return REMOTE_BASE, REMOTE_MODELS.get(kind, REMOTE_MODELS["default"])
    # Fallback degradado a local
    return LOCAL_BASE, LOCAL_MODELS.get("fast", "qwen2.5:3b-instruct")


def generate(prompt: str, kind: ModelKind = "default", **opts) -> str:
    """Genera texto seleccionando backend automáticamente."""
    base, model = select_backend(kind)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": opts,
    }
    r = requests.post(f"{base}/api/generate", json=payload, timeout=600)
    r.raise_for_status()
    return r.json().get("response", "")


if __name__ == "__main__":
    import sys

    kind = sys.argv[1] if len(sys.argv) > 1 else "fast"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Di Hola"
    base, model = select_backend(kind)
    print(f"Backend: {base} | Modelo: {model}")
    print(generate(prompt, kind=kind, num_predict=20))
