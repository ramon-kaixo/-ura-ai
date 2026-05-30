#!/usr/bin/env python3
"""
API de Consulta de Vocabulario - URA App
Endpoint REST para que otros agentes consulten vocabulario
"""

import json
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)


class APIVocabulario:
    """API REST para consulta de vocabulario"""

    def __init__(self):
        self.nombre = "api_vocabulario"
        self.biblioteca_path = Path("/Users/ramonesnaola/URA/ura_ia_1972/biblioteca/vocabulario")
        self.estadisticas_path = Path(
            "/Users/ramonesnaola/URA/ura_ia_1972/biblioteca/vocabulario/estadisticas.json"
        )
        self._cargar_estadisticas()

    def _cargar_estadisticas(self):
        """Cargar estadísticas desde archivo"""
        if self.estadisticas_path.exists():
            try:
                self.estadisticas = json.loads(self.estadisticas_path.read_text())
            except:
                self.estadisticas = {
                    "consultas": {},
                    "ultima_actualizacion": datetime.now().isoformat(),
                }
        else:
            self.estadisticas = {
                "consultas": {},
                "ultima_actualizacion": datetime.now().isoformat(),
            }

    def _guardar_estadisticas(self):
        """Guardar estadísticas a archivo"""
        self.estadisticas["ultima_actualizacion"] = datetime.now().isoformat()
        self.estadisticas_path.write_text(json.dumps(self.estadisticas, indent=2))

    def buscar_vocabulario(self, termino: str, departamento: str = None) -> list:
        """Buscar término en vocabulario"""
        resultados = []

        # Determinar directorios a buscar
        if departamento:
            directorios = [self.biblioteca_path / departamento]
        else:
            directorios = (
                list(self.biblioteca_path.iterdir()) if self.biblioteca_path.exists() else []
            )

        # Buscar en archivos JSON
        for directorio in directorios:
            if not directorio.is_dir():
                continue

            for archivo in directorio.glob("*.json"):
                try:
                    datos = json.loads(archivo.read_text())

                    # Buscar en términos técnicos
                    for item in datos.get("terminos_tecnicos", []):
                        if termino.lower() in item.get("termino", "").lower():
                            resultados.append(
                                {
                                    "fuente": datos.get("fuente"),
                                    "herramienta": datos.get("herramienta"),
                                    "termino": item.get("termino"),
                                    "contexto": item.get("contexto"),
                                    "ejemplo": item.get("ejemplo"),
                                    "departamento": directorio.name,
                                }
                            )
                except:
                    pass

        # Registrar estadística
        if termino not in self.estadisticas["consultas"]:
            self.estadisticas["consultas"][termino] = 0
        self.estadisticas["consultas"][termino] += 1
        self._guardar_estadisticas()

        return resultados

    def obtener_vocabulario_herramienta(self, herramienta: str) -> dict:
        """Obtener vocabulario completo de una herramienta"""
        for directorio in self.biblioteca_path.iterdir():
            archivo = directorio / f"{herramienta}_vocabulario.json"
            if archivo.exists():
                return json.loads(archivo.read_text())
        return None

    def listar_herramientas(self, departamento: str = None) -> list:
        """Listar herramientas disponibles"""
        herramientas = []

        if departamento:
            directorio = self.biblioteca_path / departamento
            if directorio.exists():
                for archivo in directorio.glob("*_vocabulario.json"):
                    herramientas.append(archivo.stem.replace("_vocabulario", ""))
        else:
            for directorio in self.biblioteca_path.iterdir():
                if directorio.is_dir():
                    for archivo in directorio.glob("*_vocabulario.json"):
                        herramientas.append(
                            {
                                "herramienta": archivo.stem.replace("_vocabulario", ""),
                                "departamento": directorio.name,
                            }
                        )

        return herramientas

    def obtener_estadisticas(self) -> dict:
        """Obtener estadísticas de uso"""
        return self.estadisticas


# Instancia global
api_vocabulario = APIVocabulario()


@app.route("/vocabulario/buscar", methods=["GET"])
def buscar():
    """Endpoint de búsqueda"""
    termino = request.args.get("termino", "")
    departamento = request.args.get("departamento")

    if not termino:
        return jsonify({"error": "Se requiere parámetro termino"}), 400

    resultados = api_vocabulario.buscar_vocabulario(termino, departamento)
    return jsonify(
        {
            "termino": termino,
            "departamento": departamento,
            "resultados": resultados,
            "total": len(resultados),
        }
    )


@app.route("/vocabulario/herramienta/<herramienta>", methods=["GET"])
def obtener_herramienta(herramienta):
    """Obtener vocabulario de una herramienta"""
    vocabulario = api_vocabulario.obtener_vocabulario_herramienta(herramienta)
    if vocabulario:
        return jsonify(vocabulario)
    return jsonify({"error": "Herramienta no encontrada"}), 404


@app.route("/vocabulario/herramientas", methods=["GET"])
def listar_herramientas():
    """Listar herramientas disponibles"""
    departamento = request.args.get("departamento")
    herramientas = api_vocabulario.listar_herramientas(departamento)
    return jsonify({"herramientas": herramientas})


@app.route("/vocabulario/estadisticas", methods=["GET"])
def estadisticas():
    """Obtener estadísticas de uso"""
    return jsonify(api_vocabulario.obtener_estadisticas())


@app.route("/vocabulario/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify(
        {"status": "ok", "servicio": "api_vocabulario", "timestamp": datetime.now().isoformat()}
    )


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
