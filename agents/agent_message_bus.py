#!/usr/bin/env python3
"""agent_message_bus.py — Bus de comunicacion para la flota URA
Flask + SQLite. Todos los agentes se registran y comunican a traves de el.
Corre en el GX10 (puerto 8091) o en cualquier maquina de la flota."""

import json
import os
import sqlite3
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DB = Path(os.environ.get("BUS_DB", "/opt/ura/data/agent_bus.db"))
HOST = os.environ.get("BUS_HOST", "0.0.0.0")
PORT = int(os.environ.get("BUS_PORT", "8091"))
DB.parent.mkdir(parents=True, exist_ok=True)


def init_db():
    with sqlite3.connect(str(DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT, recipient TEXT, topic TEXT,
                payload TEXT, priority TEXT DEFAULT 'normal',
                timestamp TEXT, read INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY, hostname TEXT, role TEXT,
                ip TEXT, last_heartbeat TEXT
            )
        """)
        conn.commit()


init_db()


class BusHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        try:
            data = json.loads(body)
        except:
            self._send(400, {"error": "invalid json"})
            return

        if self.path == "/send":
            with sqlite3.connect(str(DB)) as conn:
                conn.execute(
                    "INSERT INTO messages (sender, recipient, topic, payload, priority, timestamp) VALUES (?,?,?,?,?,?)",
                    (
                        data["sender"],
                        data.get("recipient", "broadcast"),
                        data.get("topic", "general"),
                        data["payload"],
                        data.get("priority", "normal"),
                        datetime.now(UTC).isoformat(),
                    ),
                )
                conn.commit()
            self._send(200, {"status": "sent"})

        elif self.path == "/heartbeat":
            with sqlite3.connect(str(DB)) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO agents (id, hostname, role, ip, last_heartbeat) VALUES (?,?,?,?,?)",
                    (
                        data["id"],
                        data.get("hostname", ""),
                        data.get("role", ""),
                        data.get("ip", ""),
                        datetime.now(UTC).isoformat(),
                    ),
                )
                conn.commit()
            self._send(200, {"status": "ok"})

        else:
            self._send(404, {"error": "not found"})

    def do_GET(self):
        with sqlite3.connect(str(DB)) as conn:
            if self.path == "/agents":
                rows = conn.execute("SELECT * FROM agents").fetchall()
                self._send(
                    200,
                    [
                        {
                            "id": r[0],
                            "hostname": r[1],
                            "role": r[2],
                            "ip": r[3],
                            "last_heartbeat": r[4],
                        }
                        for r in rows
                    ],
                )

            elif self.path.startswith("/inbox/"):
                agent_id = self.path.split("/inbox/")[1]
                msgs = conn.execute(
                    "SELECT * FROM messages WHERE recipient IN (?, 'broadcast') AND read=0 ORDER BY timestamp DESC LIMIT 20",
                    (agent_id,),
                ).fetchall()
                conn.execute("UPDATE messages SET read=1 WHERE recipient=? AND read=0", (agent_id,))
                conn.commit()
                self._send(
                    200,
                    [
                        {
                            "id": m[0],
                            "sender": m[1],
                            "topic": m[3],
                            "payload": m[4],
                            "timestamp": m[6],
                        }
                        for m in msgs
                    ],
                )

            else:
                self._send(
                    200,
                    {
                        "status": "ok",
                        "bus": "agent_message_bus",
                        "agents": conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
                    },
                )

    def do_OPTIONS(self):
        self._send(200, {})

    def _send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), BusHandler)
    print(f"Agent Message Bus en http://{HOST}:{PORT}")
    server.serve_forever()
