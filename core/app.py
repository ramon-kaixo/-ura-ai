#!/usr/bin/env python3
"""
URA API REST - API unificada
API REST para interactuar con todos los componentes del sistema
"""

import os
from datetime import datetime, UTC

from core.coordinador_verificacion import coordinador_verificacion
from core.database import db_manager
from core.scheduler_buscadores import scheduler_buscadores
from core.tecnico_ejecutor import tecnico_ejecutor
from core.tecnico_supervisor import tecnico_supervisor
from core.test_forzado import test_forzado
from flask import Flask, jsonify, request

from core.buscadores.buscador_documentacion import buscador_documentacion

api = Flask(__name__)


@api.route("/api/verificar", methods=["POST"])
def verificar():
    """Verificar respuesta con Técnico Supervisor"""
    data = request.json
    resultado = tecnico_supervisor.verificar_respuesta(
        respuesta_ura=data.get("respuesta_ura"), peticion=data.get("peticion")
    )
    # Guardar en DB
    db_manager.save_verificacion_supervisor(
        peticion=data.get("peticion"),
        respuesta_ura=data.get("respuesta_ura"),
        fuentes=resultado["respuestas_fuentes"],
        coincidencia=resultado["coincidencia"],
        aprobada=resultado["aprobada"],
    )
    return jsonify(resultado)


@api.route("/api/ejecutar", methods=["POST"])
def ejecutar():
    """Ejecutar orden con Técnico Ejecutor"""
    data = request.json
    resultado = tecnico_ejecutor.ejecutar_orden(
        orden=data.get("orden"), ura_response=data.get("ura_response")
    )
    # Guardar en DB
    db_manager.save_ejecucion_ejecutor(
        orden=data.get("orden"),
        ura_response=data.get("ura_response"),
        rechazo=resultado.get("rechazo", False),
        ejecutada=resultado.get("ejecutada", False),
        metodo=resultado.get("metodo_ejecucion", ""),
        soluciones=resultado.get("soluciones_alternativas", []),
    )
    return jsonify(resultado)


@api.route("/api/procesar", methods=["POST"])
def procesar():
    """Procesar petición con Coordinador"""
    data = request.json
    resultado = coordinador_verificacion.procesar_peticion(
        peticion=data.get("peticion"), respuesta_ura=data.get("respuesta_ura")
    )
    # Guardar en DB
    db_manager.save_proceso_coordinador(
        peticion=data.get("peticion"),
        respuesta_ura=data.get("respuesta_ura"),
        supervisor_aprobada=resultado.get("supervisor_aprobada", False),
        ejecutor_ejecutado=resultado.get("ejecutor_ejecutado", False),
        test_forzado_ejecutado=resultado.get("test_forzado_ejecutado", False),
        estado=resultado.get("estado", ""),
        ejecutada=resultado.get("ejecutada", False),
    )
    return jsonify(resultado)


@api.route("/api/test_forzado", methods=["POST"])
def test_forzado_endpoint():
    """Ejecutar test forzado"""
    data = request.json
    resultado = test_forzado.ejecutar_test(
        orden=data.get("orden"), respuesta_ura=data.get("respuesta_ura")
    )
    # Guardar en DB
    db_manager.save_test_forzado(
        orden=data.get("orden"),
        respuesta_ura=data.get("respuesta_ura"),
        negacion=resultado.get("negacion", False),
        test_ejecutado=resultado.get("test_ejecutado", False),
        test_resultado=resultado.get("test_resultado", {}),
    )
    return jsonify(resultado)


@api.route("/api/buscadores/<tipo>", methods=["GET"])
def buscador(tipo):
    """Ejecutar buscador específico"""
    resultado = scheduler_buscadores.ejecutar_tarea(f"buscador_{tipo}")
    return jsonify(resultado)


@api.route("/api/buscadores", methods=["GET"])
def buscadores_todos():
    """Ejecutar todos los buscadores"""
    resultado = scheduler_buscadores.ejecutar_todas()
    return jsonify(resultado)


@api.route("/api/documentacion", methods=["POST"])
def documentacion():
    """Buscar documentación"""
    data = request.json
    resultado = buscador_documentacion.buscar_documentacion(
        tema=data.get("tema"), categoria=data.get("categoria", "general")
    )
    return jsonify(resultado)


@api.route("/api/estadisticas", methods=["GET"])
def estadisticas():
    """Obtener estadísticas del sistema"""
    stats = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "supervisor": tecnico_supervisor.get_estadisticas(),
        "ejecutor": tecnico_ejecutor.get_estadisticas(),
        "coordinador": coordinador_verificacion.get_estadisticas(),
        "test_forzado": test_forzado.get_estadisticas(),
        "db_verificaciones": db_manager.get_estadisticas_verificaciones(),
        "db_ejecuciones": db_manager.get_estadisticas_ejecuciones(),
        "scheduler": scheduler_buscadores.get_configuracion(),
    }
    return jsonify(stats)


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    api.run(host="0.0.0.0", port=5002, debug=debug_mode)
