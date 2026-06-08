#!/usr/bin/env python3
"""ejecutor_api.py — Puerto 4096. Endpoint remoto URA."""
import json, os, subprocess, sys, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.gatekeeper import registrar_skill_propuesto

CONTEXT_PATH = os.path.expanduser("~/.config/opencode/ura_context.json")
MCP_SYNC = "http://10.164.1.26:9093"
HOST = "127.0.0.1"; PORT = 4096

def log_evento(e, d=None):
    import urllib.request
    p = {"evento": e, "timestamp": datetime.utcnow().isoformat(), "data": d or {}}
    try:
        urllib.request.urlopen(urllib.request.Request(f"{MCP_SYNC}/log", data=json.dumps(p).encode(), headers={"Content-Type": "application/json"}, method="POST"), timeout=5)
    except: pass

def ctx_r():
    if os.path.exists(CONTEXT_PATH):
        with open(CONTEXT_PATH) as f: return json.load(f)
    return {}

def ctx_w(c):
    os.makedirs(os.path.dirname(CONTEXT_PATH), exist_ok=True)
    with open(CONTEXT_PATH, "w") as f: json.dump(c, f, indent=2)

class H(BaseHTTPRequestHandler):
    def do_POST(s):
        l = int(s.headers.get("Content-Length", 0)); b = json.loads(s.rfile.read(l)) if l else {}
        if s.path == "/skill/proponer":
            nom = b.get("nombre", ""); cod = b.get("codigo", "")
            r = {"error": "nombre y codigo requeridos"} if not nom or not cod else registrar_skill_propuesto(nom, cod)
        else:
            r = {"error": "not found"}
        s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers()
        s.wfile.write(json.dumps(r).encode())
    def do_GET(s):
        s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers()
        s.wfile.write(json.dumps({"servicio": "URA Executor", "puerto": PORT}).encode())
    def log_message(s, *a): pass

if __name__ == "__main__":
    log_evento("inicio", {"puerto": PORT})
    HTTPServer((HOST, PORT), H).serve_forever()
