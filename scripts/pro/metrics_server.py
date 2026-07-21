#!/usr/bin/env python3
"""metrics_server.py — URA Search Quality Dashboard.

Sirve métricas en tiempo real desde search_quality.ndjson usando
tail (-n 1000) para evitar degradación de disco.
Endpoints:
  GET /health        → Health check con estado de componentes
  GET /ready         → Readiness check
  GET /metrics       → JSON con métricas calculadas
  GET /metrics?format=html → tabla HTML con auto-refresh 30s
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from aiohttp import web
from motor.observability import HealthRegistry
from motor.intelligence.memory.hybrid import HybridMemory

log = logging.getLogger("ura.metrics")

LOG_DIR = Path(
    os.environ.get(
        "METRICS_LOG_DIR",
        "/tmp/ura_search_logs",
    ),
)
TAIL_LINES = int(os.environ.get("METRICS_TAIL_LINES", "1000"))
HOST = os.environ.get("METRICS_HOST", "0.0.0.0")  # noqa: S104
PORT = int(os.environ.get("METRICS_PORT", "9091"))

_health = HealthRegistry()
_health.register_component("metrics_server")
_memory = HybridMemory(db_path=os.environ.get("URA_MEMORY_DB", str(Path.home() / ".ura" / "memory.db")))


def _compute_metrics(lines: list[str]) -> dict:
    events = [json.loads(line) for line in lines if line.strip()]
    if not events:
        return {"status": "no_data", "total_queries": 0}

    total = len(events)
    latencies = []
    hybrid_count = 0
    reranker_count = 0
    lang_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}

    for e in events:
        sources = e.get("sources", [])
        latencies.append(e.get("latency_ms", 0))
        if e.get("use_hybrid"):
            hybrid_count += 1
        if e.get("use_reranker"):
            reranker_count += 1
        for lang in e.get("idiomas", []):
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        for src in sources:
            source_counts[src] = source_counts.get(src, 0) + 1

    precision = {"p@1": 0.0, "p@3": 0.0, "p@5": 0.0}
    if total > 0:
        precision["p@1"] = round(sum(1 for e in events if e.get("num_results", 0) > 0) / total, 4)
        precision["p@3"] = round(sum(1 for e in events if e.get("num_results", 0) >= 3) / total, 4)
        precision["p@5"] = round(sum(1 for e in events if e.get("num_results", 0) >= 5) / total, 4)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    return {
        "status": "ok",
        "total_queries": total,
        "precision": precision,
        "latency_ms": {"p50": round(p50, 2), "p95": round(p95, 2)},
        "usage": {
            "hybrid_pct": round(hybrid_count / total * 100, 1) if total else 0,
            "reranker_pct": round(reranker_count / total * 100, 1) if total else 0,
        },
        "languages": dict(sorted(lang_counts.items(), key=lambda x: -x[1])[:10]),
        "top_sources": dict(sorted(source_counts.items(), key=lambda x: -x[1])[:10]),
    }


async def handle_metrics(request: web.Request) -> web.Response:
    files = sorted(LOG_DIR.glob("search_*.ndjson"), reverse=True) if LOG_DIR.exists() else []  # noqa: ASYNC240
    log_path = files[0] if files else LOG_DIR / "no_data.ndjson"

    proc = await asyncio.create_subprocess_exec(
        "tail",
        "-n",
        str(TAIL_LINES),
        str(log_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = stdout.decode().splitlines()
    metrics = _compute_metrics(lines)

    fmt = request.query.get("format", "json")
    if fmt == "html":
        html = (
            "<html><head><title>URA Search Metrics</title>"
            '<meta http-equiv="refresh" content="30">'
            "<style>body{font-family:monospace;background:#111;color:#0f0;padding:2rem}"
            "pre{background:#222;padding:1rem;border-radius:4px}"
            "a{color:#0ff}</style></head><body>"
            "<h1>URA Search Metrics</h1>"
            "<pre>" + json.dumps(metrics, indent=2) + "</pre>"
            '<a href="/metrics?format=json">JSON</a>'
            "</body></html>"
        )
        return web.Response(text=html, content_type="text/html")

    return web.json_response(metrics)


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response(_health.snapshot())


async def handle_ready(request: web.Request) -> web.Response:
    snap = _health.snapshot()
    status = 200 if snap.get("global") in ("healthy", "degraded") else 503
    return web.json_response(snap, status=status)


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>URA Dashboard</title>
<meta http-equiv="refresh" content="15">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:2rem}}
  h1{{color:#58a6ff;margin-bottom:1rem}}
  h2{{color:#8b949e;margin:1.5rem 0 0.5rem;font-size:1.1rem;text-transform:uppercase;letter-spacing:0.05em}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}}
  .card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem}}
  .card h3{{color:#58a6ff;font-size:0.9rem;margin-bottom:0.5rem}}
  .ok{{color:#3fb950}} .warn{{color:#d29922}} .err{{color:#f85149}}
  .stat{{display:flex;justify-content:space-between;padding:0.25rem 0;border-bottom:1px solid #21262d}}
  .stat:last-child{{border:none}}
  .label{{color:#8b949e}} .value{{font-weight:600}}
  .footer{{margin-top:2rem;color:#484f58;font-size:0.8rem;text-align:center}}
  pre{{background:#0d1117;padding:0.5rem;border-radius:4px;font-size:0.8rem;overflow-x:auto}}
</style>
</head>
<body>
<h1>URA System Dashboard</h1>
<div class="grid" id="root">{content}</div>
<pre id="raw" style="display:none"></pre>
<div class="footer">URA v4.5.1 &mdash; auto-refresh 15s</div>
<script>
async function refresh(){{
  try{{
    const [h,m,mem] = await Promise.all([
      fetch('/health').then(r=>r.json()),
      fetch('/metrics').then(r=>r.json()),
      fetch('/memory').then(r=>r.json()).catch(()=>({{}}))
    ]);
    let html = '';
    // Health card
    html += '<div class="card"><h3>Estado del Sistema</h3>';
    const g = h.global||'unknown';
    html += `<div class="stat"><span class="label">Global</span><span class="${{g==='healthy'?'ok':g==='degraded'?'warn':'err'}}">${{g}}</span></div>`;
    if(h.components) for(const[name,comp] of Object.entries(h.components)){{
      html += `<div class="stat"><span class="label">${{name}}</span><span class="${{comp.status==='healthy'?'ok':comp.status==='degraded'?'warn':'err'}}">${{comp.status}}${{comp.reason?': '+comp.reason:''}}</span></div>`;
    }}
    html += '</div>';
    // Metrics card
    html += '<div class="card"><h3>Métricas de Búsqueda</h3>';
    if(m.total_queries>0){{
      html += `<div class="stat"><span class="label">Consultas</span><span class="value">${{m.total_queries}}</span></div>`;
      html += `<div class="stat"><span class="label">Latencia p50</span><span class="value">${{m.latency_ms?.p50||0}}ms</span></div>`;
      html += `<div class="stat"><span class="label">Latencia p95</span><span class="value">${{m.latency_ms?.p95||0}}ms</span></div>`;
      html += `<div class="stat"><span class="label">Híbrido</span><span class="value">${{m.usage?.hybrid_pct||0}}%</span></div>`;
    }}else{{
      html += '<div class="stat"><span class="label">Datos</span><span class="warn">sin datos</span></div>';
    }}
    html += '</div>';
    // Memory card
    html += '<div class="card"><h3>Memoria Híbrida</h3>';
    html += `<div class="stat"><span class="label">Registros</span><span class="value">${{mem.total_records??'N/A'}}</span></div>`;
    html += `<div class="stat"><span class="label">Vector Store</span><span class="${{mem.vector_store_ok?'ok':'err'}}">${{mem.vector_store_ok?'OK':'OFF'}}</span></div>`;
    html += '</div>';
    document.getElementById('root').innerHTML = html;
  }}catch(e){{
    document.getElementById('raw').style.display='block';
    document.getElementById('raw').textContent = 'Error: '+e;
  }}
}}
refresh();
</script>
</body>
</html>"""


