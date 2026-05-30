#!/usr/bin/env python3
"""Federated learning server — aggregates experiences from multiple bars."""

import json
import logging
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request

logger = logging.getLogger("FederatedServer")

EXPERIENCES_DIR = Path(os.getenv("URA_FEDERATED_DIR", "/tmp/ura_federated"))
EXPERIENCES_DIR.mkdir(parents=True, exist_ok=True)

WEIGHTS_FILE = Path(os.getenv("URA_WEIGHTS_FILE", "/tmp/ura_global_weights.json"))

app = Flask(__name__)


@app.route("/upload", methods=["POST"])
def upload() -> object:
    """Receives experiences from a bar client.

    Returns:
        JSON response with status.
    """
    data = request.json
    bar_id = data.get("bar_id", "unknown")
    experiencias = data.get("experiencias", [])
    timestamp = int(time.time())
    filepath = EXPERIENCES_DIR / f"{bar_id}_{timestamp}.json"
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(experiencias, fh, indent=2)
    logger.info("Recibidas %d experiencias de %s", len(experiencias), bar_id)
    return jsonify({"status": "ok", "count": len(experiencias)})


@app.route("/model", methods=["GET"])
def get_model() -> object:
    """Returns the current global model weights.

    Returns:
        JSON response with model weights.
    """
    if WEIGHTS_FILE.exists():
        with open(WEIGHTS_FILE, encoding="utf-8") as fh:
            weights = json.load(fh)
        return jsonify(weights)
    return jsonify({"weights": {}, "version": 0})


@app.route("/aggregate", methods=["POST"])
def aggregate() -> object:
    """Aggregates experiences from all bars and updates global weights.

    Returns:
        JSON response with aggregation status.
    """
    all_experiences = []
    for filepath in EXPERIENCES_DIR.glob("*.json"):
        with open(filepath, encoding="utf-8") as fh:
            all_experiences.extend(json.load(fh))

    weights: dict = {}
    for exp in all_experiences:
        doc = exp.get("document", "")
        meta = exp.get("metadata", {})
        key = meta.get("tarea", doc[:50])
        if key not in weights:
            weights[key] = {"count": 0, "success": 0}
        weights[key]["count"] += 1
        if meta.get("reward", 0) > 0.5:
            weights[key]["success"] += 1

    with open(WEIGHTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(weights, fh, indent=2)

    logger.info(
        "Agregacion completada: %d experiencias, %d reglas", len(all_experiences), len(weights)
    )
    return jsonify({"status": "ok", "rules": len(weights)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=8080)
