import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from core.mochila.circuit_breaker import CircuitBreaker, CircuitState
from core.mochila.cost_tracker import CostTracker
from core.mochila.rate_limiter import RateLimiter
from core.mochila.router import ClasificadorKeyword, NoProviderAvailable, RouteResult, Router
from core.mochila.tools import TOOL_SCHEMAS, file_read, ejecutar_tool


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def setup_method(self):
        import glob, os
        for f in glob.glob("/tmp/test_cb_*.json"):
            try:
                os.unlink(f)
            except OSError:
                pass

    def test_init_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1, half_open_max_requests=1, health_file=Path("/tmp/test_cb_init.json"))
        assert cb.puede_pasar("test") is True
        assert cb.estado("test")["state"] == "closed"

    def test_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1, half_open_max_requests=1, health_file=Path("/tmp/test_cb_open.json"))
        for _ in range(3):
            cb.registrar_fallo("test")
        assert cb.puede_pasar("test") is False
        assert cb.estado("test")["state"] == "open"
        assert cb.estado("test")["consecutive_failures"] == 3

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, half_open_max_requests=1, health_file=Path("/tmp/test_cb_half.json"))
        cb.registrar_fallo("test")
        cb.registrar_fallo("test")
        assert cb.estado("test")["state"] == "open"
        assert cb.puede_pasar("test") is False
        asyncio.run(asyncio.sleep(0.1))
        assert cb.puede_pasar("test") is True
        assert cb.estado("test")["state"] == "half_open"

    def test_closed_on_success_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, half_open_max_requests=1, health_file=Path("/tmp/test_cb_close_on_success.json"))
        cb.registrar_fallo("test")
        cb.registrar_fallo("test")
        asyncio.run(asyncio.sleep(0.1))
        cb.puede_pasar("test")
        cb.registrar_exito("test")
        assert cb.estado("test")["state"] == "closed"
        assert cb.estado("test")["consecutive_failures"] == 0

    def test_open_again_on_failure_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, half_open_max_requests=2, health_file=Path("/tmp/test_cb_open_again.json"))
        cb.registrar_fallo("test")
        cb.registrar_fallo("test")
        asyncio.run(asyncio.sleep(0.1))
        cb.puede_pasar("test")
        cb.registrar_fallo("test")
        assert cb.estado("test")["state"] == "open"

    def test_timeout_counts_as_failure(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_max_requests=1, health_file=Path("/tmp/test_cb_timeout.json"))
        cb.registrar_fallo("test", es_timeout=True)
        assert cb.estado("test")["state"] == "open"

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_max_requests=1, health_file=Path("/tmp/test_cb_reset.json"))
        cb.registrar_fallo("test")
        assert cb.estado("test")["state"] == "open"
        cb.reset("test")
        assert cb.estado("test")["state"] == "closed"
        assert cb.estado("test")["consecutive_failures"] == 0

    def test_persistence(self):
        hf = Path(tempfile.mkstemp(suffix=".json")[1])
        hf.unlink(missing_ok=True)
        try:
            cb1 = CircuitBreaker(failure_threshold=2, recovery_timeout=1, half_open_max_requests=1, health_file=hf)
            cb1.registrar_fallo("persist_test")
            cb1.registrar_fallo("persist_test")
            assert cb1.estado("persist_test")["state"] == "open"

            cb2 = CircuitBreaker(failure_threshold=2, recovery_timeout=1, half_open_max_requests=1, health_file=hf)
            assert cb2.estado("persist_test")["state"] == "open"
            assert cb2.estado("persist_test")["consecutive_failures"] == 2
        finally:
            hf.unlink(missing_ok=True)

    def test_multiple_providers(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_max_requests=1, health_file=Path("/tmp/test_cb_multi.json"))
        cb.registrar_fallo("p1")
        assert cb.puede_pasar("p1") is False
        assert cb.puede_pasar("p2") is True


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter()
        rl.configurar("test", 3)
        for _ in range(3):
            puede, actual, limite = rl.puede_pasar("test")
            assert puede is True
            rl.registrar("test")

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        rl.configurar("test", 2)
        rl.registrar("test")
        rl.registrar("test")
        puede, actual, limite = rl.puede_pasar("test")
        assert puede is False
        assert actual == 2
        assert limite == 2

    def test_window_expires(self):
        rl = RateLimiter()
        rl.configurar("test", 1)
        rl.registrar("test")
        puede, _, _ = rl.puede_pasar("test")
        assert puede is False
        rl._ventanas["test"] = [0.0]
        puede, _, _ = rl.puede_pasar("test")
        assert puede is True


# ---------------------------------------------------------------------------
# Cost Tracker
# ---------------------------------------------------------------------------