async def handle_dashboard(request: web.Request) -> web.Response:
    snap = _health.snapshot()
    global_status = snap.get("global", "unknown")
    healthy_count = snap.get("healthy_count", 0)
    components = snap.get("components", {})
    mem = _memory.health()

    comp_rows = "".join(
        f'<div class="stat"><span class="label">{name}</span>'
        f'<span class="{"ok" if c["status"] == "healthy" else "warn" if c["status"] == "degraded" else "err"}">'
        f"{c['status']}{': ' + c['reason'] if c.get('reason') else ''}</span></div>"
        for name, c in sorted(components.items())
    )

    html = _DASHBOARD_HTML.replace(
        "{content}",
        f'<div class="card"><h3>Estado del Sistema</h3>'
        f'<div class="stat"><span class="label">Global</span>'
        f'<span class="{"ok" if global_status == "healthy" else "warn" if global_status == "degraded" else "err"}">{global_status}</span></div>'
        f'<div class="stat"><span class="label">Componentes saludables</span><span class="ok">{healthy_count}</span></div>'
        f"{comp_rows}</div>"
        f'<div class="card"><h3>Memoria Híbrida</h3>'
        f'<div class="stat"><span class="label">Registros</span><span class="value">{mem.get("total_records", "N/A")}</span></div>'
        f'<div class="stat"><span class="label">Vector Store</span>'
        f'<span class="{"ok" if mem.get("vector_store_ok") else "err"}">{"OK" if mem.get("vector_store_ok") else "OFF"}</span></div>'
        f"</div>"
        f'<div class="card"><h3>Recursos</h3>'
        f'<div class="stat"><span class="label">Python</span><span class="value">3.12</span></div>'
        f'<div class="stat"><span class="label">Entorno</span><span class="value">{os.environ.get("URA_ENV", "produccion")}</span></div>'
        f"</div>",
    )
    return web.Response(text=html, content_type="text/html")


