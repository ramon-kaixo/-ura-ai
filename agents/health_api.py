#!/usr/bin/env python3
"""Health API — Endpoint JSON de salud para URA (puerto 5103)."""

import subprocess
from flask import Flask, jsonify
from pathlib import Path

app = Flask(__name__)
BASE = Path.home() / "URA" / "ura_ia_1972"


def check_url(url, timeout=5):
    import requests

    try:
        r = requests.get(url, timeout=timeout)
        return {"status": "ok", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_buzos():
    d = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"
    return {"activos": len(list(d.glob("hallazgos_*.json")))}


def check_disco():
    r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
    uso = r.stdout.splitlines()[-1].split()[4].replace("%", "")
    return {"uso_pct": int(uso)}


@app.route("/health")
def health():
    estado = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "status": "ok",
        "servicios": {
            "registry": check_url("http://127.0.0.1:5100/agents"),
            "dashboard": check_url("http://127.0.0.1:5101"),
            "searxng": check_url("http://178.105.81.83:8888"),
            "ollama": check_url("http://10.164.1.99:11434/api/tags"),
        },
        "buzos": check_buzos(),
        "disco": check_disco(),
    }
    for srv, data in estado["servicios"].items():
        if data.get("status") != "ok":
            estado["status"] = "degraded"
            break
    return jsonify(estado)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5103)
