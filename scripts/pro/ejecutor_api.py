#!/usr/bin/env python3
"""ejecutor_api.py — Puerto 4096. Endpoint remoto URA."""
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")
from cli.gatekeeper import registrar_skill_propuesto
from core.open_claw_reporte import generar_reporte

HOST = "127.0.0.1"; PORT = 4096

class H(BaseHTTPRequestHandler):
    def do_POST(s):
        l = int(s.headers.get("Content-Length", 0)); b = json.loads(s.rfile.read(l)) if l else {}
        if s.path == "/skill/proponer":
            nom = b.get("nombre", ""); cod = b.get("codigo", "")
            r = {"error": "nombre y codigo requeridos"} if not nom or not cod else registrar_skill_propuesto(nom, cod)
        elif s.path == "/reporte":
            r = generar_reporte()
        else:
            r = {"error": "not found"}
        s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers()
        s.wfile.write(json.dumps(r).encode())
    def do_GET(s):
        s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers()
        s.wfile.write(json.dumps({"servicio": "URA Executor", "puerto": PORT}).encode())
    def log_message(s, *a): pass

if __name__ == "__main__":
    HTTPServer((HOST, PORT), H).serve_forever()
