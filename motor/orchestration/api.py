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
  GET    /tasks/{id}/events  — Historial de eventos
  GET    /stats              — Estadísticas de la cola
  GET    /health             — Health check
  POST   /recover-stale      — Recuperar tareas stale
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from motor.orchestration.task_queue import TaskQueue

log = logging.getLogger(__name__)

app = FastAPI(title="URA Task Queue", version="1.0.0")
_queue = TaskQueue()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTask(BaseModel):
    description: str
    plan_phase: str = ""
    priority: int = 0
    max_retries: int = 3
    context_json: str = "{}"


class ClaimTask(BaseModel):
    agent: str


class FailTask(BaseModel):
    error: str
    require_human: bool = False


class CompleteTask(BaseModel):
    commit_sha: str = ""


class ReviewTask(BaseModel):
    reviewer: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/tasks")
def create_task(req: CreateTask):
    task = _queue.create(
        description=req.description,
        plan_phase=req.plan_phase,
        priority=req.priority,
        max_retries=req.max_retries,
        context_json=req.context_json,
    )
    return task.to_dict()


@app.get("/tasks")
def list_tasks(status: str | None = None, limit: int = 50):
    tasks = _queue.list_by_status(status, limit)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = _queue.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@app.post("/tasks/{task_id}/claim")
def claim_task(task_id: str, req: ClaimTask):
    task = _queue.claim(task_id, req.agent)
    if not task:
        raise HTTPException(409, "Task not available for claiming")
    return task.to_dict()


@app.post("/tasks/{task_id}/start")
def start_task(task_id: str):
    task = _queue.start(task_id)
    if not task:
        raise HTTPException(409, "Task not in 'assigned' state")
    return task.to_dict()


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, req: CompleteTask):
    task = _queue.complete(task_id, req.commit_sha)
    if not task:
        raise HTTPException(409, "Task not in reviewable state")
    return task.to_dict()


@app.post("/tasks/{task_id}/fail")
def fail_task(task_id: str, req: FailTask):
    task = _queue.fail(task_id, req.error, req.require_human)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@app.post("/tasks/{task_id}/review")
def review_task(task_id: str, req: ReviewTask):
    task = _queue.review(task_id, req.reviewer)
    if not task:
        raise HTTPException(409, "Task not in 'in_progress' state")
    return task.to_dict()


@app.post("/tasks/{task_id}/heartbeat")
def heartbeat_task(task_id: str):
    ok = _queue.heartbeat(task_id)
    if not ok:
        raise HTTPException(404, "Task not found or not active")
    return {"status": "ok"}


@app.get("/tasks/{task_id}/events")
def get_events(task_id: str):
    events = _queue.get_events(task_id)
    return {"events": events, "count": len(events)}


@app.get("/stats")
def get_stats():
    return _queue.stats()


@app.post("/recover-stale")
def recover_stale():
    stale = _queue.recover_stale()
    return {"recovered": len(stale), "tasks": [t.to_dict() for t in stale]}


@app.get("/health")
def health():
    stats = _queue.stats()
    return {
        "status": "ok",
        "queue": stats,
    }


def main():
    import uvicorn

    port = int(os.environ.get("TASK_QUEUE_PORT", "4097"))
    host = os.environ.get("TASK_QUEUE_HOST", "0.0.0.0")  # noqa: S104  # nosec B104
    log.info("[TASK_QUEUE_API] Starting on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
