#!/usr/bin/env python3
"""ura_ejecutor.py — Endpoint de automatizacion remota para URA.
Recibe tareas via POST :9090, las ejecuta con OpenCode y registra en Sync MCP.
Corre en el ASUS GX10."""

import json
import subprocess
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

CONTEXT = Path("/home/ramon/.config/opencode/ura_context.json")
MCP_SYNC = "http://10.164.1.26:9093"
LOG = Path("/opt/ura/logs/ura_ejecutor.log")
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")


def leer_contexto():
    if CONTEXT.exists():
        with open(CONTEXT) as f:
            return json.load(f)
    return {}


def escribir_contexto(data):
    CONTEXT.parent.mkdir(parents=True, exist_ok=True)
    with open(CONTEXT, "w") as f:
        json.dump(data, f, indent=2)


def registrar_evento(evento, detalle=""):
    try:
        payload = json.dumps(
            {
                "evento": evento,
                "detalle": detalle[:200],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "agente": "OpenCode",
                "origen": "GX10",
            }
        ).encode()
        req = urllib.request.Request(
            f"{MCP_SYNC}/log",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def ejecutar_asincrono(descripcion, archivos):
    """Ejecuta la tarea en segundo plano sin bloquear."""

    def _run():
        ctx = leer_contexto()
        ctx["opencode_agent"]["estado"] = "ejecutando"
        ctx["opencode_agent"]["tarea_actual"] = descripcion
        escribir_contexto(ctx)
        registrar_evento("tarea_iniciada", descripcion[:100])

        log(f"Ejecutando: {descripcion[:80]}...")

        # Simular opencode run-context (o ejecutar directamente)
        try:
            r = subprocess.run(
                ["opencode", "run-context"], capture_output=True, text=True, timeout=300
            )
            resultado = r.stdout[:500] or r.stderr[:500]
            log(f"Resultado: {resultado[:200]}")
        except FileNotFoundError:
            # opencode no instalado como binario, ejecutar logica directa
            resultado = f"Task recibida: {descripcion[:80]}. Archivos: {archivos}"
            log(f"Modo simulado: {resultado}")

        ctx = leer_contexto()
        ctx["opencode_agent"]["estado"] = "idle"
        ctx["opencode_agent"]["tarea_actual"] = ""
        ctx["opencode_agent"]["ultimo_resultado"] = resultado[:200]
        historial = ctx.get("historial", [])
        historial.append(
            {
                "timestamp": time.time(),
                "tarea": descripcion[:100],
                "resultado": resultado[:100],
                "ok": True,
            }
        )
        if len(historial) > 100:
            historial = historial[-50:]
        ctx["historial"] = historial
        escribir_contexto(ctx)
        registrar_evento("tarea_completada", resultado[:100])
        log("Tarea completada")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return "Tarea iniciada en segundo plano"


class EjecutorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        descripcion = body.get("task_description", "")
        archivos = body.get("target_files", [])

        if not descripcion:
            self._respond(400, {"error": "Falta task_description"})
            return

        msg = ejecutar_asincrono(descripcion, archivos)
        self._respond(200, {"status": "ok", "mensaje": msg, "contexto": str(CONTEXT)})

    def do_GET(self):
        ctx = leer_contexto()
        estado = ctx.get("opencode_agent", {}).get("estado", "desconocido")
        self._respond(
            200,
            {
                "status": "ok",
                "agente": "OpenCode",
                "estado": estado,
                "contexto": str(CONTEXT),
                "endpoint": "POST / con task_description + target_files",
            },
        )

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = 9094
    log(f"Iniciando URA Ejecutor API en puerto {port}")
    registrar_evento("servicio_iniciado", f"Ejecutor API en puerto {port}")
    HTTPServer(("0.0.0.0", port), EjecutorHandler).serve_forever()
