#!/usr/bin/env python3
"""URA Dashboard — Panel unificado con salud en tiempo real."""

import os
import subprocess
from datetime import datetime, UTC
from flask import Flask, render_template_string, request
from flask_httpauth import HTTPTokenAuth
import requests

app = Flask(__name__)
auth = HTTPTokenAuth(scheme="Bearer")
REGISTRY_URL = "http://127.0.0.1:5100/agents"


@auth.verify_token
def verify_token(token):
    return token == os.environ.get("URA_TOKEN", "")


def get_ura_agents():
    try:
        r = requests.get(REGISTRY_URL, timeout=3)
        return r.json() if r.ok else []
    except:
        return []


def get_system_programs():
    apps = []
    for base in ["/Applications", os.path.expanduser("~/Applications")]:
        if os.path.exists(base):
            for item in os.listdir(base):
                if item.endswith(".app"):
                    apps.append(
                        {"name": item.replace(".app", ""), "path": os.path.join(base, item)}
                    )
    return sorted(apps, key=lambda x: x["name"])


def get_health_status(agents):
    ahora = datetime.now(UTC)
    online, offline = [], []
    for a in agents:
        last = a.get("last_seen", "")
        if last:
            try:
                if (ahora - datetime.fromisoformat(last)).total_seconds() < 120:
                    online.append(a)
                    continue
            except:
                pass
        offline.append(a)
    return online, offline


TEMPLATE = """<!DOCTYPE html><html><head><title>URA Dashboard</title>
<style>body{font-family:system-ui;margin:20px;background:#1e1e1e;color:#ddd}input,select,button{padding:10px;margin:5px}input{width:300px}table{border-collapse:collapse;width:100%;margin-bottom:20px}th,td{padding:8px;text-align:left;border-bottom:1px solid #444}th{background:#333}pre{background:#222;padding:10px}.online{color:#4caf50}.offline{color:#f44336}.section{margin-top:30px}</style></head>
<body><h2>🔍 Panel de Control URA</h2>
<input type="text" id="search" placeholder="Buscar agente, programa o pantalla..." onkeyup="filter()">
<div class="section"><h3>❤️ Salud del Sistema</h3>
<table><tr><th>Estado</th><th>ID</th><th>Tipo</th><th>IP</th><th>Último latido</th></tr>
{% for a in online %}<tr><td class="online">🟢 Online</td><td>{{ a.id }}</td><td>{{ a.get('type','?') }}</td><td>{{ a.get('ip','?') }}</td><td>{{ a.get('last_seen','?') }}</td></tr>{% endfor %}
{% for a in offline %}<tr><td class="offline">🔴 Offline</td><td>{{ a.id }}</td><td>{{ a.get('type','?') }}</td><td>{{ a.get('ip','?') }}</td><td>{{ a.get('last_seen','?') }}</td></tr>{% endfor %}</table></div>
<div class="section"><h3>🤖 Agentes URA</h3>
<table id="agents"><tr><th>ID</th><th>Tipo</th><th>IP</th><th>Puerto</th><th>Último latido</th></tr>
{% for a in agents %}<tr><td>{{ a.id }}</td><td>{{ a.get('type','?') }}</td><td>{{ a.get('ip','?') }}</td><td>{{ a.get('port','?') }}</td><td>{{ a.get('last_seen','?') }}</td></tr>{% endfor %}</table></div>
<div class="section"><h3>📷 Cámaras</h3>
<table id="camaras"><tr><th>ID</th><th>IP</th><th>Puerto</th><th>Último latido</th></tr>
{% for c in camaras %}<tr><td>{{ c.id }}</td><td>{{ c.get('ip','?') }}</td><td>{{ c.get('port','?') }}</td><td>{{ c.get('last_seen','?') }}</td></tr>{% else %}<tr><td colspan="4">Sin cámaras registradas</td></tr>{% endfor %}</table></div>
<div class="section"><h3>💻 Programas del sistema</h3>
<table id="programs"><tr><th>Nombre</th><th>Ruta</th></tr>
{% for p in programs %}<tr><td>{{ p.name }}</td><td>{{ p.path }}</td></tr>{% endfor %}</table></div>
<div class="section"><h3>🚚 Transportador</h3>
<form action="/transport" method="post">
<input name="item_id" placeholder="ID del elemento" required>
<input name="destination" placeholder="Ruta destino" required>
<select name="action"><option value="copy">Copiar</option><option value="move">Mover</option><option value="send">Enviar vía SCP</option></select>
<button type="submit">Ejecutar</button></form></div>
<script>function filter(){let q=document.getElementById("search").value.toLowerCase();document.querySelectorAll("table tr").forEach(r=>{r.style.display=r.innerText.toLowerCase().includes(q)?"":"none"})}</script></body></html>"""


@app.route("/")
@auth.login_required
def index():
    agents = get_ura_agents()
    online, offline = get_health_status(agents)
    camaras = [a for a in agents if a.get("type") == "camara"]
    return render_template_string(
        TEMPLATE,
        agents=agents,
        online=online,
        offline=offline,
        camaras=camaras,
        programs=get_system_programs(),
    )


@app.route("/transport", methods=["POST"])
@auth.login_required
def transport():
    item_id = request.form["item_id"]
    dest = request.form["destination"]
    action = request.form["action"]
    r = subprocess.run(
        ["python3", "scripts/ura_transporter.py", f"--{action}", item_id, "--to", dest],
        capture_output=True,
        text=True,
    )
    return f"<pre>{r.stdout}{r.stderr}</pre>"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5101)
