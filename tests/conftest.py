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
    2. Aísla módulos de proveedores LLM con pop SIN re-import (los tests
       de providers y _get_optional_providers re-importan bajo demanda;
       un re-import aquí invalidaba referencias guardadas de los tests
       que hacen importlib.reload propio).
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
    """Resetea los estados globales compartidos en los clientes de LLM.

    Causa raíz G2 (TASK-20260809-007): ProviderRegistry es un singleton de
    módulo; los tests registran proveedores sin restaurar, y los siguientes
    tests en la suite ven estado contaminado (fallan solo en suite, pasan en
    aislamiento). Aquí se limpia el registro entre tests.
    """
    from motor.core.llm import registry as _llm_registry

    _providers_prev = dict(_llm_registry.registry._providers)
    _default_prev = _llm_registry.registry._default_name
    _llm_registry.registry._providers = {}
    _llm_registry.registry._default_name = None
    yield
    _llm_registry.registry._providers = _providers_prev
    _llm_registry.registry._default_name = _default_prev


@pytest.fixture(autouse=True)
def aislar_torch_cuda() -> Generator[None, None, None]:
    """Aisla torch.cuda.is_available entre tests (CIERRE-20260822).

    Algunos tests reemplazan el atributo sin restaurarlo; si el test de
    anker_pipeline (que espera RuntimeError cuando CUDA no está) corre
    después, recibe un valor contaminado y falla solo en suite completa.
    """
    try:
        import torch

        original = torch.cuda.is_available
        yield
        torch.cuda.is_available = original
    except ImportError:  # pragma: no cover - torch opcional
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


# Perfiles de hypothesis (PLAN mutmut v5, F1/F5):
#   dev -> commit local (pocos ejemplos, <10s) — por defecto
#   ci  -> timer diario 06:00 (muchos ejemplos) — vía HYPOTHESIS_PROFILE=ci
try:
    from hypothesis import settings, Verbosity

    settings.register_profile("dev", max_examples=10, deadline=2000)
    settings.register_profile("ci", max_examples=200, deadline=1000)
    settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
except ImportError:  # hypothesis opcional
    pass
