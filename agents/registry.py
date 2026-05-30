"""Agente Registry API — Directorio central de agentes URA."""

import json
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)
INVENTORY = Path(__file__).resolve().parent.parent / "config" / "network_inventory.json"


def load():
    if INVENTORY.exists():
        with open(INVENTORY) as f:
            return json.load(f)
    return {"agents": [], "services": {}}


def save(data):
    with open(INVENTORY, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/agents")
def list_agents():
    return jsonify(load()["agents"])


@app.get("/agents/<agent_id>")
def get_agent(agent_id):
    for a in load()["agents"]:
        if a["id"] == agent_id:
            return jsonify(a)
    return jsonify({"error": "not found"}), 404


@app.post("/agents")
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
def heartbeat(agent_id):
    inv = load()
    for a in inv["agents"]:
        if a["id"] == agent_id:
            a["last_seen"] = request.json.get("timestamp", "")
            save(inv)
            return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100)
