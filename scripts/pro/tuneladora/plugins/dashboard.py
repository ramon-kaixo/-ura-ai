"""DashboardPlugin — web de estado de la tuneladora."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine

HTML_PAGE = """<!DOCTYPE html><html><head>
<title>URA Tuneladora</title>
<style>body{font-family:sans-serif;margin:40px;background:#1a1a2e;color:#eee}
h1{color:#e94560}.ok{color:#4ecca3}.warn{color:#ffc107}.crit{color:#e94560}
.card{background:#16213e;padding:20px;margin:10px 0;border-radius:8px}
</style></head><body>
<h1>URA Tuneladora</h1>
<div class="card">
<p>Estado: <span class="ok"><b>RUNNING</b></span></p>
<p>Pipelines: health (5min), cleanup (60min), audit (6h)</p>
<p>Puerto: 9092</p>
</div>
<div class="card">
<h3>Ultima ejecucion</h3>
<p id="last">Cargando...</p>
</div>
<script>
fetch('/api/status').then(r=>r.json()).then(d=>{
document.getElementById('last').textContent=JSON.stringify(d)
})
</script>
</body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html()
        elif self.path == "/api/status":
            self._send_json()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_html(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode())

    def _send_json(self) -> None:
        data = json.dumps({"running": True, "pipelines": ["health", "cleanup", "audit"]})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data.encode())

    def log_message(self, _format: str, *args: Any) -> None:
        pass


class DashboardPlugin:
    def __init__(self, engine: PipelineEngine, port: int = 9092) -> None:
        self.engine = engine
        self.port = port

    def start(self) -> None:
        server = HTTPServer(("0.0.0.0", self.port), DashboardHandler)  # noqa: S104  # nosec B104
        self.engine.log.info("Dashboard en http://0.0.0.0:%d", self.port)
        server.serve_forever()
