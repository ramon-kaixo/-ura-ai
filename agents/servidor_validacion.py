#!/usr/bin/env python3
"""
Servidor web para validación DAM desde el móvil
"""

import json
import os
import sqlite3
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
DB_PATH = BASE_DIR / "board.db"
PORT = 8765

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>URA - Validación</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ background: white; border-radius: 20px; padding: 30px; width: 100%; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
        h1 {{ color: #2c3e50; text-align: center; margin-bottom: 20px; font-size: 24px; }}
        .token {{ background: #ecf0f1; padding: 15px; border-radius: 10px; text-align: center; font-family: monospace; font-size: 14px; color: #555; margin-bottom: 20px; word-break: break-all; }}
        .accion {{ font-size: 18px; font-weight: bold; color: {color}; text-align: center; margin-bottom: 10px; }}
        .descripcion {{ color: #7f8c8d; text-align: center; margin-bottom: 25px; }}
        .botones {{ display: flex; gap: 15px; }}
        button {{ flex: 1; padding: 20px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; transition: transform 0.2s; }}
        button:active {{ transform: scale(0.95); }}
        .aprobar {{ background: #27ae60; color: white; }}
        .denegar {{ background: #e74c3c; color: white; }}
        .mensaje {{ margin-top: 20px; padding: 15px; border-radius: 10px; text-align: center; }}
        .ok {{ background: #d4edda; color: #155724; }}
        .error {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Validación URA</h1>
        <div class="token">{token}</div>
        <div class="accion">{accion}</div>
        <div class="descripcion">{descripcion}</div>
        <div class="botones">
            <button class="denegar" onclick="responder('denegar')">❌ DENEGAR</button>
            <button class="aprobar" onclick="responder('aprobar')">✅ APROBAR</button>
        </div>
        <div id="mensaje"></div>
    </div>
    <script>
        function responder(respuesta) {{
            fetch('/validar?token={token}&respuesta=' + respuesta)
                .then(r => r.json())
                .then(d => {{
                    document.getElementById('mensaje').innerHTML =
                        '<div class="' + (d.success ? 'ok' : 'error') + '">' + d.mensaje + '</div>';
                    if(d.success) {{
                        document.querySelector('.botones').style.display = 'none';
                    }}
                }});
        }}
    </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/validar?"):
            query = urllib.parse.parse_qs(self.path.split("?")[1])
            token = query.get("token", [""])[0]
            respuesta = query.get("respuesta", [""])[0]

            self.enviar_respuesta(token, respuesta)
        else:
            self.mostrar_formulario()

    def mostrar_formulario(self):
        token = self.headers.get("token", "SIN-TOKEN")

        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        c.execute(
            "SELECT accion, descripcion, nivel FROM autorizaciones_dam WHERE token = ? AND estado = 'pendiente'",
            (token,),
        )
        row = c.fetchone()
        conn.close()

        if row:
            accion, descripcion, nivel = row
            color = "#e74c3c" if nivel == "OMEGA" else "#3498db"
            html = HTML_FORM.format(
                token=token, accion=accion, descripcion=descripcion[:50], color=color
            )
        else:
            html = HTML_FORM.format(
                token=token,
                accion="TOKEN NO ENCONTRADO",
                descripcion="Esta autorización ya fue procesada o no existe",
                color="#e74c3c",
            )

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def enviar_respuesta(self, token: str, respuesta: str):
        ahora = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()

        if respuesta == "aprobar":
            c.execute(
                "UPDATE autorizaciones_dam SET estado = 'aprobado', validado_por = 'movil', fecha_validacion = ? WHERE token = ?",
                (ahora, token),
            )
            mensaje = "✅ AUTORIZACIÓN APROBADA"
        else:
            c.execute(
                "UPDATE autorizaciones_dam SET estado = 'denegado', validado_por = 'movil', fecha_validacion = ? WHERE token = ?",
                (ahora, token),
            )
            mensaje = "❌ AUTORIZACIÓN DENEGADA"

        c.execute(
            "INSERT INTO eventos_seguridad_dam (evento, nivel, detalles, resultado, timestamp) VALUES (?, ?, ?, ?, ?)",
            ("VALIDACION_MOVIL", respuesta.upper(), token, respuesta.upper(), ahora),
        )

        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "mensaje": mensaje}).encode())


def obtener_url_validacion(token: str) -> str:
    import socket

    hostname = socket.gethostname()
    return f"http://{hostname}.local:8765/validar?token={token}"


def iniciar_servidor():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🌐 Servidor de validación: http://localhost:{PORT}")
    return server


if __name__ == "__main__":
    server = iniciar_servidor()
    server.serve_forever()
