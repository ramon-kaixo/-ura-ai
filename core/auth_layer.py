#!/usr/bin/env python3
"""Auth Layer - Validación de API keys para endpoints protegidos."""

import os
from typing import Optional

# API key por defecto (debe sobreescribirse en producción)
DEFAULT_API_KEY = os.environ.get("URA_API_KEY", "ura_1972_secure_default")
AUTH_ENABLED = os.environ.get("URA_AUTH_ENABLED", "true").lower() == "true"


def validate(api_key: Optional[str]) -> bool:
    """Valida una API key.
    
    Args:
        api_key: La API key a validar (puede ser None)
    
    Returns:
        True si la key es válida, False en caso contrario
    """
    if not AUTH_ENABLED:
        return True
    
    if not api_key:
        return False
    
    return api_key == DEFAULT_API_KEY


def require_auth() -> bool:
    """Indica si la autenticación está habilitada.
    
    Returns:
        True si se requiere autenticación, False en caso contrario
    """
    return AUTH_ENABLED
