#!/usr/bin/env python3
"""
URA Code Generators Registry
Registro central de generators para URA y el Director Técnico
"""

from core.code_agents.generators import (
    generator_agent,
    generator_api,
    generator_tests,
    generator_scripts,
    generator_sql,
    generator_config,
    generator_monitor,
    generator_workflow,
    generator_parser,
    generator_repair,
)

GENERATORS = {
    "agent": {
        "modulo": generator_agent,
        "descripcion": "Crea nuevos agentes especializados para URA",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "api": {
        "modulo": generator_api,
        "descripcion": "Genera conectores REST e integraciones externas",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "tests": {
        "modulo": generator_tests,
        "descripcion": "Genera tests pytest para módulos existentes",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "media",
    },
    "scripts": {
        "modulo": generator_scripts,
        "descripcion": "Genera scripts de automatización",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "sql": {
        "modulo": generator_sql,
        "descripcion": "Genera queries SQLite parametrizadas",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "config": {
        "modulo": generator_config,
        "descripcion": "Genera archivos de configuración JSON",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "monitor": {
        "modulo": generator_monitor,
        "descripcion": "Genera módulos de monitoreo y métricas",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "media",
    },
    "workflow": {
        "modulo": generator_workflow,
        "descripcion": "Genera flujos de orquestación entre agentes",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "media",
    },
    "parser": {
        "modulo": generator_parser,
        "descripcion": "Genera parsers para CSV, JSON, email, extractos",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "alta",
    },
    "repair": {
        "modulo": generator_repair,
        "descripcion": "Genera parches de auto-reparación desde tracebacks",
        "modelo": "qwen2.5:3b-instruct",
        "confianza_minima_auto": "baja",
    },
}


def listar() -> list:
    """Listar todos los generators disponibles"""
    return [{"tipo": k, "descripcion": v["descripcion"]} for k, v in GENERATORS.items()]


def generar(tipo: str, tarea: str) -> dict:
    """
    Generar código usando un generator específico

    Args:
        tipo: Tipo de generator (agent, api, tests, etc.)
        tarea: Descripción de la tarea a generar

    Returns:
        Dict con resultado de generación + metadatos
    """
    if tipo not in GENERATORS:
        return {
            "ok": False,
            "error": f"Generator '{tipo}' no existe. Disponibles: {list(GENERATORS.keys())}",
        }

    g = GENERATORS[tipo]
    resultado = g["modulo"].generar(tarea)
    resultado["tipo"] = tipo
    resultado["requiere_confirmacion"] = resultado.get("confianza") != g["confianza_minima_auto"]

    return resultado


if __name__ == "__main__":
    print("=== TEST REGISTRY ===")
    print("Generators disponibles:")
    for g in listar():
        print(f"  {g['tipo']}: {g['descripcion']}")

    resultado = generar("config", "Configuración para un agente de monitoreo de red")
    print(
        f"Test generación: {resultado['ok']}, Confianza: {resultado.get('confianza')}, Requiere confirmación: {resultado.get('requiere_confirmacion')}"
    )
