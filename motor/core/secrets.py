"""motor/core/secrets.py — Gestión unificada de secretos.

API pública:
    get_secret(name, default=None) -> str | None
    require_secret(name) -> str
    has_secret(name) -> bool
    list_available() -> list[str]

Backends (orden de precedencia):
    1. Variables de entorno (os.environ)
    2. Archivo local no versionado (/etc/ura/secrets.env)
    3. Default proporcionado por el consumidor

Uso:
    from motor.core.secrets import get_secret, require_secret

    api_key = require_secret("GROQ_API_KEY")
    token = get_secret("PUSHOVER_APP_TOKEN", default="")
"""

import os
import threading
from pathlib import Path

RUTA_SECRETOS = "/etc/ura/secrets.env"

_lock = threading.Lock()
_cached_file_secrets: dict[str, str] | None = None

KNOWN_SECRETS = frozenset(
    {
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "URA_API_KEY",
        "PUSHOVER_USER_KEY",
        "PUSHOVER_APP_TOKEN",
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "OPENCLAW_GATEWAY_TOKEN",
        "URA_SMTP_PASS",
        "URA_SMTP_HOST",
        "URA_SMTP_PORT",
        "URA_SMTP_USER",
        "URA_EMAIL_FROM",
        "URA_EMAIL_TO",
        "ROUTER_PASSWORD",
        "VNC_PWD",
        "URA_SSH_USER",
        "LILDAX_PASSWORD",
        "GRAFANA_PASSWORD",
        "WEBUI_SECRET_KEY",
        "N8N_KEY",
        "FRIGATE_RTSP_PASSWORD",
        "PYPI_TOKEN",
        "LANGFUSE_SECRET_KEY",
    },
)


def _load_file_secrets() -> dict[str, str]:
    """Carga secretos desde archivo KEY=VALUE.

    Formato: una variable por línea, # para comentarios,
    líneas en blanco ignoradas. Las comillas simples/dobles
    alrededor del valor se eliminan.
    """
    global _cached_file_secrets  # noqa: PLW0603
    if _cached_file_secrets is not None:
        return _cached_file_secrets
    result: dict[str, str] = {}
    path = Path(RUTA_SECRETOS)
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, _, val = stripped.partition("=")
                result[key.strip()] = val.strip().strip("'\"")
        except OSError:
            pass
    with _lock:
        _cached_file_secrets = result
    return result


def _clear_cache() -> None:
    """Limpia la caché del backend de archivo (útil en tests)."""
    global _cached_file_secrets  # noqa: PLW0603
    with _lock:
        _cached_file_secrets = None


def get_secret(name: str, default: str | None = None) -> str | None:
    """Obtiene un secreto por nombre.

    Orden de precedencia:
    1. Variable de entorno
    2. Archivo /etc/ura/secrets.env
    3. default proporcionado
    """
    value = os.environ.get(name)
    if value:
        return value
    file_secrets = _load_file_secrets()
    value = file_secrets.get(name)
    if value:
        return value
    return default


def require_secret(name: str) -> str:
    """Obtiene un secreto o lanza KeyError si no está disponible."""
    value = get_secret(name)
    if not value:
        msg = f"Secreto requerido no encontrado: {name}. "
        msg += f"Defínelo como variable de entorno o en {RUTA_SECRETOS}."
        raise KeyError(msg)
    return value


def has_secret(name: str) -> bool:
    """Verifica si un secreto está disponible (no vacío)."""
    return bool(get_secret(name))


def list_available() -> list[str]:
    """Lista los nombres de secretos disponibles actualmente."""
    return sorted(name for name in KNOWN_SECRETS if has_secret(name))
