#!/usr/bin/env python3
"""ejecutor_api.py — Endpoint de automatizacion remota para URA.
Recibe tareas de desarrollo de la Tuneladora y las ejecuta.
Puerto: 4096 (OpenCode).
"""

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

CONTEXT_PATH = os.path.expanduser("~/.config/opencode/ura_context.json")
MCP_SYNC = os.environ.get("MCP_SYNC_URL", "http://10.164.1.26:9093")
HOST = os.environ.get("EXECUTOR_HOST", "127.0.0.1")
PORT = int(os.environ.get("EXECUTOR_PORT", "4096"))

# Qdrant + embedding para /v2/interact
from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient

_qdrant = None
_ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

def _get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient.instancia(UraConfig.load())
    return _qdrant


def log_evento(evento, datos=None) -> None:
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
    except Exception:
        pass


def leer_contexto():
    if os.path.exists(CONTEXT_PATH):
        with open(CONTEXT_PATH) as f:
            return json.load(f)
    return {}


def escribir_contexto(ctx) -> None:
    os.makedirs(os.path.dirname(CONTEXT_PATH), exist_ok=True)
    with open(CONTEXT_PATH, "w") as f:
        json.dump(ctx, f, indent=2)


def ejecutar_tarea(task_desc, target_files):
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

    def worker() -> None:
        try:
            cmd = ["opencode", "run-context"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            output = result.stdout[:1000] if result.stdout else result.stderr[:500]
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


# === Handler /v2/interact ===

def _distancia_coseno(a: list[float], b: list[float]) -> float:
    """Distancia coseno entre dos vectores. 0 = idénticos, 1 = ortogonales."""
    import math
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 1.0
    return 1.0 - (dot / (na * nb))


def handle_interact(body: dict) -> dict:
    qdrant = _get_qdrant()
    tx_id = body.get("id", str(uuid.uuid4()))
    raw = body.get("raw", "")
    structure = body.get("structure", {})

    # 1. Generar embeddings
    emb_raw = qdrant.generar_embedding(raw) if raw else [0.0] * 768
    raw_struct = json.dumps(structure, sort_keys=True)
    emb_struct = qdrant.generar_embedding(raw_struct) if raw_struct != "{}" else [0.0] * 768

    # 2. Comparar RAW vs STRUCT
    distancia = _distancia_coseno(emb_raw, emb_struct)
    alerta = distancia > 0.5

    # 3. Almacenar en Qdrant (coleccion transacciones)
    payload = {
        "tx_id": tx_id,
        "raw": raw[:2000],
        "structure": raw_struct[:2000],
        "raw_distance_struct": round(distancia, 4),
        "timestamp": datetime.utcnow().isoformat(),
    }
    qdrant.guardar_documento(tx_id, raw, payload)

    # 4. Ejecutar tarea segun intent
    intent = structure.get("intent", "") if isinstance(structure, dict) else ""
    if intent == "ejecutar":
        resultado = ejecutar_tarea(
            structure.get("entities", [raw])[0] if structure.get("entities") else raw,
            structure.get("entities", []),
        )
    else:
        resultado = {"status": "recibido", "nota": "intent no ejecutable, solo registro"}

    log_evento("v2_interact", {"tx_id": tx_id, "intent": intent, "alerta": alerta})

    return {
        "validation": {
            "ok": not alerta,
            "distance": round(distancia, 4),
            "alert": alerta,
        },
        "response": resultado,
        "reflection": {
            "tx_id": tx_id,
            "intent": intent,
            "dominio": structure.get("domain", "general") if isinstance(structure, dict) else "general",
        },
    }


class ExecutorHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/openclaw/ejecutar":
            task_desc = body.get("task_description", body.get("comando", ""))
            target_files = body.get("target_files", [])
            result = ejecutar_tarea(task_desc, target_files)
        elif self.path == "/v2/interact":
            result = handle_interact(body)
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

    def do_GET(self) -> None:
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
                },
            ).encode(),
        )

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    log_evento("ejecutor_api_iniciado", {"puerto": PORT, "host": HOST})
    HTTPServer((HOST, PORT), ExecutorHandler).serve_forever()
