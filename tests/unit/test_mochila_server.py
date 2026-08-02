"""Tests for core/mochila/mochila_server.py — endpoints HTTP con TestClient."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


class FakeProvider:
    def __init__(self, nombre: str, modelos: list[str] | None = None) -> None:
        self.nombre = nombre
        self.modelos = modelos or [f"{nombre}-modelo-1", f"{nombre}-modelo-2"]
        self.llamadas: list[dict] = []

    @property
    def timeout(self) -> int:
        return 60

    async def health(self) -> dict:
        return {"status": "ok", "modelos_disponibles": self.modelos, "latencia_ms": 1.0}

    async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
        self.llamadas.append({"modelo": modelo, "stream": stream, "mensajes": mensajes})
        if stream:
            yield {
                "choices": [{"index": 0, "delta": {"content": "hola"}, "finish_reason": None}],
                "usage": None,
            }
            yield {
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            return
        yield {
            "id": "resp-1",
            "object": "chat.completion",
            "created": 1,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "respuesta"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


class FakeProviderError(Exception):
    def __init__(self, message="boom", provider="ollama", status_code=502):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


@pytest.fixture(scope="module")
def ms():
    import core.mochila.mochila_server as module
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter

    tmp = Path(tempfile.mkdtemp(prefix="mochila_test_"))

    originales = {
        "_API_KEY": module._API_KEY,
        "PROVIDERS": module.PROVIDERS,
        "PROVIDER_TIMEOUTS": module.PROVIDER_TIMEOUTS,
        "CACHE_MODELS": module.CACHE_MODELS,
        "CACHE_MODELS_TS": module.CACHE_MODELS_TS,
        "scheduler": module.scheduler,
        "cost_tracker": module.cost_tracker,
        "rate_limiter": module.rate_limiter,
        "circuit_breaker": module.circuit_breaker,
    }

    module._API_KEY = "test-key"
    module.PROVIDERS = {
        "ollama": FakeProvider("ollama"),
        "openrouter": FakeProvider("openrouter"),
        "gemini": FakeProvider("gemini"),
    }
    module.PROVIDER_TIMEOUTS = {"ollama": 120.0, "openrouter": 60.0, "gemini": 30.0}
    module.CACHE_MODELS = []
    module.CACHE_MODELS_TS = 0
    module.cost_tracker = CostTracker(cost_file=tmp / "costs.jsonl")
    module.rate_limiter = RateLimiter()
    module.circuit_breaker = CircuitBreaker(health_file=tmp / "health.json")

    scheduler = AsyncMock()
    scheduler.estimar_vram = lambda body: 10
    scheduler.acquire = AsyncMock(return_value="req-1")
    scheduler.release = AsyncMock()
    module.scheduler = scheduler

    module.router = module.Router(providers=module.PROVIDERS)

    yield module

    for nombre, valor in originales.items():
        setattr(module, nombre, valor)


@pytest.fixture
def client(ms):
    return TestClient(ms.app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-key"}


class TestAuthMiddleware:
    def test_sin_token_401(self, client):
        resp = client.post("/v1/chat/completions", json={})
        assert resp.status_code == 401

    def test_token_invalido_401(self, client):
        resp = client.post(
            "/v1/chat/completions",
            json={},
            headers={"Authorization": "Bearer mal"},
        )
        assert resp.status_code == 401

    def test_health_exento(self, client):
        assert client.get("/health").status_code == 200

    def test_metrics_exento(self, client):
        assert client.get("/metrics").status_code == 200

    def test_docs_exento(self, client):
        assert client.get("/openapi.json").status_code == 200


class TestHealth:
    def test_ok(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert set(data["providers"]) == {"ollama", "openrouter", "gemini"}


class TestV1Models:
    def test_lista_modelos(self, client):
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        data = resp.json()
        ids = [m["id"] for m in data["data"]]
        assert "ollama/ollama-modelo-1" in ids
        assert "openrouter/openrouter-modelo-1" in ids
        assert "gemini/auto" in ids

    def test_incluye_rutas(self, client, ms):
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        ids = [m["id"] for m in resp.json()["data"]]
        assert any(mid in ids for mid in ("ollama/deepseek-coder:6.7b", "openrouter/anthropic/claude-sonnet-4"))

    def test_cache(self, client, ms):
        client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        assert ms.CACHE_MODELS


class TestChatCompletions:
    def test_no_stream_ok(self, client, ms):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "auto", "messages": [{"role": "user", "content": "hola"}]},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "respuesta"
        assert "X-Mochila-Provider" in resp.headers
        assert resp.headers["X-Mochila-Provider"] == "ollama"

    def test_modelo_explicito(self, client, ms):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gemini/mi-modelo", "messages": [{"role": "user", "content": "x"}]},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert resp.headers["X-Mochila-Provider"] == "gemini"

    def test_uso_registrado(self, client, ms):
        client.post(
            "/v1/chat/completions",
            json={"model": "auto", "messages": [{"role": "user", "content": "hola"}]},
            headers={"Authorization": "Bearer test-key"},
        )
        resumen = ms.cost_tracker.resumen_hoy()
        assert resumen["total_tokens"] >= 15

    def test_stream_ok(self, client, ms):
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={"model": "auto", "stream": True, "messages": [{"role": "user", "content": "hola"}]},
            headers={"Authorization": "Bearer test-key"},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
        assert "hola" in body
        assert "[DONE]" in body

    def test_provider_error_502(self, client, ms):
        from core.mochila.providers import ProviderError

        class Explosivo(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("fuego", "ollama", 500)
                yield None  # pragma: no cover

        ms.PROVIDERS["ollama"] = Explosivo("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 500
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")

    def test_respuesta_vacia_502(self, client, ms):
        class Vacio(FakeProvider):
            async def chat(self, *a, **k):
                if False:  # pragma: no cover
                    yield None

        ms.PROVIDERS["ollama"] = Vacio("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 502
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")


class TestRateLimitYBreaker:
    def test_breaker_bloquea_503(self, client, ms):
        ms.circuit_breaker.registrar_fallo("ollama")
        ms.circuit_breaker.registrar_fallo("ollama")
        ms.circuit_breaker.registrar_fallo("ollama")
        ms.circuit_breaker.registrar_fallo("ollama")
        ms.circuit_breaker.registrar_fallo("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 503
        finally:
            ms.circuit_breaker.reset("ollama")

    def test_rate_limit_429(self, client, ms):
        ms.rate_limiter.configurar("ollama", 1)
        ms.rate_limiter.registrar("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}]},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 429
        finally:
            ms.rate_limiter.configurar("ollama", 30)

    def test_breaker_endpoint(self, client):
        resp = client.get("/breaker", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert set(resp.json()) == {"ollama", "openrouter", "gemini"}

    def test_breaker_reset(self, client):
        resp = client.post("/breaker/reset/ollama", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_breaker_reset_404(self, client):
        resp = client.post("/breaker/reset/nope", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 404

    def test_rate_status(self, client):
        resp = client.get("/metrics/rate/ollama", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["provider"] == "ollama"

    def test_rate_status_404(self, client):
        resp = client.get("/metrics/rate/nope", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 404

    def test_cost_summary(self, client):
        resp = client.get("/metrics/cost", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert "total_tokens" in resp.json()


class TestMetrics:
    def test_estructura(self, client):
        resp = client.get("/metrics")
        data = resp.json()
        assert data["providers"] == ["ollama", "openrouter", "gemini"]
        assert data["tools_disponibles"] > 0
        assert "clasificador" in data


class TestHelpers:
    def test_generar_id(self, ms):
        a = ms._generar_id()
        b = ms._generar_id()
        assert a.startswith("mochila-")
        assert a != b

    def test_sse_bytes(self, ms):
        assert ms._sse_bytes({"a": 1}) == b"data: " + json.dumps({"a": 1}).encode() + b"\n\n"

    def test_error_sse_con_penalty(self, ms):
        out = ms._error_sse("mensaje", "tipo", {"k": "v"})
        assert b'"penalty_context"' in out
        assert b'"type": "tipo"' in out

    def test_chunk_es_fin(self, ms):
        assert ms._chunk_es_fin({"choices": [{"delta": {}, "finish_reason": "stop"}]}) is True
        assert ms._chunk_es_fin({"choices": [{"delta": {"content": "x"}, "finish_reason": None}]}) is False
        assert ms._chunk_es_fin({}) is False

    def test_resolver_herramientas(self, ms, client):
        from core.mochila.mochila_server import ChatRequest

        req_true = ChatRequest(model="auto", messages=[], tools=True)
        assert ms._resolver_herramientas(req_true) is not None
        req_list = ChatRequest(model="auto", messages=[], tools=[{"type": "function"}])
        assert ms._resolver_herramientas(req_list) == [{"type": "function"}]
        req_none = ChatRequest(model="auto", messages=[])
        assert ms._resolver_herramientas(req_none) is None

    def test_evaluar_guardian_vacio(self, ms):
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        ab, texto, _penalty = ms._evaluar_guardian(G(), {"choices": [{"delta": {}}]}, "acum", "m")
        assert ab is False
        assert texto == "acum"

    def test_evaluar_guardian_bloquea(self, ms, monkeypatch):
        monkeypatch.setattr("core.mochila.mochila_server.log_event", lambda *a, **k: None)

        class G:
            def evaluar_texto_stream(self, texto):
                return False

            def generar_penalizacion(self):
                return {"pen": 1}

        ab, texto, penalty = ms._evaluar_guardian(G(), {"choices": [{"delta": {"content": "malo"}}]}, "", "m")
        assert ab is True
        assert texto == "malo"
        assert penalty == {"pen": 1}


class TestProxyGateway:
    def test_get_upstream_errores_conectando(self, client, ms):
        resp = client.get("/api/foo")
        assert resp.status_code in (401, 502)

    def test_apaga_scheduler(self, client, ms):
        assert ms.scheduler is not None
