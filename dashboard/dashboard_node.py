#!/usr/bin/env python3
"""URA Dashboard — muestra estado de los 8 nodos en tiempo real."""

import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

PORT = 5050
NODES = {
    "Disco": 8101,
    "Ollama": 8102,
    "Limpieza": 8103,
    "Procesos": 8104,
    "Red": 8105,
    "RAM": 8106,
    "Backup": 8107,
    "Salud": 8108,
}

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>URA Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e27;color:#e0e0e0;font-family:monospace;padding:20px}
h1{text-align:center;color:#00f0ff;margin-bottom:20px;font-size:1.5em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:15px}
.card{background:#111633;border:1px solid #1a1f44;border-radius:8px;padding:15px}
.card h3{margin:0 0 8px 0;font-size:1em}
.card .status{font-size:2em;margin:8px 0}
.card .detail{font-size:0.8em;color:#888}
.ok{border-color:#28a745}.ok .status{color:#28a745}
.warning{border-color:#ffc107}.warning .status{color:#ffc107}
.error,.critical{border-color:#dc3545}.error .status,.critical .status{color:#dc3545}
.pending{border-color:#6c757d}.pending .status{color:#6c757d}
.refresh{text-align:center;margin-top:20px;color:#555;font-size:0.8em}
</style>
<script>
function refresh() { location.reload(); }
setTimeout(refresh, 30000);
</script>
</head>
<body>
<h1>URA Monitoring</h1>
<div class="grid">
{CARDS}
</div>
<div class="refresh">Actualiza cada 30s</div>
</body>
</html>"""


def build_card(name, port):
    try:
        r = requests.get(f"http://localhost:{port}/health", timeout=3)
        data = r.json()
        estado = data.get("estado", "unknown")
        detail = ""
        if "gb_libres" in data:
            detail = f"{data['gb_libres']:.1f} GB libres"
        elif "latencia_ms" in data:
            detail = f"{data['latencia_ms']:.1f} ms"
        elif "zombies_killed" in data:
            detail = f"{data.get('zombies_killed', 0)} muertos"
        elif "ram_libre_gb" in data:
            detail = f"{data['ram_libre_gb']:.1f} GB libres"
        css = (
            "ok"
            if estado in ("ok", "healthy")
            else ("pending" if estado == "pendiente" else "error")
        )
        icon = {
            "ok": "✅",
            "healthy": "✅",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
            "pendiente": "⏳",
        }.get(estado, "❓")
        return f'<div class="card {css}"><h3>{name}</h3><div class="status">{icon}</div><div class="detail">{detail}</div></div>'
    except Exception:
        return f'<div class="card error"><h3>{name}</h3><div class="status">❌</div><div class="detail">Sin conexión</div></div>'


def build_metrics():
    """Formato Prometheus text exposition."""
    lines = ["# HELP ura_node_health URA node health status (1=ok, 0=error)"]
    lines.append("# TYPE ura_node_health gauge")
    for name, port in NODES.items():
        try:
            r = requests.get(f"http://localhost:{port}/health", timeout=3)
            data = r.json()
            estado = data.get("estado", "unknown")
            value = 1 if estado in ("ok", "healthy") else 0
        except Exception:
            value = 0
        label = name.lower()
        lines.append(f'ura_node_health{{node="{label}"}} {value}')

    # Add disk metrics
    try:
        r = requests.get("http://localhost:8101/health", timeout=3)
        data = r.json()
        lines.append("# HELP ura_disk_free_gb Free disk space in GB")
        lines.append("# TYPE ura_disk_free_gb gauge")
        lines.append(f"ura_disk_free_gb {data.get('gb_libres', 0)}")
    except Exception:
        pass

    # Add RAM metrics
    try:
        r = requests.get("http://localhost:8106/health", timeout=3)
        data = r.json()
        lines.append("# HELP ura_ram_free_gb Free RAM in GB")
        lines.append("# TYPE ura_ram_free_gb gauge")
        lines.append(f"ura_ram_free_gb {data.get('ram_libre_gb', 0)}")
    except Exception:
        pass

    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/metrics":
            content = build_metrics()
            ct = "text/plain; version=0.0.4"
        else:
            cards = "".join(build_card(name, port) for name, port in NODES.items())
            content = TEMPLATE.replace("{CARDS}", cards)
            ct = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(content.encode())


if __name__ == "__main__":
    print(f"URA Dashboard en http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
