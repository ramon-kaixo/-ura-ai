#!/usr/bin/env python3
"""
web/auto_repair_dashboard.py - Dashboard Web para Sistema de Auto-Reparación
Interfaz web Flask para visualizar reparaciones
"""

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.error_auto_repair import ErrorAutoRepair
from core.port_manager import get_port_manager

app = Flask(__name__)
repair_system = ErrorAutoRepair()
port_manager = get_port_manager()


@app.route("/")
def dashboard():
    """Página principal del dashboard"""
    return render_template("auto_repair_dashboard.html")


@app.route("/api/stats")
def get_stats():
    """Obtener estadísticas del sistema"""
    history = repair_system.get_repair_history()

    total = len(history)
    success = sum(1 for entry in history if entry.get("success", False))
    failure = total - success
    success_rate = (success / total * 100) if total > 0 else 0

    recurrent = repair_system.get_recurrent_errors()
    predicted = repair_system.predict_errors()

    return jsonify(
        {
            "total_repairs": total,
            "successful_repairs": success,
            "failed_repairs": failure,
            "success_rate": round(success_rate, 1),
            "recurrent_errors": recurrent,
            "predicted_errors": predicted,
            "ml_available": repair_system.ml_model is not None,
            "simulation_mode": repair_system.simulation_mode,
        }
    )


@app.route("/api/history")
def get_history():
    """Obtener historial de reparaciones"""
    history = repair_system.get_repair_history()

    # Ordenar por timestamp descendente
    history = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)

    return jsonify({"history": history, "count": len(history)})


@app.route("/api/predict", methods=["POST"])
def predict():
    """Predecir errores probables"""
    predicted = repair_system.predict_errors()

    return jsonify({"success": True, "predicted_errors": predicted, "count": len(predicted)})


@app.route("/api/repair", methods=["POST"])
def repair():
    """Intentar reparar un error"""
    data = request.json
    error_type = data.get("error_type")
    error_message = data.get("error_message")
    timeout = data.get("timeout", 60)

    success, message = repair_system.attempt_repair(error_type, error_message, timeout)

    return jsonify({"success": success, "message": message})


@app.route("/api/preventive", methods=["POST"])
def preventive():
    """Ejecutar verificaciones preventivas"""
    issues = repair_system.run_preventive_checks()

    return jsonify({"success": True, "issues_found": issues, "count": len(issues)})


@app.route("/api/train-ml", methods=["POST"])
def train_ml():
    """Entrenar modelo ML"""
    success = repair_system.train_ml_model()

    return jsonify(
        {
            "success": success,
            "message": "Modelo entrenado exitosamente" if success else "Error entrenando modelo",
        }
    )


@app.route("/api/generate-pdf", methods=["POST"])
def generate_pdf():
    """Generar reporte PDF"""
    pdf_path = repair_system.generate_pdf_report()

    return jsonify({"success": bool(pdf_path), "path": pdf_path})


@app.route("/api/toggle-simulation", methods=["POST"])
def toggle_simulation():
    """Alternar modo de simulación"""
    repair_system.simulation_mode = not repair_system.simulation_mode

    return jsonify({"success": True, "simulation_mode": repair_system.simulation_mode})


if __name__ == "__main__":
    port = port_manager.get_port_for_service("ura_dashboard_web")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=port,
    )
