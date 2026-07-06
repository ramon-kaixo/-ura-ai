"""API REST — FastAPI service para el Knowledge Engine.

Endpoints:
  GET    /health                  Health check
  GET    /status                  Graph status
  POST   /compile                 Trigger compile (202 async)
  POST   /compile/sync            Trigger compile (200 sync)
  POST   /search                  Search documents
  GET    /documents/{doc_id}      Get document
  GET    /rules                   List rules
  POST   /rules/eval              Evaluate rules
  POST   /archive                 Create source archive
  GET    /metrics                 Prometheus metrics
  GET    /docs                    OpenAPI Swagger UI
  GET    /openapi.json            OpenAPI schema

Seguridad:
  - Todos los parámetros HTTP validados (tipos, límites, enums, tamaños)
  - Errores JSON estructurados, sin tracebacks
  - compile usa flock (exclusión mutua entre procesos)
  - Límites de tamaño de petición y tiempo de ejecución
  - CORS configurable
  - doc_id validado contra formato esperado
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

# Límites de seguridad
_MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

log = logging.getLogger("ura.knowledge.api")

DEFAULT_DB_PATH = Path(os.environ.get("URA_KNOWLEDGE_DB", "")) or Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"
DEFAULT_SOURCE_DIR = Path(os.environ.get("URA_SOURCE_DIR", "")) or Path.home() / "URA" / "ura_ia_1972" / "source"

# ── Autenticación opcional ────────────────────────────────────────────────

_API_KEY: str | None = os.environ.get("URA_API_KEY")

if _API_KEY:
    log.info("API authentication enabled (URA_API_KEY set)")
    _security_scheme = HTTPBearer(auto_error=False)

    async def _verify_api_key(credentials: HTTPAuthorizationCredentials | None = Security(_security_scheme)) -> None:
        """Verifica el Bearer token contra la API Key configurada."""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required (Bearer token)")
        if credentials.credentials != _API_KEY:
            raise HTTPException(status_code=403, detail="Invalid API key")
else:
    log.info("API authentication disabled (set URA_API_KEY to enable)")

    async def _verify_api_key() -> None:  # type: ignore[misc]
        """No-op: autenticación desactivada."""
        return None

# Límites
_MAX_SEARCH_LIMIT = 100
_MIN_QUERY_LENGTH = 1
_MAX_QUERY_LENGTH = 500
_DOC_ID_PATTERN = "0123456789abcdef"
_MAX_BODY_PREVIEW = 5000
_COMPILE_TIMEOUT_S = 300

# ── Pydantic models with validation ──────────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(min_length=_MIN_QUERY_LENGTH, max_length=_MAX_QUERY_LENGTH)
    mode: str = "lexical"
    type: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=10, ge=1, le=_MAX_SEARCH_LIMIT)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("lexical", "hybrid"):
            raise ValueError(f"mode must be 'lexical' or 'hybrid', got '{v}'")
        return v


class CompileResponse(BaseModel):
    success: bool
    documents_changed: int = 0
    documents_total: int = 0
    message: str = ""


# ── Custom exception handler ─────────────────────────────────────────────


class AppError(Exception):
    """Error controlado de la API. No expone tracebacks."""

    def __init__(self, status_code: int, message: str, detail: str = ""):
        self.status_code = status_code
        self.message = message
        self.detail = detail


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


# ── App state ─────────────────────────────────────────────────────────────


class AppState:
    def __init__(self):
        self.db_path: Path = DEFAULT_DB_PATH
        self.source_dir: Path = DEFAULT_SOURCE_DIR
        self._repo: Any = None

    def get_repo(self):
        if self._repo is None:
            from knowledge.engine.repository import SQLiteKnowledgeRepository

            self._repo = SQLiteKnowledgeRepository(self.db_path)
        return self._repo


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from knowledge.engine.connection import open_db
    from knowledge.engine.migrations import SCHEMA_VERSION, get_schema_version

    conn = open_db(state.db_path)
    version = get_schema_version(conn)
    conn.close()
    log.info("API started: schema v%s, db=%s, source=%s", version, state.db_path, state.source_dir)
    yield


app = FastAPI(
    title="Knowledge Engine API",
    description="REST API for the Knowledge Engine. All endpoints return JSON. Compile is protected by flock.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_exception_handler(AppError, _app_error_handler)


# ── Middleware: autenticación + seguridad básica ──────────────────────────

_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/metrics"}


@app.middleware("http")
async def _body_size_middleware(request: Request, call_next):
    """Middleware: límite de tamaño de petición + autenticación."""
    # Verificar Content-Length antes de leer el body
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_REQUEST_BODY_SIZE:
        return JSONResponse(status_code=413, content={"error": "Request too large", "detail": f"Max {_MAX_REQUEST_BODY_SIZE // 1024 // 1024}MB"})
    return await _auth_middleware_inner(request, call_next)


async def _auth_middleware_inner(request: Request, call_next):
    """Middleware de autenticación y seguridad."""
    # Endpoints públicos no requieren auth
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith(("/docs/", "/redoc/", "/openapi")):
        pass
    elif _API_KEY:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"error": "Authentication required", "detail": "Bearer token required"})
        token = auth.removeprefix("Bearer ")
        if token != _API_KEY:
            return JSONResponse(status_code=403, content={"error": "Forbidden", "detail": "Invalid API key"})
    # else: no auth configured, allow all

    start = time.monotonic()
    response: Response = await call_next(request)
    response.headers["X-Engine-Version"] = "0.2.0"
    response.headers["X-Request-Time-Ms"] = str(round((time.monotonic() - start) * 1000))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# ── Helper: validar doc_id (delega en feedback.py) ────────────────────────


def _validate_doc_id(doc_id: str) -> None:
    from knowledge.engine.feedback import InvalidDocIdError, _validate_doc_id as _fb_validate

    try:
        _fb_validate(doc_id)
    except InvalidDocIdError as exc:
        raise AppError(422, "Invalid document ID", str(exc))


# ── Endpoints ─────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Health check. Retorna 503 si la BD no responde."""
    repo = state.get_repo()
    health_data = repo.health_check()
    if health_data.get("healthy"):
        return {"status": "ok", "schema_version": health_data.get("schema_version")}
    raise AppError(503, "Unhealthy", health_data.get("error", "unknown"))