_GIT_VERSION = ""


def _get_version() -> str:
    global _GIT_VERSION
    if not _GIT_VERSION:
        try:
            _GIT_VERSION = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, timeout=5, check=False
            ).stdout.strip()
        except Exception:
            _GIT_VERSION = "unknown"
    return _GIT_VERSION


LEDGER_DIR = Path.home() / ".nervioso" / "ledger"


async def handle_memory(request: web.Request) -> web.Response:
    return web.json_response(_memory.health())


async def handle_version(request: web.Request) -> web.Response:
    return web.json_response({"version": _get_version(), "python": "3.12", "name": "ura"})


async def handle_pipeline_status(request: web.Request) -> web.Response:
    if not LEDGER_DIR.exists():
        return web.json_response({"status": "no_data", "detail": "LEDGER_DIR no existe"})
    files = sorted(LEDGER_DIR.glob("*.json"), reverse=True)
    if not files:
        return web.json_response({"status": "no_data", "detail": "Sin ejecuciones en ledger"})
    try:
        data = json.loads(files[0].read_text())
        return web.json_response(
            {
                "status": "ok",
                "ultima_ejecucion": data.get("timestamp", ""),
                "pipeline": data.get("pipeline", ""),
                "resultado": data.get("result", ""),
                "trigger": data.get("trigger", ""),
                "archivo": files[0].name,
            }
        )
    except Exception as e:
        return web.json_response({"status": "error", "detail": str(e)})


TRENDS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "architecture" / "arq_trends.jsonl"


async def handle_arq_trends(request: web.Request) -> web.Response:
    if not TRENDS_PATH.exists():
        return web.json_response({"status": "no_data", "entries": []})
    try:
        lines = TRENDS_PATH.read_text().strip().split("\n")
        entries = [json.loads(l) for l in lines if l.strip()]
        return web.json_response({"status": "ok", "entries": entries[-50:]})  # últimas 50
    except Exception as e:
        return web.json_response({"status": "error", "detail": str(e)})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app = web.Application()
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ready", handle_ready)
    app.router.add_get("/dashboard", handle_dashboard)
    app.router.add_get("/memory", handle_memory)
    app.router.add_get("/version", handle_version)
    app.router.add_get("/pipeline/status", handle_pipeline_status)
    app.router.add_get("/arq/trends", handle_arq_trends)
    _health.set_healthy("metrics_server")
    _health.register_component("hybrid_memory")
    _health.set_healthy("hybrid_memory", f"{_memory.count()} registros")
    _health.register_component("pipeline")
    _health.set_healthy("pipeline")
    log.info("Metrics server starting on %s:%s (tail -n %s)", HOST, PORT, TAIL_LINES)
    web.run_app(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
