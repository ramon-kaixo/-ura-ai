"""URA Assistant — servidor conversacional FastAPI.

Uso:
  URA_API_KEY=mi-clave-secreta uvicorn motor.assistant.main:app --host 127.0.0.1 --port 8000

Variables de entorno:
  URA_API_KEY       - API Key para autenticación (opcional, si no se pone no hay auth)
  URA_DATA_DIR      - Directorio para datos persistentes (defecto: ~/.ura)
  URA_DB_PATH       - Ruta a la base de datos SQLite
  URA_LLM_TIMEOUT   - Timeout en segundos para llamadas LLM (defecto: 30)
  URA_LLM_MODEL_FAST- Modelo rápido (defecto: qwen2.5:7b)
  URA_LLM_MODEL_DEEP- Modelo profundo (defecto: qwen3:32b-q8_0)
  URA_HOST          - Host de escucha (defecto: 127.0.0.1)
  URA_PORT          - Puerto de escucha (defecto: 8000)
  URA_MAX_MESSAGE_LENGTH - Longitud máxima del mensaje (defecto: 100000)
  URA_RATE_LIMIT    - Máximo de requests por minuto (defecto: 60)
"""

from __future__ import annotations

import logging
import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from motor.assistant.api import router as chat_router
from motor.assistant.auth import AuthMiddleware
from motor.assistant.config import config
from motor.assistant.health import get_assistant_health
from motor.observability.logging import JSONFormatter, setup_logging

_VERSION = "1.0.0"

# ── Observability: logging estructurado ─────────────────────
setup_logging(level="INFO")
_log = logging.getLogger("ura.assistant")
for handler in _log.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setFormatter(JSONFormatter(prefix="assistant"))
        break

# ── Observability: health registry (inicializado via api.py lazy init) ──


app = FastAPI(
    title="URA Assistant",
    description="Asistente conversacional inteligente multi-modelo",
    version=_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)

app.include_router(chat_router)


@app.get("/health")
async def health():
    snapshot = get_assistant_health().snapshot()
    return {
        "status": "ok",
        "version": _VERSION,
        "auth": config.auth_enabled,
        "components": snapshot,
    }


@app.get("/")
async def root():
    return {"name": "URA Assistant", "docs": "/docs", "health": "/health"}


def main() -> None:
    config.ensure_data_dir()
    _log.info("URA Assistant starting", extra={"host": config.host, "port": config.port})
    uvicorn.run(
        "motor.assistant.main:app",
        host=config.host,
        port=config.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
