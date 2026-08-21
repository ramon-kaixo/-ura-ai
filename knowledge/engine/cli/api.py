"""CLI: api — inicia el servidor API REST.

Seguridad:
  - Por defecto solo escucha en 127.0.0.1 (localhost).
  - Para acceso externo: --host 0.0.0.0 --auth <clave>
  - Si no se pasa --auth, usa URA_API_KEY del entorno.
  - Sin autenticación configurada: solo localhost.
"""

import os
import sys

from motor.core.secrets import get_secret


def cmd_api(args) -> int:
    """Inicia el servidor API REST FastAPI (puerto 4097)."""
    import uvicorn

    port = getattr(args, "port", 4097)
    host = getattr(args, "host", "127.0.0.1")
    auth = getattr(args, "auth", None) or get_secret("URA_API_KEY")

    if auth:
        os.environ["URA_API_KEY"] = auth
    elif host == "0.0.0.0":  # noqa: S104
        pass

    sys.stdout.flush()
    uvicorn.run(
        "knowledge.engine.api:app",
        host=host,
        port=port,
        log_level="info",
    )
    return 0
