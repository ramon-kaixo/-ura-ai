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
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from motor.orchestration.task_queue import TaskQueue
from motor.orchestration.telemetry import TelemetryStore, dashboard_html

log = logging.getLogger(__name__)

# API Key authentication
_API_KEY = os.environ.get("URA_API_KEY", "")
_EXEMPT_PATHS = {"/health", "/readiness", "/liveness", "/dashboard"}

app = FastAPI(title="URA Task Queue", version="1.0.0")
_queue = TaskQueue()
_telemetry = TelemetryStore()


@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    """Valida X-API-Key en requests (exento: health, liveness, dashboard)."""
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)
    if not _API_KEY:
        return await call_next(request)  # No auth configured = open (dev mode)
    api_key = request.headers.get("X-API-Key", "")
    if api_key != _API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing X-API-Key"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTask(BaseModel):
    description: str
    plan_phase: str = ""
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 1800
    context_json: str = "{}"
    node_id: str = ""


class ClaimTask(BaseModel):
    agent: str


class FailTask(BaseModel):
    error: str
    require_human: bool = False


class CompleteTask(BaseModel):
    commit_sha: str = ""


class ReviewTask(BaseModel):
    reviewer: str


class SyncTask(BaseModel):
    """Task received from a remote node for sync."""
    description: str
    plan_phase: str = ""
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 1800
    context_json: str = "{}"
    node_id: str = ""
    source_node: str = ""
    source_task_id: str = ""


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
        timeout_seconds=req.timeout_seconds,
        context_json=req.context_json,
        node_id=req.node_id,
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


@app.get("/tasks/node/{node_id}")
def list_tasks_by_node(node_id: str, status: str | None = None, limit: int = 50):
    tasks = _queue.list_by_node(node_id, status, limit)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks), "node_id": node_id}


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


# ---------------------------------------------------------------------------
# Telemetry endpoints
# ---------------------------------------------------------------------------


@app.get("/telemetry/stats")
def telemetry_stats(minutes: int = 60):
    return _telemetry.stats(since_minutes=minutes)


@app.get("/telemetry/recent")
def telemetry_recent(limit: int = 20):
    return {"tasks": _telemetry.recent_tasks(limit)}


@app.get("/telemetry/query")
def telemetry_query(event: str | None = None, task_id: str | None = None, limit: int = 50):
    metrics = _telemetry.query(event=event, task_id=task_id, limit=limit)
    return {
        "metrics": [{"id": m.id, "ts": m.ts, "event": m.event, "task_id": m.task_id, "node": m.node} for m in metrics]
    }


@app.get("/dashboard", response_class=None)
def dashboard():
    from fastapi.responses import HTMLResponse

    stats = _telemetry.stats(since_minutes=60)
    tasks = _telemetry.recent_tasks()
    return HTMLResponse(dashboard_html(stats, tasks))


# ---------------------------------------------------------------------------
# Failover + Readiness/Liveness
# ---------------------------------------------------------------------------

_failover: Any = None


def _get_failover() -> Any:
    global _failover  # noqa: PLW0603
    if _failover is None:
        from motor.orchestration.failover import AutonomousFailover

        _failover = AutonomousFailover()
    return _failover


@app.get("/readiness")
def readiness():
    """Kubernetes-style readiness probe."""
    stats = _queue.stats()
    pending = stats.get("by_status", {}).get("pending", 0)
    in_progress = stats.get("by_status", {}).get("in_progress", 0)
    queue_depth = pending + in_progress

    ready = queue_depth < 100  # Backpressure threshold
    return {
        "ready": ready,
        "queue_depth": queue_depth,
        "pending": pending,
        "in_progress": in_progress,
    }


@app.get("/liveness")
def liveness():
    """Kubernetes-style liveness probe."""
    return {"alive": True, "pid": os.getpid()}


@app.get("/failover/status")
def failover_status():
    """Estado del sistema de failover."""
    fo = _get_failover()
    return fo.get_status()


@app.post("/failover/start")
def failover_start():
    """Inicia el health checker del failover."""
    fo = _get_failover()
    fo.start()
    return {"status": "started", "mode": fo.mode.value}


@app.post("/failover/stop")
def failover_stop():
    """Detiene el health checker del failover."""
    fo = _get_failover()
    fo.stop()
    return {"status": "stopped"}


@app.post("/recover-stale-auto")
def recover_stale_auto():
    """Stale recovery automatico (sin intervencion manual)."""
    stale = _queue.recover_stale()
    if stale:
        _telemetry.record("auto_stale_recovery", details={"count": len(stale)})
    return {"recovered": len(stale), "tasks": [t.to_dict() for t in stale]}


