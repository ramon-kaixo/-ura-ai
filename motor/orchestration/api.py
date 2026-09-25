"""API REST para la Task Queue — FastAPI server en puerto 4097.

Endpoints:
  POST   /tasks              — Crear tarea
  GET    /tasks              — Listar tareas (filtro por status)
  GET    /tasks/{id}         — Obtener tarea
  POST   /tasks/{id}/claim   — Reclamar tarea (nodo)
  POST   /tasks/{id}/start   — Marcar como en progreso
  POST   /tasks/{id}/complete — Marcar como completada
  POST   /tasks/{id}/fail    — Marcar como fallida
  POST   /tasks/{id}/review  — Marcar para revisión
  POST   /tasks/{id}/heartbeat — Actualizar heartbeat
  POST   /tasks/{id}/pause    — Pausar tarea en progreso (reservada al nodo)
  POST   /tasks/{id}/resume   — Reanudar tarea pausada
  GET    /tasks/{id}/events  — Historial de eventos
  GET    /stats              — Estadísticas de la cola
  GET    /health             — Health check
  POST   /recover-stale      — Recuperar tareas stale
  GET    /worker/status      — Estado del pool (work-stealing / rebalanceo)
  POST   /nodes/{id}/pause   — Detener un nodo (libera assigned, pausa in_progress)
  POST   /nodes/{id}/resume  — Reanudar un nodo
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from motor.core.secrets import get_secret
from motor.orchestration.task_queue import TaskQueue
from motor.orchestration.telemetry import TelemetryStore

log = logging.getLogger(__name__)

# API Key authentication
_API_KEY = get_secret("URA_API_KEY", "")
_EXEMPT_PATHS = {"/health", "/readiness", "/liveness", "/dashboard"}

app = FastAPI(title="URA Task Queue", version="1.0.0")
_queue = TaskQueue()
_telemetry = TelemetryStore()


@app.middleware("http")
async def api_key_auth(request: Request, call_next: Any) -> Any:
    """Valida X-API-Key en requests (exento: health, liveness, dashboard)."""
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)
    if not _API_KEY:
        return await call_next(request)  # No auth configured = open (dev mode)
    api_key = request.headers.get("X-API-Key", "")
    if api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return await call_next(request)
