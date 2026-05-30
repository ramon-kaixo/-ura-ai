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
            if args.get("nivel") is not None:
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {args['nivel']}"], timeout=5
                )
                result = {"ok": True, "resultado": f"Volumen: {args['nivel']}"}
            else:
                r = subprocess.run(
                    ["osascript", "-e", "get volume settings"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                result = {"ok": True, "resultado": r.stdout.strip()}
        elif name == "abrir_app":
            subprocess.run(
                ["osascript", "-e", f'tell application "{args["nombre"]}" to activate'], timeout=10
            )
            result = {"ok": True, "resultado": f"{args['nombre']} abierto"}
        elif name == "cerrar_app":
            subprocess.run(
                ["osascript", "-e", f'tell application "{args["nombre"]}" to quit'], timeout=10
            )
            result = {"ok": True, "resultado": f"{args['nombre']} cerrado"}
        elif name == "sistema":
            r = subprocess.run(
                ["ssh", "ramon@10.164.1.99", "uptime && free -h | head -2"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result = {"ok": True, "resultado": r.stdout or r.stderr}
        elif name == "camaras":
            r = subprocess.run(
                ["curl", "-s", "http://10.164.1.99:1984/api/streams"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            streams = json.loads(r.stdout)
            result = {"ok": True, "resultado": f"{len(streams)} streams configurados"}
        elif name == "vision":
            img = "/tmp/ura_vision.png"
            subprocess.run(["screencapture", "-x", img], timeout=5)
            if os.path.exists(img):
                subprocess.run(["tesseract", img, "/tmp/ura_vision_out"], timeout=15)
                txt = ""
                if os.path.exists("/tmp/ura_vision_out.txt"):
                    with open("/tmp/ura_vision_out.txt") as f:
                        txt = f.read()[:1000]
                result = {"ok": True, "resultado": txt.strip() or "(pantalla sin texto)"}
                try:
                    os.unlink(img)
                except:
                    pass
            else:
                result = {"error": "No se pudo capturar pantalla"}
        elif name == "raton":
            accion = args.get("accion", "move")
            x, y = args.get("x", 0), args.get("y", 0)
            if accion == "click":
                subprocess.run(
                    ["osascript", "-e", f'tell app "System Events" to click at {{{x}, {y}}}'],
                    timeout=5,
                )
                result = {"ok": True, "resultado": f"Click en ({x},{y})"}
            elif accion == "posicion":
                r = subprocess.run(
                    ["osascript", "-e", 'tell app "System Events" to get position of mouse'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                result = {"ok": True, "resultado": r.stdout.strip()}
            else:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'tell app "System Events" to set position of mouse to {{{x}, {y}}}',
                    ],
                    timeout=5,
                )
                result = {"ok": True, "resultado": f"Raton en ({x},{y})"}
        elif name == "teclear":
            texto = args.get("texto", "").replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'tell app "System Events" to keystroke "{texto}"'], timeout=10
            )
            result = {"ok": True, "resultado": f"Texto: {texto[:50]}..."}
        elif name == "explorar":
            r1 = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            r2 = subprocess.run(
                ["ls", "-la", "/Applications/"], capture_output=True, text=True, timeout=5
            )
            procesos = len(
                [l for l in r1.stdout.splitlines() if "python" in l or "node" in l or "docker" in l]
            )
            apps = len([l for l in r2.stdout.splitlines() if ".app" in l])
            result = {
                "ok": True,
                "resultado": f"Procesos: {procesos} relevantes. Apps: ~{apps}. macOS.",
            }
    except Exception as e:
        result = {"error": str(e)}

    log_accion(name, args, result)
    return result


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
