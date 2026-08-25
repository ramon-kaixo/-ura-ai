"""Tests de los puentes temporales core -> motor (TASK-20260825-005).

Los shims re-exportan la implementacion viva en core/model_router/.
Estos tests fijan el contrato: misma identidad/valor que el origen.
"""

from __future__ import annotations

import pytest


def test_bridge_llm_metrics_es_el_singleton_de_core() -> None:
    from core.model_router.metrics import metrics as metrics_src
    from motor.core.llm.metrics import metrics

    assert metrics is metrics_src


def test_bridge_router_get_urls_identidad() -> None:
    from core.model_router.router import get_urls as get_urls_src
    from motor.core.model_router.router import get_urls

    assert get_urls is get_urls_src
    assert callable(get_urls)


def test_bridge_router_timeout_values() -> None:
    from core.model_router import router as router_src
    from motor.core.model_router.router import CONN_TIMEOUT, READ_TIMEOUT

    assert CONN_TIMEOUT == router_src.CONN_TIMEOUT
    assert READ_TIMEOUT == router_src.READ_TIMEOUT
    assert CONN_TIMEOUT > 0
    assert READ_TIMEOUT > CONN_TIMEOUT


def test_bridge_model_selection_record_success_identidad() -> None:
    from core.model_router.model_selection import (
        _record_success as _record_success_src,
    )
    from motor.core.model_router.model_selection import _record_success

    assert _record_success is _record_success_src
    assert callable(_record_success)


@pytest.mark.parametrize(
    "modulo",
    [
        "motor.core.llm.metrics",
        "motor.core.model_router.router",
        "motor.core.model_router.model_selection",
    ],
)
def test_bridge_modulos_documentados(modulo: str) -> None:
    """Cada puente declara su caracter temporal en el docstring."""
    import importlib

    mod = importlib.import_module(modulo)
    assert mod.__doc__ is not None
    assert "TASK-20260825-005" in mod.__doc__ or "puente" in mod.__doc__.lower()
