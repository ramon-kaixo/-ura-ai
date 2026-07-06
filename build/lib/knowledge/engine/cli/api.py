"""CLI: api — inicia el servidor API REST.

Seguridad:
  - Por defecto solo escucha en 127.0.0.1 (localhost).
  - Para acceso externo: --host 0.0.0.0 --auth <clave>
  - Si no se pasa --auth, usa URA_API_KEY del entorno.
  - Sin autenticación configurada: solo localhost.
"""

import os
import sys


def cmd_api(args) -> int:
    """Inicia el servidor API REST FastAPI (puerto 4097)."""
    import uvicorn

    port = getattr(args, "port", 4097)
    host = getattr(args, "host", "127.0.0.1")
    auth = getattr(args, "auth", None) or os.environ.get("URA_API_KEY")

    if auth:
        os.environ["URA_API_KEY"] = auth
    elif host == "0.0.0.0":
        print("WARNING: Listening on 0.0.0.0 without authentication. Set --auth or URA_API_KEY.", file=sys.stderr)
        print("WARNING: This is INSECURE. Only use in trusted networks.", file=sys.stderr)

    print(f"Starting Knowledge Engine API on {host}:{port}" + (" (authenticated)" if auth else " (no auth, localhost only)"))
    sys.stdout.flush()
    uvicorn.run(
        "knowledge.engine.api:app",
        host=host,
        port=port,
        log_level="info",
    )
    return 0
