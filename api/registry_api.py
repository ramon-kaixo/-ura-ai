"""Agente Registry API — Directorio central de agentes URA."""

import json
import os
from pathlib import Path
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth

app = Flask(__name__)
auth = HTTPTokenAuth(scheme="Bearer")


@auth.verify_token
def verify_token(token):
    return token == os.environ.get("URA_TOKEN", "")


app = Flask(__name__)
INVENTORY = Path(__file__).resolve().parent.parent / "config" / "network_inventory.json"


def load():
    if INVENTORY.exists():
        with open(INVENTORY) as f:
            data = json.load(f)
        if "agents" in data:
            return data
        if "inventory" in data:
            return {
                "agents": data["inventory"]
                if isinstance(data["inventory"], list)
                else list(data["inventory"].values())
            }
    return {"agents": []}


import fcntl

LOCK_FILE = "/tmp/ura_registry.lock"


def save(data):
    with open(LOCK_FILE, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
    existing = {}
    if INVENTORY.exists():
        with open(INVENTORY) as f:
            existing = json.load(f)
    existing["agents"] = data.get("agents", [])
    with open(INVENTORY, "w") as f:
        json.dump(existing, f, indent=2)
    # Backup automático
    backup_path = INVENTORY.with_suffix(".json.bak")
    with open(backup_path, "w") as f:
        json.dump(existing, f, indent=2)


@app.get("/agents")
@auth.login_required
def list_agents():
    return jsonify(load()["agents"])


@app.get("/agents/<agent_id>")
@auth.login_required
def get_agent(agent_id):
    for a in load()["agents"]:
        if a["id"] == agent_id:
            return jsonify(a)
    return jsonify({"error": "not found"}), 404


@app.post("/agents")
@auth.login_required
def register():
    data = request.json
    inv = load()
    for a in inv["agents"]:
        if a["id"] == data["id"]:
            return jsonify({"error": "ya existe"}), 409
    inv["agents"].append(data)
    save(inv)
    return jsonify({"status": "registrado"}), 201


@app.put("/agents/<agent_id>/heartbeat")
@auth.login_required
def heartbeat(agent_id):
    inv = load()
    for a in inv["agents"]:
        if a["id"] == agent_id:
            a["last_seen"] = request.json.get("timestamp", "")
            save(inv)
            return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


@app.post("/registry/heartbeat")
@auth.login_required
def registry_heartbeat():
    data = request.json or {}
    agent_id = data.get("agent") or "unknown"
    timestamp = data.get("timestamp") or ""
    if not agent_id or agent_id == "unknown":
        return jsonify({"error": "agent requerido"}), 400
    inv = load()
    for a in inv["agents"]:
        if a["id"] == agent_id:
            a["last_seen"] = timestamp
            save(inv)
            return jsonify({"status": "ok"}), 200
    inv["agents"].append(
        {
            "id": agent_id,
            "type": data.get("type", "?"),
            "ip": "127.0.0.1",
            "port": 0,
            "last_seen": timestamp,
        }
    )
    save(inv)
    return jsonify({"status": "registrado"}), 201


@app.get("/bibliotecario/consulta")
@auth.login_required
def consultar_bibliotecario():
    query = request.args.get("q", "")
    idx_path = (
        Path(__file__).resolve().parent.parent
        / "sandbox"
        / "Aprendizaje"
        / "Archivo"
        / "indice.json"
    )
    if not idx_path.exists():
        return jsonify({"resultados": [], "total": 0})
    with open(idx_path) as f:
        idx = json.load(f)
    resultados = [e for e in idx.get("entradas", []) if query.lower() in str(e).lower()]
    return jsonify({"resultados": resultados[:10], "total": len(resultados)})


if __name__ == "__main__":
    import requests as req
    import datetime

    try:
        req.post(
            "http://127.0.0.1:5100/agents",
            json={
                "id": "registry",
                "type": "infraestructura",
                "ip": "127.0.0.1",
                "port": 5100,
                "last_seen": datetime.datetime.utcnow().isoformat(),
            },
            timeout=3,
        )
    except Exception:
        pass
    app.run(host="127.0.0.1", port=5100)
