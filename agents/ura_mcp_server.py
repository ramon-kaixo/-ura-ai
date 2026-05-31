#!/usr/bin/env python3
"""URA MCP Server — Tools de conciencia, control y vision para URA."""

import json
import subprocess
import sys
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

LOG_FILE = Path("/opt/ura/data/monologo_interno.json")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def log_accion(name, args_in, result):
    registros = []
    if LOG_FILE.exists():
        try:
            registros = json.loads(LOG_FILE.read_text())
        except:
            pass
    registros.append(
        {
            "timestamp": time.time(),
            "tipo": name,
            "argumentos": args_in,
            "resultado": str(result.get("resultado", ""))[:200] if result.get("resultado") else "",
            "ok": result.get("ok", False),
            "error": result.get("error", ""),
        }
    )
    if len(registros) > 1000:
        registros = registros[-500:]
    LOG_FILE.write_text(json.dumps(registros, indent=2))


TOOLS = [
    {
        "name": "volumen",
        "description": "Volumen del Mac (0-100)",
        "inputSchema": {"type": "object", "properties": {"nivel": {"type": "integer"}}},
    },
    {
        "name": "abrir_app",
        "description": "Abre una app en el Mac",
        "inputSchema": {"type": "object", "properties": {"nombre": {"type": "string"}}},
    },
    {
        "name": "cerrar_app",
        "description": "Cierra una app",
        "inputSchema": {"type": "object", "properties": {"nombre": {"type": "string"}}},
    },
    {
        "name": "sistema",
        "description": "Estado del GX10",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "camaras",
        "description": "Estado camaras Dahua",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vision",
        "description": "Captura pantalla y lee texto con OCR",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "raton",
        "description": "Mueve/clic/lee posicion del raton",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "accion": {"type": "string"},
            },
        },
    },
    {
        "name": "teclear",
        "description": "Escribe texto en el teclado",
        "inputSchema": {"type": "object", "properties": {"texto": {"type": "string"}}},
    },
    {
        "name": "explorar",
        "description": "Explora el sistema y reporta",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def ejecutar_tool(name, args):
    result = {"ok": False, "resultado": "", "error": ""}
    try:
        if name == "volumen":
            set_volumen(args["nivel"], result)
        elif name == "abrir_app":
            abrir_cerrar_app("open", args["nombre"], result)
        elif name == "cerrar_app":
            abrir_cerrar_app("close", args["nombre"], result)
        elif name == "sistema":
            obtener_sistema(result)
        elif name == "camaras":
            contar_cameras(result)
        elif name == "vision":
            reconocer_vision(args.get("accion"), args.get("x"), args.get("y"), result)
        elif name == "raton":
            mover_o_clickar_raton(args.get("accion"), args.get("x"), args.get("y"), result)
        elif name == "teclear":
            teclar_texto(args.get("texto"), result)
        elif name == "explorar":
            explorar_sistema(result)
    except Exception as e:
        result = {"error": str(e)}

    log_accion(name, args, result)
    return result


def set_volumen(nivel, result):
    subprocess.run(["osascript", "-e", f"set volume output volume {nivel}"], timeout=5)
    result["ok"] = True
    result["resultado"] = f"Volumen: {nivel}"


def abrir_cerrar_app(accion, nombre, result):
    subprocess.run(["osascript", "-e", f'tell application "{nombre}" to {accion}'], timeout=10)
    result["ok"] = True
    result["resultado"] = f"{nombre} {accion.lower()}"


def obtener_sistema(result):
    r = subprocess.run(
        ["ssh", "ramon@10.164.1.99", "uptime && free -h | head -2"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    result["ok"] = True
    result["resultado"] = r.stdout or r.stderr


def contar_cameras(result):
    r = subprocess.run(
        ["curl", "-s", "http://10.164.1.99:1984/api/streams"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    streams = json.loads(r.stdout)
    result["ok"] = True
    result["resultado"] = f"{len(streams)} streams configurados"


def reconocer_vision(accion, x, y, result):
    img = "/tmp/ura_vision.png"
    subprocess.run(["screencapture", "-x", img], timeout=5)
    if os.path.exists(img):
        subprocess.run(["tesseract", img, "/tmp/ura_vision_out"], timeout=15)
        txt = ""
        if os.path.exists("/tmp/ura_vision_out.txt"):
            with open("/tmp/ura_vision_out.txt") as f:
                txt = f.read()[:1000]
        result["ok"] = True
        result["resultado"] = txt.strip() or "(pantalla sin texto)"
        try:
            os.unlink(img)
        except:
            pass
    else:
        result["error"] = "No se pudo capturar pantalla"


def mover_o_clickar_raton(accion, x, y, result):
    if accion == "click":
        subprocess.run(
            ["osascript", "-e", f'tell app "System Events" to click at {{{x}, {y}}}'],
            timeout=5,
        )
        result["ok"] = True
        result["resultado"] = f"Click en ({x},{y})"
    elif accion == "posicion":
        r = subprocess.run(
            ["osascript", "-e", 'tell app "System Events" to get position of mouse'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["ok"] = True
        result["resultado"] = r.stdout.strip()
    else:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell app "System Events" to set position of mouse to {{{x}, {y}}}',
            ],
            timeout=5,
        )
        result["ok"] = True
        result["resultado"] = f"Raton en ({x},{y})"


def teclar_texto(texto, result):
    texto = texto.replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'tell app "System Events" to keystroke "{texto}"'], timeout=10
    )
    result["ok"] = True
    result["resultado"] = f"Texto: {texto[:50]}..."


def explorar_sistema(result):
    r1 = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
    r2 = subprocess.run(["ls", "-la", "/Applications/"], capture_output=True, text=True, timeout=5)
    procesos = len(
        [l for l in r1.stdout.splitlines() if "python" in l or "node" in l or "docker" in l]
    )
    apps = len([l for l in r2.stdout.splitlines() if ".app" in l])
    result["ok"] = True
    result["resultado"] = f"Procesos: {procesos} relevantes. Apps: ~{apps}. macOS."


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/mcp/tools":
            result = {"tools": TOOLS}
        elif self.path == "/mcp/call":
            result = ejecutar_tool(body.get("name", ""), body.get("arguments", {}))
        else:
            result = {"error": "not found"}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "tools": len(TOOLS)}).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9091
    HTTPServer(("0.0.0.0", port), MCPHandler).serve_forever()
