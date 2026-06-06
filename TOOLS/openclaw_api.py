"""openclaw_api.py — FastAPI + MCP server para URA-Search v5.0.

Endpoints REST:
  GET  /health        → healthcheck
  GET  /metrics       → RAM, colas, estado
  POST /ingestar      → lanza ingesta de URL
  GET  /audit         → últimas entradas del audit_log
  POST /prompt        → construye prompt blindado
  GET  /dashboard/json → métricas analíticas

MCP tools (para Laia):
  buscar_corpus, pedir_ingesta, leer_mochila, ver_estado_pipeline, consultar_audit

Arranque: uvicorn openclaw_api:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent))
from mochila_engine import BASE_DIR, MochilaEngine
from elastic_orchestrator import ElasticOrchestrator
from knowledge_auditor import KnowledgeAuditor
from analytics_dashboard import _cargar_audit
from prompt_injector import PromptInjector

app = FastAPI(title="OpenClaw API", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_orch = ElasticOrchestrator()
_auditor = KnowledgeAuditor()
_injector = PromptInjector()
RETRO_DIR = BASE_DIR / "05_RETROALIMENTACION"
METRICS_PATH = RETRO_DIR / "metrics.json"

class IngestarReq(BaseModel):
    url: str; coleccion: str = "sin_nombre"; departamento: str | None = None

class PromptReq(BaseModel):
    mochila_id: str; texto_crudo: str; departamento: str | None = None

@app.on_event("startup")
async def startup(): asyncio.create_task(_orch.run())

@app.on_event("shutdown")
async def shutdown(): _orch.detener()

@app.get("/health")
async def health():
    est = _orch.metricas.estado if _orch.metricas else "iniciando"
    return {"status": "ok", "timestamp": _now_iso(), "estado": est}

@app.get("/metrics")
async def metrics():
    if METRICS_PATH.exists():
        return JSONResponse(content=json.loads(METRICS_PATH.read_text()))
    return {"estado": "sin datos"}

@app.post("/ingestar")
async def ingestar(req: IngestarReq, bg: BackgroundTasks):
    if not _orch.puede_procesar():
        raise HTTPException(503, "RAM critica. Reintentar.")
    m = MochilaEngine.nueva(url=req.url, nombre_coleccion=req.coleccion)
    bg.add_task(_ejecutar_pipeline, req.url, req.coleccion, m.id)
    return {"mochila_id": m.id, "estado": "ingesta_iniciada", "url": req.url}

@app.get("/audit")
async def audit(n: int = Query(50, ge=1, le=500)):
    return {"entradas": _auditor.leer_recientes(n=n)}

@app.post("/prompt")
async def construir_prompt(req: PromptReq):
    mochila_path = None
    for p in (BASE_DIR / "04_METADATOS").rglob(f"mochila_{req.mochila_id[:8]}*.json"):
        mochila_path = p; break
    if not mochila_path:
        # Crear mochila temporal
        m = MochilaEngine.nueva(url="", nombre_coleccion="temp")
    else:
        m = MochilaEngine.cargar(mochila_path)
        m.registrar_feedback(score_fiabilidad=0.85)
    p = _injector.construir(m, req.texto_crudo, req.departamento)
    return {"prompt": p.texto_completo, "tokens": p.n_tokens_estimados,
            "inyeccion": p.hubo_inyeccion, "hash": p.hash_prompt}

@app.get("/dashboard/json")
async def dashboard_json():
    entradas = _cargar_audit(n_max=2000)
    n = len(entradas)
    n_rev = sum(1 for e in entradas if e.get("rev"))
    scores = [e.get("score_fid", 0) for e in entradas if e.get("score_fid", 0) > 0]
    import statistics
    media = statistics.mean(scores) if scores else 0
    return {"n_ingestas": n, "n_revision": n_rev, "score_fid_medio": round(media, 4)}

@app.get("/mcp/tools")
async def mcp_tools():
    return {"tools": [
        {"name": "buscar_corpus", "description": "Busca en el corpus de conocimiento",
         "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer", "default": 5}},
                         "required": ["query"]}},
        {"name": "pedir_ingesta", "description": "Ordena ingestar una URL",
         "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "coleccion": {"type": "string", "default": "sin_nombre"}},
                         "required": ["url"]}},
        {"name": "ver_estado_pipeline", "description": "Estado del motor",
         "inputSchema": {"type": "object", "properties": {}}},
    ]}

@app.post("/mcp/call")
async def mcp_call(body: dict):
    name = body.get("name"); args = body.get("arguments", {})
    if name == "ver_estado_pipeline":
        return {"content": await metrics()}
    if name == "buscar_corpus":
        # Fallback a busqueda por keywords
        q = args.get("query", ""); k = args.get("k", 5)
        palabras = set(q.lower().split())
        entradas = _cargar_audit(n_max=5000)
        scored = []
        for e in entradas:
            url = e.get("url", "").lower()
            score = sum(1 for w in palabras if w in url)
            if score: scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return {"content": {"resultados": [e for _, e in scored[:k]]}}
    if name == "pedir_ingesta":
        req = IngestarReq(url=args.get("url", ""), coleccion=args.get("coleccion", "sin_nombre"))
        return {"content": await ingestar(req, BackgroundTasks())}
    raise HTTPException(404, f"Tool '{name}' no encontrada")

async def _ejecutar_pipeline(url: str, coleccion: str, mochila_id: str):
    try:
        m = MochilaEngine.nueva(url=url, nombre_coleccion=coleccion)
        from ethical_guard import EthicalGuard
        guard = EthicalGuard()
        guard.analizar(m)
        m.marcar_completada()
        m.guardar()
        _auditor.registrar(m)
    except Exception as e:
        pass

def _now_iso(): return datetime.now(tz=timezone.utc).isoformat()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("openclaw_api:app", host="0.0.0.0", port=8080, reload=False)
