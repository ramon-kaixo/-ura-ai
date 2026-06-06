#!/usr/bin/env python3
"""auth_layer.py — Validación de tokens API para endpoints URA.

Lee la API key desde:
  1. Variable de entorno URA_API_KEY
  2. Archivo .env en el directorio del proyecto
  3. Por defecto: deshabilitado (permitir todo) si no está configurado
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("auth")

_ENV_KEY = "URA_API_KEY"
_SECRETS_PATH = Path("/etc/ura/secrets.conf")
_ENV_PATH = Path(__file__).parent.parent / ".env"


def _load_api_key() -> str | None:
    """Carga la API key desde env o .env. Retorna None si no está configurada."""
    key = os.environ.get(_ENV_KEY)
    if key:
        return key
    if _ENV_PATH.exists():
        try:
            for line in _ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{_ENV_KEY}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return None


_API_KEY: str | None = _load_api_key()


def is_enabled() -> bool:
    """Indica si la autenticación está activa."""
    return _API_KEY is not None


def validate(token: str | None) -> bool:
    """Valida un token contra la API key configurada.

    Si la autenticación no está habilitada (sin clave configurada),
    permite el acceso por defecto.
    """
    if not is_enabled():
        return True
    if not token:
        log.warning("auth: petición sin token")
        return False
    result = token == _API_KEY
    if not result:
        log.warning("auth: token inválido")
    return result


def require_auth() -> bool:
    """Retorna True si la autenticación es obligatoria."""
    return is_enabled()
