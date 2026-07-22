"""Fixtures globales para toda la suite de tests.

Aísla el estado entre tests para evitar dependencias de orden de ejecución.

Problema: Tests que importan módulos de proveedores (gemini, lmstudio, etc.)
comparten el caché de Python. Cuando un test importa un módulo, el siguiente
test obtiene la misma instancia en caché, que puede tener estado residual.

Solución: Restaurar entorno + limpiar módulos problemáticos después de cada test.
"""

from __future__ import annotations

import os
import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment_and_state():
    """Fixture global que se ejecuta automáticamente en cada test.

    1. Guarda el entorno de variables antes del test.
    2. Elimina los módulos de proveedores del caché para forzar
       re-importación limpia en el siguiente test.
    3. Restaura el entorno después del test.
    """
    # 1. Guardar copia del entorno original
    original_env = dict(os.environ)

    # 2. Eliminar módulos de proveedores del caché de importación
    #    para que cada test obtenga una instancia fresca.
    modules_to_clear = [
        "motor.core.llm.gemini",
        "motor.core.llm.lmstudio",
        "motor.core.llm.openrouter",
        "motor.core.llm.vllm",
        "motor.core.llm.ollama",
        "motor.core.llm.openai",
        "motor.core.llm.anthropic",
        "motor.core.llm.base",
    ]
    for mod_name in modules_to_clear:
        sys.modules.pop(mod_name, None)

    yield

    # 3. Restaurar el entorno exacto previo a la ejecución del test
    os.environ.clear()
    os.environ.update(original_env)

    # 4. Limpiar nuevamente los módulos de proveedores después del test
    for mod_name in modules_to_clear:
        sys.modules.pop(mod_name, None)
