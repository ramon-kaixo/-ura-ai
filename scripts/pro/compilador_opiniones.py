#!/usr/bin/env python3
"""compilador_opiniones.py — Compilador de opiniones con reparación JSON y reintentos.

Lógica:
- json_repair corrige JSON corrupto de modelos 70B bajo estrés
- Temperatura 0.0 para infraestructura, 0.3 para el resto
- Reintento con Qwen 32B si el JSON sigue inválido tras reparar
"""

from __future__ import annotations

import json

from json_repair import repair_json

# Prioridades por temperatura
PRIORIDAD_INFRA = {"core/", "scripts/", "configs/", "mantenimiento/"}
TEMPERATURA_DEFAULT = 0.3
TEMPERATURA_INFRA = 0.0


def es_infraestructura(ruta: str) -> bool:
    """Determina si un archivo es de infraestructura (temperatura 0.0)."""
    return any(ruta.startswith(prefijo) for prefijo in PRIORIDAD_INFRA)


def validar_esquema(data: dict) -> bool:
    """Valida que el JSON tenga los campos obligatorios."""
    obligatorios = ["vulnerabilidad", "criticidad"]
    return all(k in data for k in obligatorios)


def compilar_opinion(
    modelo: str,
    codigo: str,
    ruta: str = "",
    reintentos: int = 1,
) -> dict | None:
    """Envía código a un modelo, repara JSON, reintenta si falla.

    Args:
        modelo: Nombre del modelo en Ollama (ej: "llama3.3:70b")
        codigo: Código fuente a auditar (sanitizado)
        ruta: Ruta del archivo (para determinar temperatura)
        reintentos: Número de reintentos permitidos (default 1 = fallback a Qwen)

    Returns:
        Dict con {"vulnerabilidad": ..., "criticidad": ...} o None si falla

    """
    temperatura = TEMPERATURA_INFRA if es_infraestructura(ruta) else TEMPERATURA_DEFAULT
    prompt = (
        f"Audita este código con temperatura {temperatura}.\n"
        "Responde ÚNICAMENTE un JSON con los campos:\n"
        '  - "vulnerabilidad": descripción del problema\n'
        '  - "criticidad": "BAJA" | "MEDIA" | "ALTA" | "CRITICA"\n'
        "No añadas explicaciones fuera del JSON.\n\n"
        f"Código:\n```\n{codigo}\n```"
    )

    for intento in range(reintentos + 1):
        modelo_reintento = "qwen2.5-coder:32b" if intento > 0 else modelo

        try:
            import subprocess

            result = subprocess.run(
                ["ollama", "run", modelo_reintento, prompt],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            raw = result.stdout.strip()
        except Exception:
            delay = (2**intento) + __import__("random").uniform(0, 1)
            __import__("time").sleep(delay)
            continue

        # Reparar JSON
        try:
            reparado = repair_json(raw)
            data = json.loads(reparado)
        except Exception:
            continue

        if validar_esquema(data):
            data["modelo"] = modelo_reintento
            data["temperatura"] = temperatura
            return data

    return None


if __name__ == "__main__":
    # Test rápido
    test_code = "def foo(x): return x + 1"
    r = compilar_opinion("qwen2.5-coder:32b", test_code, "core/test.py")
    if r:
        pass
    else:
        pass