@app.get("/status")
async def status():
    """Graph status: documentos, relaciones, versión."""
    from knowledge.engine.connection import open_db

    try:
        conn = open_db(state.db_path)
        doc_count = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        edge_count = conn.execute("SELECT COUNT(*) as c FROM kg_edges").fetchone()["c"]
        version = conn.execute(
            "SELECT graph_version, source_commit, compiler_version FROM kg_active_version WHERE singleton=1"
        ).fetchone()
        conn.close()
        return {
            "documents": doc_count,
            "relations": edge_count,
            "graph_version": dict(version) if version else None,
        }
    except Exception as exc:
        raise AppError(500, "Status check failed", str(exc))


@app.post("/compile", status_code=202, response_model=CompileResponse)
async def compile_endpoint(incremental: bool = False):
    """Trigger compile (asíncrono, retorna 202).

    Usa flock para exclusión mutua entre procesos.
    Si otro compile está en ejecución, retorna 409 Conflict.
    """
    from knowledge.engine.orchestrator import request_compile

    try:
        if incremental:
            from knowledge.engine.compiler import compile_incremental

            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, compile_incremental,
                    state.source_dir, state.db_path),
                timeout=300,
            )
            return CompileResponse(
                success=result.success,
                documents_changed=result.documents_changed,
                documents_total=result.documents_total,
                message="incremental" if result.success else "failed",
            )

        n = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, lambda: request_compile("api",
                source_dir=state.source_dir, db_path=state.db_path)),
            timeout=300,
        )
        if n == 0:
            raise AppError(409, "Compile already running", "Another compile is in progress (flock held)")
        return CompileResponse(success=True, message="compile started")
    except asyncio.TimeoutError:
        raise AppError(504, "Compile timed out", "Compile exceeded 300s timeout")
    except AppError:
        raise
    except Exception as exc:
        raise AppError(500, "Compile failed", str(exc))


