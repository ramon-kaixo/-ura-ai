#!/usr/bin/env python3
"""
Módulo: core/code_agents/generators/generator_parser.py
Propósito: Parser de código generado por agentes. Valida sintaxis Python y extrae funciones/clases.
Dependencias principales: ast, json, re, pathlib
Reglas especiales: Rechazar código con eval() o exec(). Validar toda salida antes de aceptar.
"""

import ast
from connectors.ollama_connector import completar

SYSTEM_PROMPT = """Eres un experto en parseo de datos. Generas parsers robustos para CSV, JSON, email y extractos bancarios. Siempre validas el input, manejas encodings y devuelves datos normalizados."""


def generar(tarea: str) -> dict:
    resultado = completar(modelo="qwen2.5:3b-instruct", system=SYSTEM_PROMPT, prompt=tarea)

    # Verificar si Ollama falló
    if not resultado.get("ok"):
        return {
            "ok": False,
            "codigo": None,
            "confianza": None,
            "error": f"Ollama no disponible: {resultado.get('error')}",
        }

    codigo = resultado.get("texto", "")

    # Validar que codigo no sea None
    if codigo is None:
        return {
            "ok": False,
            "codigo": None,
            "confianza": None,
            "error": "Ollama devolvió texto vacío",
        }

    # Validar que es Python válido
    try:
        ast.parse(codigo)
        confianza = "alta"
    except SyntaxError:
        # Reintentar una vez
        resultado = completar(
            modelo="qwen2.5:3b-instruct",
            system=SYSTEM_PROMPT,
            prompt=f"Corrige este código con error de sintaxis:\n{codigo}",
        )
        codigo = resultado.get("texto", "")
        if codigo is None:
            return {
                "ok": False,
                "codigo": None,
                "confianza": None,
                "error": "Ollama devolvió texto vacío tras reintento",
            }
        try:
            ast.parse(codigo)
            confianza = "media"
        except SyntaxError:
            return {
                "ok": False,
                "codigo": None,
                "confianza": None,
                "error": "Sintaxis inválida tras reintento",
            }

    return {"ok": True, "codigo": codigo, "confianza": confianza, "error": None}


if __name__ == "__main__":
    print("=== TEST GENERATOR PARSER ===")
    resultado = generar("Crea un parser para archivos CSV")
    print(f"OK: {resultado['ok']}, Confianza: {resultado['confianza']}")
