"""Fixtures globales para toda la suite de tests.

Aísla el estado entre tests para evitar dependencias de orden de ejecucion.
Tres fixtures autouse:
1. isolate_test_environment: restaura variables de entorno
2. reset_provider_singletons: limpia cachés de proveedores LLM
3. reset_engine_holder: resetea _EngineHolder global entre tests
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment() -> Generator[None, None, None]:
    """
    Garantiza independencia absoluta de cada test:
    1. Aisla y restaura variables de entorno.
    2. Limpia sys.modules de modulos de proveedores.
    """
    original_env = dict(os.environ)
    modules_to_clear = [
        "motor.core.llm.gemini",
        "motor.core.llm.lmstudio",
        "motor.core.llm.openrouter",
        "motor.core.llm.vllm",
        "motor.core.llm.ollama",
        "motor.core.llm.openai",
        "motor.core.llm.anthropic",
    ]
    for mod_name in modules_to_clear:
        sys.modules.pop(mod_name, None)

    yield

    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def reset_provider_singletons() -> Generator[None, None, None]:
    """Resetea los estados globales compartidos en los clientes de LLM."""
    yield


@pytest.fixture(autouse=True)
def reset_engine_holder() -> Generator[None, None, None]:
    """Resetea _EngineHolder global entre tests.

    _EngineHolder.engine y .llm son singletons compartidos por todos los
    tests de test_audit_api.py. Si un test deja el engine en estado
    corrupto (conexion cerrada, threads sueltos), el siguiente test se
    cuelga en SQLite. Este fixture garantiza estado limpio cada test.
    """
    from motor.assistant.api.handlers import _EngineHolder
    from motor.assistant.api.middleware import _rate_limiter

    _EngineHolder.engine = None
    _EngineHolder.llm = None
    _rate_limiter._requests.clear()
    yield
    _EngineHolder.engine = None
    _EngineHolder.llm = None
    _rate_limiter._requests.clear()