class TestCostTracker:
    def test_register(self):
        cf = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        cf.unlink(missing_ok=True)
        try:
            ct = CostTracker(tarifas={"test": 0.0}, cost_file=cf)
            entry = ct.registrar("test", "model-x", 100, 50)
            assert entry["provider"] == "test"
            assert entry["total_tokens"] == 150
            assert entry["cost_estimate"] == 0.0
        finally:
            cf.unlink(missing_ok=True)

    def test_resumen_hoy_empty(self):
        cf = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        cf.unlink(missing_ok=True)
        try:
            ct = CostTracker(cost_file=cf)
            r = ct.resumen_hoy()
            assert r["total_tokens"] == 0
            assert r["total_cost"] == 0.0
        finally:
            cf.unlink(missing_ok=True)

    def test_resumen_hoy_aggregates(self):
        cf = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        cf.unlink(missing_ok=True)
        try:
            ct = CostTracker(tarifas={"ollama": 0.0}, cost_file=cf)
            ct.registrar("ollama", "qwen2.5:7b", 50, 20)
            ct.registrar("ollama", "qwen2.5:7b", 100, 40)
            r = ct.resumen_hoy()
            assert r["total_tokens"] == 210
            assert r["por_provider"]["ollama"] == 2
        finally:
            cf.unlink(missing_ok=True)

    def test_jsonl_append_only(self):
        cf = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        cf.unlink(missing_ok=True)
        try:
            ct = CostTracker(cost_file=cf)
            ct.registrar("p1", "m1", 10, 5)
            ct.registrar("p2", "m2", 20, 10)
            lines = cf.read_text().strip().split("\n")
            assert len(lines) == 2
        finally:
            cf.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class TestClasificadorKeyword:
    def test_codigo(self):
        c = ClasificadorKeyword()
        assert c.clasificar([{"role": "user", "content": "escribe una funcion en python"}]) == "codigo"

    def test_razonamiento(self):
        c = ClasificadorKeyword()
        assert c.clasificar([{"role": "user", "content": "analiza las ventajas de usar postgresql"}]) == "razonamiento"

    def test_rapido(self):
        c = ClasificadorKeyword()
        assert c.clasificar([{"role": "user", "content": "hola como estas"}]) == "rapido"

    def test_task_hint_overrides(self):
        c = ClasificadorKeyword()
        assert c.clasificar([{"role": "user", "content": "hola"}], task_hint="codigo") == "codigo"


class TestRouter:
    def test_route_codigo(self):
        r = Router(providers={"ollama": "fake"})
        result = r.route([{"role": "user", "content": "refactoriza esta clase"}])
        assert result.provider == "ollama"
        assert "codigo" in result.route_reason

    def test_route_explicit(self):
        r = Router(providers={"ollama": "fake", "openrouter": "fake"})
        result = r.route([{"role": "user", "content": "hola"}], modelo_hint="openrouter/model-x")
        assert result.provider == "openrouter"
        assert result.modelo == "model-x"
        assert "explicit" in result.route_reason

    def test_route_explicit_ollama_fallback(self):
        r = Router(providers={"ollama": "fake"})
        result = r.route([{"role": "user", "content": "hola"}], modelo_hint="model-x")
        assert result.provider == "ollama"
        assert result.modelo == "model-x"

    def test_route_task_hint(self):
        r = Router(providers={"ollama": "fake", "openrouter": "fake"})
        result = r.route([{"role": "user", "content": "hola"}], task_hint="razonamiento")
        assert "razonamiento" in result.route_reason

    def test_no_provider_available(self):
        r = Router(providers={})
        with pytest.raises(NoProviderAvailable):
            r.route([{"role": "user", "content": "hola"}])

    def test_route_result_dataclass(self):
        result = RouteResult(provider="ollama", modelo="qwen2.5:7b", route_reason="keyword:rapido")
        assert result.provider == "ollama"
        assert result.modelo == "qwen2.5:7b"
        assert result.route_reason == "keyword:rapido"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class TestFileRead:
    def test_read_project_file(self):
        result = asyncio.run(file_read("pyproject.toml", max_lines=5))
        assert result["size"] >= 0

    def test_deny_outside_whitelist(self):
        result = asyncio.run(file_read("/etc/passwd"))
        assert "denegado" in result.get("error", "").lower()

    def test_file_not_found(self):
        result = asyncio.run(file_read("no_existe_12345.py"))
        assert "no encontrado" in result.get("error", "").lower()

    def test_tool_schemas_valid(self):
        for schema in TOOL_SCHEMAS:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]
            assert schema["function"]["name"] in ("web_search", "page_read", "file_read", "crawl_web")


# ---------------------------------------------------------------------------
# Server endpoints (using TestClient)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from core.mochila.mochila_server import app
    with TestClient(app) as c:
        yield c


class TestServer:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "ollama" in data["providers"]

    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "clasificador" in data
        assert "circuit_breaker" in data
        assert "tools_disponibles" in data
        assert data["tools_disponibles"] == 4

    def test_breaker(self, client):
        resp = client.get("/breaker")
        assert resp.status_code == 200
        data = resp.json()
        assert "ollama" in data
        assert data["ollama"]["state"] == "closed"

    def test_breaker_reset(self, client):
        resp = client.post("/breaker/reset/ollama")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_breaker_reset_unknown(self, client):
        resp = client.post("/breaker/reset/no_existe")
        assert resp.status_code == 404

    def test_metrics_rate(self, client):
        resp = client.get("/metrics/rate/ollama")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "ollama"

    def test_metrics_rate_unknown(self, client):
        resp = client.get("/metrics/rate/no_existe")
        assert resp.status_code == 404

    def test_metrics_cost(self, client):
        resp = client.get("/metrics/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data
        assert "total_tokens" in data

    def test_v1_models(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