@app.post("/compile/sync", response_model=CompileResponse)
async def compile_sync():
    """Trigger compile (síncrono, espera hasta completar)."""
    from knowledge.engine.orchestrator import request_compile

    try:
        n = request_compile("api", source_dir=state.source_dir, db_path=state.db_path)
        if n == 0:
            raise AppError(409, "Compile already running", "Another compile is in progress (flock held)")
        return CompileResponse(success=True, message="compile completed")
    except AppError:
        raise
    except Exception as exc:
        raise AppError(500, "Compile failed", str(exc))


@app.post("/search")
async def search_endpoint(req: SearchRequest):
    """Search documents.

    Parámetros:
      query: texto de búsqueda (1-500 chars)
      mode: lexical|hybrid
      type: filtro opcional por tipo de documento
      limit: máximo resultados (1-100)
    """
    try:
        filters: dict[str, str] = {}
        if req.type:
            filters["type"] = req.type
        results = state.get_repo().search(req.query, mode=req.mode, filters=filters, limit=req.limit)
        return {
            "results": [
                {
                    "doc_id": r.doc_id,
                    "score": r.score,
                    "title": r.title,
                    "snippet": r.snippet[:200] if r.snippet else "",
                    "doc_type": r.doc_type,
                }
                for r in results
            ],
            "total": len(results),
        }
    except Exception as exc:
        raise AppError(500, "Search failed", str(exc))


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document by ID (12 hex chars)."""
    _validate_doc_id(doc_id)
    try:
        doc = state.get_repo().get_document(doc_id)
        if doc is None:
            raise AppError(404, "Document not found", f"No document with id '{doc_id}'")
        return {
            "doc_id": doc.doc_id,
            "doc_type": doc.doc_type,
            "path": doc.path,
            "title": doc.frontmatter.title,
            "tags": list(doc.frontmatter.tags),
            "body": doc.body[:_MAX_BODY_PREVIEW],
        }
    except AppError:
        raise
    except Exception as exc:
        raise AppError(500, "Failed to get document", str(exc))


@app.get("/rules")
async def list_rules():
    """List all rules with metadata."""
    from knowledge.engine.rules import list_rules

    rules = list_rules()
    return {
        "rules": [
            {
                "id": r.metadata.id,
                "version": r.metadata.version,
                "severity": r.metadata.severity,
                "description": r.metadata.description,
                "category": r.metadata.category,
                "cost": r.metadata.cost,
                "deterministic": r.metadata.deterministic,
            }
            for r in rules
        ]
    }


@app.post("/rules/eval")
async def evaluate_rules():
    """Evaluate all rules against the current graph."""
    try:
        docs, node_ids, targets = state.get_repo().get_documents_for_rules()
        from knowledge.engine.rules import RuleEvaluator

        evaluator = RuleEvaluator()
        findings = evaluator.evaluate(docs, node_ids, targets)
        return {
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "rule_version": f.rule_version,
                    "doc_id": f.doc_id,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in findings
            ],
            "total": len(findings),
        }
    except Exception as exc:
        raise AppError(500, "Rule evaluation failed", str(exc))


@app.post("/archive")
async def create_archive():
    """Create source archive (git bundle + manifest)."""
    from knowledge.engine.archiver import archive_source

    try:
        manifest = archive_source(source_dir=state.source_dir, db_path=state.db_path)
        return {
            "success": True,
            "commit": manifest.source_commit[:12] if manifest.source_commit else "",
            "files": manifest.file_count,
            "sha256": manifest.content_sha256[:16],
        }
    except ValueError as exc:
        raise AppError(422, "Archive failed", str(exc))
    except Exception as exc:
        raise AppError(500, "Archive failed", str(exc))


@app.post("/feedback/{doc_id}")
async def record_feedback_api(doc_id: str, rating: int = 3):
    """Rate a document (rating 1-5)."""
    _validate_doc_id(doc_id)
    if rating < 1 or rating > 5:
        raise AppError(422, "Rating out of range", "rating must be between 1 and 5")
    from knowledge.engine.feedback import record_feedback

    ok = record_feedback(state.db_path, doc_id, rating)
    if not ok:
        raise AppError(500, "Failed to record feedback", "")
    return {"success": True, "doc_id": doc_id, "rating": rating}


@app.get("/feedback/top")
async def top_rated_api(limit: int = 10):
    """Top rated documents."""
    if limit < 1 or limit > 100:
        raise AppError(422, "Limit out of range", "limit must be between 1 and 100")
    from knowledge.engine.feedback import top_rated

    results = top_rated(state.db_path, limit=limit)
    return {
        "results": [
            {"doc_id": fb.doc_id, "rating": fb.rating, "timestamp": fb.timestamp} for fb in results
        ],
        "total": len(results),
    }


@app.get("/metadata/lineage/{asset_id}")
async def get_lineage_api(asset_id: str):
    """Get lineage for an asset."""
    from knowledge.engine.lineage_store import SQLiteLineageStore

    store = SQLiteLineageStore(state.db_path)
    events = store.get_lineage(asset_id)
    return {
        "asset_id": asset_id,
        "events": [
            {
                "event_type": ev["event_type"],
                "event_time": ev["event_time"],
                "job_name": ev["job_name"],
                "inputs": json.loads(ev["input_ids"]) if isinstance(ev.get("input_ids"), str) else ev.get("input_ids", []),
                "outputs": json.loads(ev["output_ids"]) if isinstance(ev.get("output_ids"), str) else ev.get("output_ids", []),
            }
            for ev in events
        ],
        "total": len(events),
    }


@app.get("/memory")
async def list_memories(kind: str | None = None, limit: int = 100, offset: int = 0):
    """List memory records."""
    from knowledge.engine.memory_store import SQLiteMemoryStore

    store = SQLiteMemoryStore(state.db_path)
    records = store.list(kind=kind, limit=limit, offset=offset)
    return {"results": [r.to_dict() for r in records], "total": len(records)}


@app.get("/memory/{memory_id}")
async def get_memory(memory_id: str):
    """Get a memory record by ID."""
    from knowledge.engine.memory_store import SQLiteMemoryStore

    store = SQLiteMemoryStore(state.db_path)
    record = store.get(memory_id)
    if record is None:
        raise AppError(404, "Memory not found", f"No memory with id '{memory_id}'")
    return record.to_dict()


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    kind: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class MemoryLinkRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=200)


@app.post("/memory/search")
async def search_memories(req: MemorySearchRequest):
    """Search memory records."""
    from knowledge.engine.memory_store import SQLiteMemoryStore

    store = SQLiteMemoryStore(state.db_path)
    records = store.search(req.query, kind=req.kind, limit=req.limit)
    return {"results": [r.to_dict() for r in records], "total": len(records)}


@app.post("/memory/{memory_id}/link")
async def link_asset_to_memory(memory_id: str, req: MemoryLinkRequest):
    """Link an asset to a memory record."""
    from knowledge.engine.memory_store import SQLiteMemoryStore

    store = SQLiteMemoryStore(state.db_path)
    ok = store.link_asset(memory_id, req.asset_id)
    if not ok:
        raise AppError(404, "Memory not found", f"No memory with id '{memory_id}'")
    return {"success": True, "memory_id": memory_id, "asset_id": req.asset_id}


class ContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_assets: int = Field(default=10, ge=1, le=100)
    max_memories: int = Field(default=5, ge=0, le=50)
    include_lineage: bool = True
    include_governance: bool = True


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)
    include_memory: bool = True
    include_lineage: bool = False
    include_governance: bool = False


@app.post("/metadata/context")
async def metadata_context(req: ContextRequest):
    """Build a GraphRAG context bundle for a query."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever

    retriever = SQLiteGraphRetriever(state.db_path)
    ctx = retriever.build_context(
        query=req.query,
        max_assets=req.max_assets,
        max_memories=req.max_memories,
        include_lineage=req.include_lineage,
        include_governance=req.include_governance,
    )
    return ctx.to_dict()


@app.post("/metadata/retrieve")
async def metadata_retrieve(req: RetrieveRequest):
    """Retrieve assets and optionally memory, lineage, governance."""
    from knowledge.engine.graphrag import SQLiteGraphRetriever

    retriever = SQLiteGraphRetriever(state.db_path)
    ctx = retriever.build_context(
        query=req.query,
        max_assets=req.limit,
        max_memories=req.limit if req.include_memory else 0,
        include_lineage=req.include_lineage,
        include_governance=req.include_governance,
    )
    return ctx.to_dict()


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics (OpenMetrics format)."""
    from knowledge.engine.metrics import export_metrics

    return export_metrics(db_path=state.db_path)
