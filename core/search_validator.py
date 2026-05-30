#!/usr/bin/env python3
"""
Search Validator para N3.

Valida respuestas de búsqueda.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("search_validator")


def validate_response(texto: str) -> tuple[bool, float]:
    """
    Valida respuesta de búsqueda y asigna score.

    Args:
        texto: Texto de la respuesta

    Returns:
        (is_valid, score) donde score está entre 0.0 y 1.0
    """
    # Validación 1: longitud mínima
    if len(texto) < 50:
        return False, 0.0

    # Validación 2: no contener palabras de error
    error_keywords = [
        "error",
        "timeout",
        "failed",
        "exception",
        "no puedo",
        "no puedo responder",
        "no tengo información",
        "no encontré resultados",
        "no puedo responder",
    ]

    texto_lower = texto.lower()
    if any(keyword in texto_lower for keyword in error_keywords):
        return False, 0.0

    # Validación 3: longitud máxima razonable (evitar respuestas excesivamente largas)
    if len(texto) > 10000:
        logger.warning(f"Respuesta demasiado larga: {len(texto)} caracteres")
        return False, 0.0

    # Scoring basado en longitud y calidad
    length_score = min(len(texto) / 500, 1.0)

    # Bonus por longitud media (100-500 caracteres)
    if 100 <= len(texto) <= 500:
        length_score = min(length_score + 0.2, 1.0)

    # Bonus por longitud buena (500-1000 caracteres)
    if 500 < len(texto) <= 1000:
        length_score = min(length_score + 0.3, 1.0)

    return True, length_score


if __name__ == "__main__":
    # Tests
    test_cases = [
        ("", "vacío"),
        ("hola", "muy corto"),
        ("a" * 49, "justo debajo de 50"),
        ("a" * 50, "justo 50 caracteres"),
        ("a" * 100, "100 caracteres"),
        ("a" * 500, "500 caracteres"),
        ("a" * 1000, "1000 caracteres"),
        ("a" * 10001, "demasiado largo"),
        ("respuesta con error en el texto", "contiene error"),
        ("no puedo responder a esto", "no puedo"),
        ("respuesta válida con suficiente longitud para ser considerada buena", "válida"),
    ]

    print("=== Tests de SearchValidator ===\n")

    for texto, descripcion in test_cases:
        is_valid, score = validate_response(texto)
        print(f"{descripcion}: valid={is_valid}, score={score:.2f}")
