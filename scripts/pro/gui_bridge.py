#!/usr/bin/env python3
"""gui_bridge.py — Puente HTTP persistente para GUI Agent en GX10.

Mantiene una sesión MCP abierta dentro del contenedor Docker para que
múltiples llamadas HTTP compartan el mismo navegador (estado persistente).

Puerto: 4097
Endpoints:
    GET  /                     — Info del servicio
    GET  /health               — Health check
    POST /api/gui/<tool>       — Ejecutar herramienta del GUI Agent

Uso desde request_manager.py (Hetzner):
    POST /api/gui/navigate  {"url": "https://behance.net/..."}
    POST /api/gui/screenshot {}
"""

import json
import logging
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("gui_bridge")

HOST = "0.0.0.0"
PORT = 4097

CONTAINER = os.environ.get("URA_GUI_CONTAINER", "ura-gui-agent")
MCP_CMD = ["docker", "exec", "-i", CONTAINER, "python3", "-u", "/app/mcp_server.py"]

AVAILABLE_TOOLS = {
    "navigate": {
        "params": {"url": {"type": "string", "required": True}},
        "description": "Navegar a una URL con Anti-Detection",
    },
    "screenshot": {
        "params": {},
        "description": "Capturar screenshot (base64 JPEG)",
    },
    "click": {
        "params": {"x": {"type": "number", "required": True}, "y": {"type": "number", "required": True}},
        "description": "Clic en coordenadas (x, y)",
    },
    "type": {
        "params": {"text": {"type": "string", "required": True}, "selector": {"type": "string", "required": False}},
        "description": "Escribir texto (opcionalmente en un selector)",
    },
    "scroll": {
        "params": {"delta_y": {"type": "number", "required": False}},
        "description": "Scroll vertical",
    },
    "wait": {
        "params": {"ms": {"type": "number", "required": False}},
        "description": "Esperar milisegundos",
    },
    "analyze": {
        "params": {"prompt": {"type": "string", "required": False}},
        "description": "Analizar pantalla con modelo de visión (Ollama GPU)",
    },
    "done": {
        "params": {},
        "description": "Liberar recursos del navegador",
    },
}


class MCPSession:
    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._msg_id = 0

    def start(self) -> bool:
        if self._proc and self._proc.poll() is None:
            return True
        try:
            self._proc = subprocess.Popen(
                MCP_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
            )
        except FileNotFoundError:
            log.error("Container '%s' not found", CONTAINER)
            return False
        except Exception as e:
            log.error("Error starting MCP: %s", e)
            return False
        init_result = self.call("initialize", {})
        if "error" in init_result:
            log.error("MCP init failed: %s", init_result["error"])
            self.stop()
            return False
        log.info("MCP session started (PID=%d)", self._proc.pid)
        return True

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try: self.call("shutdown", {})
            except Exception: pass
            try: self._proc.stdin.close()
            except Exception: pass
            try: self._proc.terminate(); self._proc.wait(timeout=5)
            except Exception: self._proc.kill()
        self._proc = None

    def call(self, method: str, params: dict) -> dict:
        if not self._proc or self._proc.poll() is not None:
            if not self.start():
                return {"error": "MCP session not available"}
        with self._lock:
            self._msg_id += 1
            payload = {"jsonrpc": "2.0", "id": self._msg_id, "method": method}
            if method == "tools/call":
                payload["params"] = params
            try:
                self._proc.stdin.write(json.dumps(payload) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                if not line:
                    return {"error": "MCP process closed stdout"}
                resp = json.loads(line.strip())
            except (BrokenPipeError, OSError) as e:
                log.error("MCP pipe broken: %s", e)
                self._proc = None
                return {"error": f"MCP connection lost: {e}"}
            except json.JSONDecodeError as e:
                log.error("MCP invalid JSON: %s", e)
                return {"error": f"Invalid MCP response: {e}"}
            except Exception as e:
                return {"error": str(e)}
            if "error" in resp:
                return {"error": resp["error"].get("message", str(resp["error"]))}
            if "result" in resp:
                return resp["result"]
            return {"error": "Unknown MCP response", "raw": str(resp)}

    def call_tool(self, tool: str, args: dict) -> dict:
        return self.call("tools/call", {"name": f"gui_{tool}", "arguments": args})


_mcp = MCPSession()


class BridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, TypeError):
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self._send_json({
                "service": "URA GUI Bridge - GX10",
                "status": "running",
                "session_alive": _mcp._proc is not None and _mcp._proc.poll() is None,
                "tools": list(AVAILABLE_TOOLS.keys()),
            })
        elif self.path == "/health":
            self._send_json({
                "status": "ok",
                "container": CONTAINER,
                "session_alive": _mcp._proc is not None and _mcp._proc.poll() is None,
            })
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/api/gui/"):
            self._send_json({"error": "Use /api/gui/<tool>"}, 404)
            return
        tool_name = self.path.removeprefix("/api/gui/")
        if tool_name not in AVAILABLE_TOOLS:
            self._send_json({
                "error": f"Unknown tool: {tool_name}",
                "available": list(AVAILABLE_TOOLS.keys()),
            }, 400)
            return
        body = self._read_body()
        log.info("Calling tool=%s", tool_name)
        if tool_name == "html":
            url = body.get("url", "")
            if not url:
                self._send_json({"error": "url required"}, 400)
                return
            import subprocess
            import json as _json
            script = _json.dumps("import asyncio; from playwright.async_api import async_playwright; import sys; async def main(): async with async_playwright() as p: b=await p.chromium.launch(headless=True); page=await b.new_page(); await page.goto(sys.argv[1], wait_until='domcontentloaded', timeout=30000); html=await page.content(); await b.close(); print(html); asyncio.run(main())")
            try:
                result = subprocess.run(["docker", "exec", "-i", CONTAINER, "python3", "-c", script, url], capture_output=True, text=True, timeout=35)
                if result.returncode == 0:
                    self._send_json({"result": {"html": result.stdout, "length": len(result.stdout)}})
                else:
                    self._send_json({"error": result.stderr[:500]}, 502)
            except subprocess.TimeoutExpired:
                self._send_json({"error": "Timeout"}, 502)
            except Exception as e:
                self._send_json({"error": str(e)}, 502)
            return
        result = _mcp.call_tool(tool_name, body)
        if "error" in result:
            self._send_json({"error": result["error"]}, 502)
        else:
            self._send_json({"result": result})

    def log_message(self, format, *args):
        log.info("HTTP %s", format % args)


def main():
    log.info("GUI Bridge on %s:%d, container=%s", HOST, PORT, CONTAINER)
    check = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=5,
    )
    if CONTAINER not in check.stdout:
        log.warning("Container '%s' NOT running!", CONTAINER)
    if _mcp.start():
        log.info("Browser ready.")
    assert_port_free(HOST, PORT, "gui-bridge")
    server = HTTPServer((HOST, PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _mcp.stop()
        server.server_close()


if __name__ == "__main__":
    main()
