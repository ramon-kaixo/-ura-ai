#!/usr/bin/env python3
"""gui_bridge.py — HTTP bridge for GUI Agent with persistent MCP session."""
import json, logging, os, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("gui_bridge")

HOST, PORT = "0.0.0.0", 4097
CONTAINER = os.environ.get("URA_GUI_CONTAINER", "ura-gui-agent")
MCP_CMD = ["docker", "exec", "-i", CONTAINER, "python3", "-u", "/app/mcp_server.py"]

TOOLS = ["navigate", "screenshot", "click", "type", "scroll", "wait", "analyze", "done"]

class MCPSession:
    def __init__(self):
        self._proc = None; self._lock = threading.Lock(); self._mid = 0
    def start(self) -> bool:
        if self._proc and self._proc.poll() is None: return True
        try:
            self._proc = subprocess.Popen(MCP_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        except Exception as e:
            log.error("Start fail: %s", e); return False
        r = self.call("initialize", {})
        if "error" in r: self.stop(); return False
        log.info("MCP ready PID=%d", self._proc.pid); return True
    def stop(self):
        if self._proc and self._proc.poll() is None:
            try: self.call("shutdown", {})
            except: pass
            try: self._proc.stdin.close(); self._proc.terminate(); self._proc.wait(5)
            except: self._proc.kill()
        self._proc = None
    def call(self, method: str, params: Optional[dict] = None) -> dict:
        if not self._proc or self._proc.poll() is not None:
            if not self.start(): return {"error": "no session"}
        with self._lock:
            self._mid += 1
            p = {"jsonrpc": "2.0", "id": self._mid, "method": method}
            if params: p["params"] = params
            try:
                self._proc.stdin.write(json.dumps(p) + "\n"); self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                if not line: return {"error": "stdout closed"}
                resp = json.loads(line.strip())
            except Exception as e:
                self._proc = None; return {"error": str(e)}
            if "error" in resp: return {"error": resp["error"].get("message", str(resp["error"]))}
            if "result" in resp: return resp["result"]
            return {"error": "unknown response"}
    def call_tool(self, tool: str, args: dict) -> dict:
        return self.call("tools/call", {"name": f"gui_{tool}", "arguments": args})

mcp = MCPSession()

class Handler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if not n: return {}
        try: return json.loads(self.rfile.read(n))
        except: return {}
    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers()
    def do_GET(self):
        if self.path == "/": self._json({"service":"URA GUI Bridge","tools":TOOLS,"session_alive":mcp._proc is not None and mcp._proc.poll() is None})
        elif self.path == "/health": self._json({"status":"ok","session_alive":mcp._proc is not None and mcp._proc.poll() is None})
        else: self._json({"error":"not found"}, 404)
    def do_POST(self):
        if not self.path.startswith("/api/gui/"): self._json({"error":"use /api/gui/<tool>"}, 404); return
        tool = self.path.split("/")[-1]
        if tool not in TOOLS: self._json({"error":f"unknown tool: {tool}","available":TOOLS}, 400); return
        body = self._body(); log.info("tool=%s", tool)
        r = mcp.call_tool(tool, body)
        if "error" in r: self._json({"error": r["error"]}, 502)
        else: self._json({"result": r})

def main():
    log.info("Bridge :%d container=%s", PORT, CONTAINER)
    ck = subprocess.run(["docker","ps","--filter",f"name={CONTAINER}","--format","{{.Names}}"], capture_output=True, text=True, timeout=5)
    if CONTAINER not in ck.stdout: log.warning("Container %s NOT running!", CONTAINER)
    if mcp.start(): log.info("Browser ready")
    try: HTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt: mcp.stop()

if __name__ == "__main__": main()
