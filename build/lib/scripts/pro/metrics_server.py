#!/usr/bin/env python3
"""metrics_server.py — URA Search Quality Dashboard.

Sirve métricas en tiempo real desde search_quality.ndjson usando
tail (-n 1000) para evitar degradación de disco.
Endpoints:
  GET /health        → {"status": "ok"}
  GET /metrics       → JSON con métricas calculadas
  GET /metrics?format=html → tabla HTML con auto-refresh 30s
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from aiohttp import web

log = logging.getLogger("ura.metrics")

LOG_DIR = Path(
    os.environ.get(
        "METRICS_LOG_DIR",
        "/tmp/ura_search_logs",
    ),
)
TAIL_LINES = int(os.environ.get("METRICS_TAIL_LINES", "1000"))
HOST = os.environ.get("METRICS_HOST", "0.0.0.0")
PORT = int(os.environ.get("METRICS_PORT", "9091"))


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
    files = sorted(LOG_DIR.glob("search_*.ndjson"), reverse=True) if LOG_DIR.exists() else []
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
    return web.json_response({"status": "ok"})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app = web.Application()
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_get("/health", handle_health)
    log.info("Metrics server starting on %s:%s (tail -n %s)", HOST, PORT, TAIL_LINES)
    web.run_app(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
