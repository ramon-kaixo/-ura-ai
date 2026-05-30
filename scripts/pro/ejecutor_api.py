#!/usr/bin/env python3
"""ejecutor_api.py — Endpoint de automatizacion remota para URA.
Recibe tareas de desarrollo de la Tuneladora y las ejecuta.
Puerto: 4096 (OpenCode)
"""

import json
import os
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

CONTEXT_PATH = os.path.expanduser("~/.config/opencode/ura_context.json")
MCP_SYNC = "http://10.164.1.26:9093"
HOST = "0.0.0.0"
PORT = 4096


def log_evento(evento, datos=None):
    """Registra evento en MCP Sync del Mac Mini."""
    import urllib.request

    payload = {"evento": evento, "timestamp": datetime.utcnow().isoformat(), "data": datos or {}}
    try:
        req = urllib.request.Request(
            f"{MCP_SYNC}/log",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def leer_contexto():
    """Lee el contexto compartido Ura-OpenCode."""
    if os.path.exists(CONTEXT_PATH):
        with open(CONTEXT_PATH) as f:
            return json.load(f)
    return {}


def escribir_contexto(ctx):
    """Escribe el contexto compartido."""
    os.makedirs(os.path.dirname(CONTEXT_PATH), exist_ok=True)
    with open(CONTEXT_PATH, "w") as f:
        json.dump(ctx, f, indent=2)


def ejecutar_tarea(task_desc, target_files):
    """Ejecuta una tarea de desarrollo y actualiza el contexto."""
    print(f"  Ejecutando: {task_desc[:80]}...")

    # 1. Actualizar contexto
    ctx = leer_contexto()
    ctx["opencode_agent"]["ultima_sincronizacion"] = datetime.utcnow().isoformat()
    ctx["opencode_agent"]["estado"] = "ejecutando"
    ctx["opencode_agent"]["tarea_actual"] = {
        "descripcion": task_desc,
        "archivos": target_files,
        "inicio": datetime.utcnow().isoformat(),
    }
    escribir_contexto(ctx)
    log_evento("tarea_iniciada", {"descripcion": task_desc[:50], "archivos": target_files})

    # 2. Ejecutar en segundo plano (no bloquea la Tuneladora)
    def worker():
        try:
            # Abrir terminal para ejecutar opencode run-context
            cmd = ["opencode", "run-context"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            output = result.stdout[:1000] if result.stdout else result.stderr[:500]

            # Actualizar contexto con resultado
            ctx = leer_contexto()
            ctx["opencode_agent"]["estado"] = "completado"
            ctx["opencode_agent"]["ultimo_resultado"] = output[:500]
            ctx["opencode_agent"]["tareas_completadas"].append(task_desc[:60])
            escribir_contexto(ctx)
            log_evento("tarea_completada", {"resultado": output[:200]})

        except Exception as e:
            ctx = leer_contexto()
            ctx["opencode_agent"]["estado"] = "error"
            ctx["opencode_agent"]["ultimo_error"] = str(e)
            escribir_contexto(ctx)
            log_evento("tarea_error", {"error": str(e)})

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "aceptada", "tarea": task_desc[:60]}


class ExecutorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/openclaw/ejecutar":
            task_desc = body.get("task_description", body.get("comando", ""))
            target_files = body.get("target_files", [])
            result = ejecutar_tarea(task_desc, target_files)
        elif self.path == "/status":
            ctx = leer_contexto()
            result = {
                "status": ctx.get("opencode_agent", {}).get("estado", "idle"),
                "ultima_tarea": ctx.get("opencode_agent", {}).get("tarea_actual", {}),
                "completadas": len(ctx.get("opencode_agent", {}).get("tareas_completadas", [])),
            }
        else:
            result = {"error": "not found"}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        ctx = leer_contexto()
        status = ctx.get("opencode_agent", {}).get("estado", "idle")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "servicio": "OpenCode Executor API",
                    "estado": status,
                    "puerto": PORT,
                    "agente": "OpenCode - Brazo ejecutor de URA",
                }
            ).encode()
        )

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"OpenCode Executor API en http://{HOST}:{PORT}")
    log_evento("ejecutor_api_iniciado", {"puerto": PORT})
    HTTPServer((HOST, PORT), ExecutorHandler).serve_forever()
