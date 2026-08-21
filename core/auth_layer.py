#!/usr/bin/env python3
"""Auth Layer - Validación de API keys para endpoints protegidos."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import ISecretStore

DEFAULT_API_KEY: str | None = None
AUTH_ENABLED = os.environ.get("URA_AUTH_ENABLED", "true").lower() == "true"


def _get_api_key(store: ISecretStore | None = None) -> str:
    if store is not None:
        key = store.get_secret("URA_API_KEY")
        if key is not None:
            return key
    from motor.core.secrets import get_secret as _get_secret

    key = _get_secret("URA_API_KEY")
    if key is not None:
        return key
    raise RuntimeError("URA_API_KEY not configured. Set URA_API_KEY env var or configure in /etc/ura/secrets.env")


def validate(api_key: str | None, store: ISecretStore | None = None) -> bool:
    if not AUTH_ENABLED:
        return True
    if not api_key:
        return False
    return api_key == _get_api_key(store)


def require_auth() -> bool:
    return AUTH_ENABLED