@app.get("/parallel/status")
def parallel_status():
    """Estado del trabajo paralelo: nodo, branch, behind, conflictos."""
    import subprocess

    node_id = os.environ.get("URA_NODE_ID", "unknown")
    branch = "unknown"
    behind_main = 0
    has_conflicts = False
    other_branches: dict[str, dict] = {}

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        branch = result.stdout.strip() or "unknown"
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            capture_output=True, text=True, timeout=5,
        )
        behind_main = int(result.stdout.strip() or "0")
    except Exception:
        pass

    # Verificar conflictos
    conflict_log = Path("CONFLICT.log")
    has_conflicts = conflict_log.exists()

    # Últimos commits de otras ramas
    for other in ("feature/opencode-gx10", "feature/opencode-web", "feature/opencode-mac"):
        if other == branch:
            continue
        try:
            result = subprocess.run(
                ["git", "log", f"origin/{other}", "--oneline", "-3"],
                capture_output=True, text=True, timeout=5,
            )
            commits = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            other_branches[other] = {"commits": commits}
        except Exception:
            other_branches[other] = {"commits": []}

    return {
        "node_id": node_id,
        "branch": branch,
        "behind_main": behind_main,
        "has_conflicts": has_conflicts,
        "other_branches": other_branches,
    }


# ---------------------------------------------------------------------------
# Node Registry — multi-node discovery
# ---------------------------------------------------------------------------

_registry: Any = None



@app.post("/tasks/sync")
def sync_task(req: SyncTask):
    """Receive a task from a remote node and add to local queue."""
    import json as _json

    # Build context with source info for dedup
    ctx = _json.loads(req.context_json) if req.context_json else {}
    if req.source_task_id or req.source_node:
        ctx["source_node"] = req.source_node
        ctx["source_task_id"] = req.source_task_id

    # Check for duplicate
    if req.source_task_id and req.source_node:
        for t in _queue.list_by_status(None, 1000):
            t_ctx = _json.loads(t.context_json) if t.context_json else {}
            if t_ctx.get("source_node") == req.source_node and t_ctx.get("source_task_id") == req.source_task_id:
                return {"status": "already_synced", "task_id": t.id}

    task = _queue.create(
        description=req.description,
        plan_phase=req.plan_phase,
        priority=req.priority,
        max_retries=req.max_retries,
        timeout_seconds=req.timeout_seconds,
        node_id=req.node_id,
        context_json=_json.dumps(ctx),
    )
    return {"status": "synced", "task_id": task.id}

def _get_registry() -> Any:
    global _registry  # noqa: PLW0603
    if _registry is None:
        from motor.orchestration.node_registry import NodeRegistry

        _registry = NodeRegistry()
    return _registry


class RegisterNode(BaseModel):
    node_id: str
    hostname: str
    tailscale_ip: str
    api_port: int = 4097
    tags: list[str] = []


@app.get("/nodes")
def list_nodes():
    """List all known peer nodes and their health status."""
    reg = _get_registry()
    nodes = reg.list_all()
    return {
        "nodes": [n.to_dict() for n in nodes],
        "count": len(nodes),
        "self": os.environ.get("URA_NODE_ID", "unknown"),
    }


@app.post("/nodes/register")
def register_node(req: RegisterNode):
    """Register or update a peer node."""
    reg = _get_registry()
    node = reg.register(
        node_id=req.node_id,
        hostname=req.hostname,
        tailscale_ip=req.tailscale_ip,
        api_port=req.api_port,
        tags=req.tags,
    )
    return node.to_dict()


@app.delete("/nodes/{node_id}")
def unregister_node(node_id: str):
    """Remove a node from the registry."""
    reg = _get_registry()
    removed = reg.unregister(node_id)
    if not removed:
        raise HTTPException(404, "Node not found")
    return {"removed": node_id}


@app.get("/nodes/{node_id}")
def get_node(node_id: str):
    """Get info about a specific peer node."""
    reg = _get_registry()
    node = reg.get(node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    return node.to_dict()


@app.post("/nodes/check")
def check_nodes(node_id: str | None = None):
    """Trigger health check for one or all nodes."""
    reg = _get_registry()
    results = reg.check_health(node_id)
    return {"results": results}


@app.post("/nodes/start-checker")
def start_node_checker():
    """Start background health checker for all nodes."""
    reg = _get_registry()
    reg.start_checker()
    return {"status": "started"}


@app.post("/nodes/stop-checker")
def stop_node_checker():
    """Stop background health checker."""
    reg = _get_registry()
    reg.stop_checker()
    return {"status": "stopped"}


def main():
    import uvicorn

    port = int(os.environ.get("TASK_QUEUE_PORT", "4097"))
    host = os.environ.get("TASK_QUEUE_HOST", "0.0.0.0")  # noqa: S104  # nosec B104
    log.info("[TASK_QUEUE_API] Starting on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
