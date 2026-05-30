"""Tests para Registry API (5 endpoints REST)."""

import json
import os
import tempfile
import pytest
from unittest.mock import patch
from pathlib import Path

TOKEN = "test-token-ura"


# Mock del archivo de inventario
@pytest.fixture
def mock_inventory():
    os.environ["URA_TOKEN"] = TOKEN
    data = {
        "agents": [
            {
                "id": "test1",
                "type": "test",
                "ip": "10.0.0.1",
                "port": 5000,
                "last_seen": "2026-05-16",
            },
            {
                "id": "test2",
                "type": "test",
                "ip": "10.0.0.2",
                "port": 5001,
                "last_seen": "2026-05-16",
            },
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        fname = f.name
    with patch.object(Path, "resolve", return_value=Path(fname)):
        with patch("agents.registry_api.INVENTORY", Path(fname)):
            from agents import registry_api

            registry_api.app.config["TESTING"] = True
            client = registry_api.app.test_client()
            client.environ_base.setdefault("HTTP_AUTHORIZATION", f"Bearer {TOKEN}")
            yield client
    os.unlink(fname)


def test_list_agents(mock_inventory):
    """GET /agents — lista todos los agentes"""
    r = mock_inventory.get("/agents")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 2
    assert data[0]["id"] == "test1"


def test_get_agent_found(mock_inventory):
    """GET /agents/<id> — agente existente"""
    r = mock_inventory.get("/agents/test1")
    assert r.status_code == 200
    assert r.get_json()["id"] == "test1"


def test_get_agent_not_found(mock_inventory):
    """GET /agents/<id> — 404 si no existe"""
    r = mock_inventory.get("/agents/no_existe")
    assert r.status_code == 404


def test_register_agent(mock_inventory):
    """POST /agents — registrar nuevo agente"""
    r = mock_inventory.post("/agents", json={"id": "nuevo", "type": "test"})
    assert r.status_code == 201
    assert r.get_json()["status"] == "registrado"


def test_register_duplicate(mock_inventory):
    """POST /agents — 409 si ya existe"""
    r = mock_inventory.post("/agents", json={"id": "test1", "type": "test"})
    assert r.status_code == 409


def test_heartbeat(mock_inventory):
    """PUT /agents/<id>/heartbeat — actualiza last_seen"""
    r = mock_inventory.put("/agents/test1/heartbeat", json={"timestamp": "2026-06-01"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_heartbeat_not_found(mock_inventory):
    """PUT /agents/<id>/heartbeat — 404 si no existe"""
    r = mock_inventory.put("/agents/no_existe/heartbeat", json={"timestamp": "2026-06-01"})
    assert r.status_code == 404


def test_registry_heartbeat(mock_inventory):
    """POST /registry/heartbeat — heartbeat genérico"""
    r = mock_inventory.post(
        "/registry/heartbeat", json={"agent": "test1", "timestamp": "2026-06-01"}
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_registry_heartbeat_new_agent(mock_inventory):
    """POST /registry/heartbeat — registra agente nuevo automáticamente"""
    r = mock_inventory.post(
        "/registry/heartbeat", json={"agent": "nuevo", "type": "test", "timestamp": "2026-06-01"}
    )
    assert r.status_code == 201
    assert r.get_json()["status"] == "registrado"


def test_bibliotecario_consulta(mock_inventory):
    """GET /bibliotecario/consulta — endpoint de búsqueda"""
    r = mock_inventory.get("/bibliotecario/consulta?q=test1")
    assert r.status_code == 200
    data = r.get_json()
    assert "resultados" in data
    assert "total" in data
