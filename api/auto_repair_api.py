#!/usr/bin/env python3
"""
api/auto_repair_api.py - API REST para Sistema de Auto-Reparación
Endpoint HTTP para reparaciones remotas
"""

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.error_auto_repair import ErrorAutoRepair
from core.port_manager import get_port_manager

app = Flask(__name__)
repair_system = ErrorAutoRepair()
port_manager = get_port_manager()


@app.route("/api/auto-repair/health", methods=["GET"])
def health_check():
    """Endpoint de health check"""
    return jsonify(
        {
            "status": "healthy",
            "service": "ura-auto-repair-api",
            "ml_available": repair_system.ml_model is not None,
            "port": port_manager.get_port_for_service("ura_api_auto_repair"),
        }
    )


@app.route("/api/auto-repair/predict", methods=["GET"])
def predict_errors():
    """Predecir errores probables"""
    try:
        predicted = repair_system.predict_errors()
        return jsonify({"success": True, "predicted_errors": predicted, "count": len(predicted)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/repair", methods=["POST"])
def attempt_repair():
    """Intentar reparar un error"""
    try:
        data = request.json
        error_type = data.get("error_type")
        error_message = data.get("error_message")
        timeout = data.get("timeout", 60)

        if not error_type or not error_message:
            return (
                jsonify({"success": False, "error": "error_type y error_message son requeridos"}),
                400,
            )

        success, message = repair_system.attempt_repair(error_type, error_message, timeout)

        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/history", methods=["GET"])
def get_history():
    """Obtener historial de reparaciones"""
    try:
        history = repair_system.get_repair_history()
        return jsonify({"success": True, "history": history, "count": len(history)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/recurrent", methods=["GET"])
def get_recurrent_errors():
    """Obtener errores recurrentes"""
    try:
        recurrent = repair_system.get_recurrent_errors()
        return jsonify({"success": True, "recurrent_errors": recurrent})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/preventive", methods=["POST"])
def run_preventive_checks():
    """Ejecutar verificaciones preventivas"""
    try:
        issues = repair_system.run_preventive_checks()
        return jsonify({"success": True, "issues_found": issues, "count": len(issues)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/train-ml", methods=["POST"])
def train_ml_model():
    """Entrenar modelo ML"""
    try:
        success = repair_system.train_ml_model()
        return jsonify(
            {
                "success": success,
                "message": (
                    "Modelo entrenado exitosamente" if success else "Error entrenando modelo"
                ),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auto-repair/recommendations", methods=["GET"])
def get_recommendations():
    """Obtener recomendaciones de reparaciones"""
    try:
        recommendations = repair_system.get_repair_recommendations()
        return jsonify({"success": True, "recommendations": recommendations})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = port_manager.get_port_for_service("ura_api_auto_repair")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=port,
    )
