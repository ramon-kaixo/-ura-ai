#!/usr/bin/env python3
"""Mini API Bridge: conecta el chat HTML con los agentes URA."""

import sys
import os
import json
import asyncio
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

# Fix: ensure BaseHTTPRequestHandler is accessible
sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")
os.chdir("/Users/ramonesnaola/URA/ura_ia_1972")

from core.central_router import CentralRouter
import requests

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://gx10-ts:11434")
router = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._cors()

    def do_GET(self):
        self._cors()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/chat":
            self._handle_chat(data)
        elif self.path == "/agent":
            self._handle_agent(data)
        elif self.path == "/api/probar_sugerencia":
            self._handle_probar_sugerencia(data)
        else:
            self._cors()
            self.wfile.write(b"{}")

    def _respond(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_chat(self, data):
        """Primero intenta el agente, si no hay resultado útil → Ollama."""
        msg = data.get("message", "")
        model = data.get("model", "qwen2.5:7b")

        # Intentar agente primero
        try:
            result = asyncio.run(router.process_request(msg))
            agent_response = result.get("response", "") if isinstance(result, dict) else str(result)
            if (
                agent_response
                and "Error ejecutando agente" not in agent_response
                and "Error cargando" not in agent_response
                and "No module named" not in agent_response
            ):
                self._respond(
                    {"response": agent_response, "source": f"agent:{intent}", "model": "ura-agents"}
                )
                return
        except Exception:
            pass

        # Fallback a Ollama con chat API (system message)
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Eres URA, el asistente inteligente del sistema URA. Controlas una flota de dispositivos: camaras Dahua (15), ASUS GX10 (servidor), Mac Mini M4 (supervisor), y multiples agentes en la red Tailscale. Responde siempre en español de forma natural y conversacional. Tu nombre es URA, no Qwen ni Alibaba. Presumes de tus capacidades pero eres humilde.",
                        },
                        {"role": "user", "content": msg},
                    ],
                    "stream": False,
                    "options": {"num_predict": 1024},
                },
                timeout=120,
            )
            ollama_resp = r.json().get("message", {}).get("content", "").strip()
            if not ollama_resp:
                ollama_resp = r.json().get("response", "").strip()
            self._respond({"response": ollama_resp, "source": "ollama", "model": model})
        except Exception as e:
            self._respond({"response": f"Error: {str(e)}", "source": "error"})

    def _handle_agent(self, data):
        """Solo agente, sin fallback."""
        msg = data.get("message", "")
        try:
            result = asyncio.run(router.process_request(msg))
            self._respond(
                {
                    "response": (
                        result.get("response", "") if isinstance(result, dict) else str(result)
                    ),
                    "source": "agent",
                    "intent": result.get("intent", "?") if isinstance(result, dict) else "?",
                }
            )
        except Exception as e:
            self._respond({"response": str(e), "source": "error"})

    def _handle_probar_sugerencia(self, data):
        idx = data.get("idx", 0)
        script = os.path.join(os.path.dirname(__file__), "scripts", "probar_sugerencia.py")
        subprocess.Popen([sys.executable, script, str(idx)])
        self._respond({"status": "probando", "idx": idx})


if __name__ == "__main__":
    router = CentralRouter()
    port = 5052
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"🚀 URA Agent Bridge → http://127.0.0.1:{port}")
    server.serve_forever()
