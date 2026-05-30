#!/usr/bin/env python3
"""registry_api.py — Registro central de agentes y dispositivos URA
API REST para que los agentes se registren y el Policia los supervise."""

import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DATA_FILE = Path(os.environ.get("REGISTRY_DATA", "/opt/ura/data/registry.json"))
HOST = os.environ.get("REGISTRY_HOST", "127.0.0.1")
PORT = int(os.environ.get("REGISTRY_PORT", "5100"))

DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def load():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


class RegistryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = load()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        try:
            entry = json.loads(body)
            data = load()
            entry["last_seen"] = datetime.now().isoformat()
            data.append(entry)
            save(data)
            self.send_response(201)
        except Exception as e:
            self.send_response(400)
            self.wfile.write(str(e).encode())
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silencioso


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), RegistryHandler)
    print(f"Registry API en http://{HOST}:{PORT}")
    server.serve_forever()
