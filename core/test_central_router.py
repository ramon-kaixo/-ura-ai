#!/usr/bin/env python3
"""Tests básicos para CentralRouter — los 5 métodos más importantes."""

import pytest
import asyncio
import json
from pathlib import Path

from core.central_router import CentralRouter, get_central_router


@pytest.fixture
def router():
    return CentralRouter()


# === SINGLETON ===


def test_singleton_pattern(router):
    """Dos instancias son el mismo objeto (singleton real)."""
    r2 = CentralRouter()
    assert router is r2


def test_get_central_router(router):
    """get_central_router devuelve singleton."""
    r = get_central_router()
    assert r is router


# === ENTRY POINT ===


def test_process_request_devuelve_dict(router):
    """process_request devuelve dict con claves esperadas."""
    import asyncio

    result = asyncio.run(router.process_request("hola"))
    assert isinstance(result, dict)
    for key in ("intent", "agent", "response", "confidence", "metadata"):
        assert key in result, f"Falta clave: {key}"


def test_process_request_input_vacio(router):
    """Input vacío no crashea."""
    import asyncio

    result = asyncio.run(router.process_request(""))
    assert isinstance(result, dict)


def test_process_request_input_largo(router):
    """Input muy largo no crashea."""
    result = asyncio.run(router.process_request("a" * 5000))
    assert isinstance(result, dict)


def test_process_request_detecta_cocina(router):
    """'receta de paella' debe detectar intención de cocina."""
    result = asyncio.run(router.process_request("dame una receta de paella"))
    assert "cocina" in result.get("intent", ""), f"Intent: {result.get('intent')}"


def test_process_request_detecta_factura(router):
    """'crear factura' debe detectar intención de facturación."""
    result = asyncio.run(router.process_request("crea una factura para el cliente Pérez"))
    assert "factura" in result.get("intent", ""), f"Intent: {result.get('intent')}"


def test_process_request_registra_en_scribe(router):
    """forensic_scribe registra task_start (y opcionalmente task_success)."""
    import asyncio

    scribe_log = Path.home() / ".ura" / "scribe_log.json"
    before_count = 0
    if scribe_log.exists():
        before_count = len(json.loads(scribe_log.read_text()))

    asyncio.run(router.process_request("hola"))

    assert scribe_log.exists(), "scribe_log no existe tras process_request"
    events = json.loads(scribe_log.read_text())
    after_count = len(events)
    # Al menos task_start debe registrarse
    assert after_count >= before_count + 1, (
        f"Esperaba ≥{before_count + 1} eventos, hay {after_count}"
    )
    # Verificar que task_start está entre los últimos eventos
    recent_types = [e["type"] for e in events[-(after_count - before_count + 1) :]]
    assert "task_start" in recent_types, f"Falta task_start en {recent_types}"


# === INTENT DETECTION ===


def test_detect_intent_keywords(router):
    """Keyword detection encuentra intenciones conocidas."""
    intent, conf = router._detect_intent_keywords("dame una receta de tortilla de patatas")
    assert "cocina" in intent, f"Esperaba cocina, obtuve: {intent}"
    assert conf > 0


def test_detect_intent_keywords_sin_match(router):
    """Sin keywords conocidas devuelve chat con baja confianza."""
    intent, conf = router._detect_intent_keywords("xyzzy nothing matches")
    assert intent == "chat" or conf < 0.5


# === AGENT LISTING ===


def test_list_agents(router):
    """list_agents devuelve lista con información."""
    agents = router.list_agents()
    assert isinstance(agents, list)
    assert len(agents) > 0
    assert "intent" in agents[0] or "name" in agents[0] or "agent" in agents[0]


def test_get_status(router):
    """get_status devuelve métricas del router."""
    status = router.get_status()
    assert isinstance(status, dict)
    assert "intents" in status or "agents" in status


# === MEMORIA COMPARTIDA ===


def test_shared_memory_set_get(router):
    """Guardar y leer de memoria compartida."""
    router.set_shared_memory("test_key", "test_value", agent="test")
    val = router.get_shared_memory("test_key")
    assert val == "test_value"


def test_list_shared_memory(router):
    """Listar claves en memoria compartida."""
    router.set_shared_memory("test_list", 42, agent="test")
    keys = router.list_shared_memory()
    assert "test_list" in keys
