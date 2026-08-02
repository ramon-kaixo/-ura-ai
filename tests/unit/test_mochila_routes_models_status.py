"""Tests para core/mochila/routes/models.py y status.py."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest import mock

from core.mochila._state import MochilaState


def _state() -> MochilaState:
    st = MochilaState(providers={}, provider_timeouts={})
    st.router = SimpleNamespace(
        rutas={"razonamiento": [{"provider": "ollama", "modelo": "qwen3:32b"}]},
        clasificador=SimpleNamespace(),
    )
    st.circuit_breaker = SimpleNamespace(estado=lambda p: {"ok": True})
    st.rate_limiter = SimpleNamespace()
    st.cost_tracker = SimpleNamespace(resumen_hoy=lambda: {"total": 1})
    return st


class TestModelsRouter:
    def test_models_ok(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.models import create_models_router

        st = _state()
        provider = mock.AsyncMock()
        provider.health.return_value = {"status": "ok", "modelos_disponibles": ["m1", "m2"]}
        st.providers["ollama"] = provider
        app = FastAPI()
        app.include_router(create_models_router(st))
        client = TestClient(app)
        r = client.get("/v1/models")
        assert r.status_code == 200
        data = r.json()
        assert data["object"] == "list"
        ids = [m["id"] for m in data["data"]]
        assert "ollama/m1" in ids
        assert "ollama/m2" in ids
        assert "ollama/auto" in ids
        assert "ollama/qwen3:32b" in ids

    def test_models_cache(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.models import create_models_router

        st = _state()
        provider = mock.AsyncMock()
        provider.health.return_value = {"status": "ok", "modelos_disponibles": ["m1"]}
        st.providers["ollama"] = provider
        app = FastAPI()
        app.include_router(create_models_router(st))
        client = TestClient(app)
        client.get("/v1/models")
        provider.health.await_count_1 = provider.health.await_count
        client.get("/v1/models")
        assert provider.health.await_count == 1  # cacheada

    def test_models_cache_expira(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.models import create_models_router

        st = _state()
        provider = mock.AsyncMock()
        provider.health.return_value = {"status": "ok", "modelos_disponibles": ["m1"]}
        st.providers["ollama"] = provider
        app = FastAPI()
        app.include_router(create_models_router(st))
        client = TestClient(app)
        client.get("/v1/models")
        st.cache_models_ts = time.time() - 120  # expirar
        client.get("/v1/models")
        assert provider.health.await_count == 2

    def test_models_provider_sin_modelos(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.models import create_models_router

        st = _state()
        provider = mock.AsyncMock()
        provider.health.return_value = {"status": "ok"}
        st.providers["ollama"] = provider
        app = FastAPI()
        app.include_router(create_models_router(st))
        client = TestClient(app)
        r = client.get("/v1/models")
        ids = [m["id"] for m in r.json()["data"]]
        assert "ollama/auto" in ids


class TestStatusRouter:
    def test_status_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.status import create_status_router

        st = _state()
        st.providers["ollama"] = mock.Mock()
        app = FastAPI()
        with mock.patch("core.mochila.routes.status.system_status", mock.AsyncMock(return_value={"status": "ok"})):
            app.include_router(create_status_router(st))
            client = TestClient(app)
            r = client.get("/status")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_metrics_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.status import create_status_router

        st = _state()
        st.providers["ollama"] = mock.Mock()
        app = FastAPI()
        app.include_router(create_status_router(st))
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert data["providers"] == ["ollama"]
        assert "razonamiento" in data["rutas"]
        assert data["rutas"]["razonamiento"] == ["ollama/qwen3:32b"]
        assert data["tools_disponibles"] >= 0
