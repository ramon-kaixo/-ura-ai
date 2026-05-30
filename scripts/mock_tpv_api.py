#!/usr/bin/env python3
"""Mock TPV API server for development and testing."""

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_FILE = Path("/tmp/ura_tpv_mock_data.json")

DEFAULT_DATA = {
    "ventas": [
        {
            "id": 1,
            "total": 25.50,
            "items": ["cerveza", "patatas"],
            "timestamp": datetime.now().isoformat(),
        },
        {
            "id": 2,
            "total": 42.00,
            "items": ["vino", "tortilla"],
            "timestamp": datetime.now().isoformat(),
        },
    ],
    "stock": {
        "cerveza": {"cantidad": 48, "umbral": 10},
        "vino": {"cantidad": 12, "umbral": 5},
        "patatas": {"cantidad": 20, "umbral": 5},
        "tortilla": {"cantidad": 3, "umbral": 5},
        "cafe": {"cantidad": 100, "umbral": 20},
    },
    "clientes_hoy": 42,
}


def _load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return DEFAULT_DATA


def _save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


@app.route("/api/ventas/diarias")
def ventas_diarias() -> object:
    data = _load_data()
    fecha = request.args.get("fecha", datetime.now().strftime("%Y-%m-%d"))
    total = sum(v["total"] for v in data["ventas"])
    return jsonify(
        {
            "fecha": fecha,
            "total": total,
            "num_ventas": len(data["ventas"]),
            "clientes": data["clientes_hoy"],
        }
    )


@app.route("/api/stock/<producto>")
def stock_producto(producto: str) -> object:
    data = _load_data()
    stock = data["stock"].get(producto, {"cantidad": 0, "umbral": 0})
    bajo = stock["cantidad"] < stock["umbral"]
    return jsonify(
        {
            "producto": producto,
            "cantidad": stock["cantidad"],
            "umbral": stock["umbral"],
            "bajo": bajo,
        }
    )


@app.route("/api/ventas/nueva", methods=["POST"])
def registrar_venta() -> object:
    data = _load_data()
    nueva = request.json or {}
    nueva["id"] = len(data["ventas"]) + 1
    nueva["timestamp"] = datetime.now().isoformat()
    data["ventas"].append(nueva)
    data["clientes_hoy"] += 1
    _save_data(data)
    return jsonify({"status": "ok", "id": nueva["id"]})


@app.route("/api/clientes/hoy")
def clientes_hoy() -> object:
    data = _load_data()
    return jsonify({"fecha": datetime.now().strftime("%Y-%m-%d"), "total": data["clientes_hoy"]})


@app.route("/api/health")
def health() -> object:
    return jsonify({"status": "ok", "service": "mock_tpv", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    print("   Mock TPV API iniciado en http://localhost:8080")
    app.run(host="0.0.0.0", port=8080)
