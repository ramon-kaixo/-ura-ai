"""Tests para RouterHandler (core/model_router/handler.py) via HTTP real.

Usa socketpair: el handler se construye sobre un socket y se le envían
peticiones HTTP crudas
la respuesta se lee del extremo opuesto.
"""

import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, ".")
from core.model_router.handler import RouterHandler


class _FakeRateLimiter:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    def is_allowed(self, client_ip: str) -> bool:
        return self._allowed


class _FakeCache:
    def __init__(self) -> None:
        self.cache: dict = {}
        self._hit: dict | None = None

    def set_hit(self, response: dict) -> None:
        self._hit = response

    def get(self, prompt: str, tipo: str) -> dict | None:
        return self._hit

    def set(self, prompt: str, tipo: str, response: dict) -> None:
        self.cache[prompt] = response


class _FakeMetrics:
    def __init__(self) -> None:
        self.metrics: dict[str, dict] = {}
        self.increments: list[tuple[str, dict]] = []

    def increment(self, name: str, tags: dict | None = None) -> None:
        self.increments.append((name, tags or {}))
        self.metrics.setdefault(name, {"count": 0})
        self.metrics[name]["count"] += 1

    def get_prometheus_format(self) -> str:
        return "router_requests_total 42\n"


class _Harness:
    def __init__(self) -> None:
        self.server_sock, self.client_sock = socket.socketpair()
        self.client_sock.settimeout(3)

    def request(self, raw: bytes) -> bytes:
        t = threading.Thread(target=self._run_handler, daemon=True)
        t.start()
        time.sleep(0.05)
        self.client_sock.sendall(raw)
        t.join(timeout=5)
        if t.is_alive():
            raise TimeoutError("handler colgado")
        resp = b""
        try:
            while True:
                chunk = self.client_sock.recv(65536)
                if not chunk:
                    break
                resp += chunk
        except TimeoutError:
            pass
        return resp

    def _run_handler(self) -> None:
        RouterHandler(self.server_sock, ("10.0.0.9", 40000), object())

    def get(self, path: str, extra_headers: bytes = b"") -> bytes:
        return self.request(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: test\r\nConnection: close\r\n" + extra_headers + b"\r\n")

    def post(self, path: str, body: bytes = b"") -> bytes:
        return self.request(
            b"POST "
            + path.encode()
            + b" HTTP/1.1\r\nHost: test\r\nConnection: close\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\n\r\n"
            + body
        )

    def close(self) -> None:
        self.server_sock.close()
        self.client_sock.close()


def _patch_metrics(monkeypatch) -> _FakeMetrics:
    """Parchea core.model_router.metrics.metrics via sys.modules.

    El string dotted falla porque core/model_router/__init__.py importa
    `from .metrics import metrics`, sombreando el submódulo con la instancia.
    """
    fake = _FakeMetrics()
    mod = sys.modules["core.model_router.metrics"]
    monkeypatch.setattr(mod, "metrics", fake)
    return fake


def _patch_vram_guard(monkeypatch, fake: object) -> None:
    """Igual que _patch_metrics para vram_guard (mismo shadowing)."""
    mod = sys.modules["core.model_router.vram_guard"]
    monkeypatch.setattr(mod, "vram_guard", fake)


def _extract_json(resp: bytes) -> dict:
    body = resp.split(b"\r\n\r\n", 1)[1]
    return __import__("json").loads(body)


def _status(resp: bytes) -> int:
    return int(resp.split(b"\r\n", 1)[0].split(b" ", 2)[1])


@pytest.fixture
def router_ctx(monkeypatch):
    """Fixtures comunes: rate limit abierto, modelos cacheados."""
    monkeypatch.setattr("core.model_router.router.rate_limiter", _FakeRateLimiter(True))
    monkeypatch.setattr(
        "core.model_router.model_selection.obtener_modelos_disponibles",
        lambda url=None: {"qwen3:32b", "qwen2.5:7b"},
    )
    RouterHandler._modelos_cache = {"qwen3:32b", "qwen2.5:7b"}
    RouterHandler._cache_ts = time.time()
    yield
    RouterHandler._modelos_cache = None
    RouterHandler._cache_ts = 0


@pytest.mark.timeout(60)
class TestRouterHandlerVersion:
    @pytest.mark.slow
    def test_api_version_json(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "ECO")
        monkeypatch.setattr("core.model_router.router.ROUTER_PORT", 11435)
        monkeypatch.setattr("core.model_router.router.get_ollama_url", lambda: "http://ollama:11434")
        monkeypatch.setattr(
            "core.model_router.model_selection.MODELO_ROUTES",
            {"razonamiento": {"modelos": ["qwen3:32b"], "descripcion": "Razonamiento"}},
        )
        h = _Harness()
        try:
            resp = h.get("/api/version")
            data = _extract_json(resp)
            assert data["service"] == "model_router"
            assert data["power_mode"] == "ECO"
            assert data["port"] == 11435
            assert "prompt_caching" in data["features"]
        finally:
            h.close()

    @pytest.mark.slow
    def test_root_redirects_to_version(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "AUTO")
        h = _Harness()
        try:
            data = _extract_json(h.get("/"))
            assert data["service"] == "model_router"
        finally:
            h.close()


class TestRouterHandlerHealth:
    @pytest.mark.slow
    def test_health_ok(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: False)
        monkeypatch.setattr("core.model_router.router.auth_validate", lambda k: True)
        monkeypatch.setattr("core.model_router.router.get_ollama_url", lambda: "http://ollama:11434")
        h = _Harness()
        try:
            resp = h.get("/health")
            data = _extract_json(resp)
            assert data["status"] == "ok"
            assert data["models_available"] == 2
            assert _status(resp) == 200
        finally:
            h.close()

    @pytest.mark.slow
    def test_health_degraded_when_no_models(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: False)
        monkeypatch.setattr(
            "core.model_router.model_selection.obtener_modelos_disponibles",
            lambda url=None: set(),
        )
        RouterHandler._modelos_cache = None
        RouterHandler._cache_ts = 0
        h = _Harness()
        try:
            resp = h.get("/health")
            data = _extract_json(resp)
            assert data["status"] == "degraded"
            assert _status(resp) == 503
        finally:
            h.close()

    @pytest.mark.slow
    def test_health_forbidden_without_key(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: True)
        monkeypatch.setattr("core.model_router.router.auth_validate", lambda k: False)
        h = _Harness()
        try:
            resp = h.get("/health")
            assert _status(resp) == 403
        finally:
            h.close()


class TestRouterHandlerMetrics:
    @pytest.mark.slow
    def test_metrics_prometheus_text(self, router_ctx, monkeypatch) -> None:
        _patch_metrics(monkeypatch)
        h = _Harness()
        try:
            resp = h.get("/metrics")
            assert b"router_requests_total 42" in resp
            assert b"text/plain" in resp
        finally:
            h.close()


class TestRouterHandlerRateLimit:
    @pytest.mark.slow
    def test_rate_limit_429(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.rate_limiter", _FakeRateLimiter(False))
        h = _Harness()
        try:
            resp = h.get("/api/version")
            data = _extract_json(resp)
            assert _status(resp) == 429
            assert "Rate limit" in data["error"]
        finally:
            h.close()

    @pytest.mark.slow
    def test_post_rate_limit_429(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.rate_limiter", _FakeRateLimiter(False))
        h = _Harness()
        try:
            resp = h.post("/v1/chat/completions", b'{"model":"auto"}')
            assert _status(resp) == 429
        finally:
            h.close()


class TestRouterHandlerProxy:
    @pytest.mark.slow
    def test_api_tags_proxied(self, router_ctx, monkeypatch) -> None:
        def fake_proxy(path, body, method, client_ip=None):
            return 200, {"Content-Type": "application/json"}, b'{"models": []}'

        monkeypatch.setattr("core.model_router.proxy.proxy_request", fake_proxy)
        h = _Harness()
        try:
            resp = h.get("/api/tags")
            assert b'{"models": []}' in resp
            assert _status(resp) == 200
        finally:
            h.close()

    @pytest.mark.slow
    def test_v1_unknown_path_proxied(self, router_ctx, monkeypatch) -> None:
        def fake_proxy(path, body, method, client_ip=None):
            assert path == "/v1/models"
            return 200, {"Content-Type": "application/json"}, b'{"object":"list"}'

        monkeypatch.setattr("core.model_router.proxy.proxy_request", fake_proxy)
        h = _Harness()
        try:
            resp = h.get("/v1/models")
            assert b'{"object":"list"}' in resp
        finally:
            h.close()


class TestRouterHandlerVRam:
    @pytest.mark.slow
    def test_vram_status(self, router_ctx) -> None:
        h = _Harness()
        try:
            data = _extract_json(h.get("/vram/status"))
            assert "slots_disponibles" in data
        finally:
            h.close()


class TestRouterHandlerSupervisor:
    @pytest.mark.slow
    def test_supervisor_error_path_when_zmq_fails(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: False)
        monkeypatch.setattr("core.model_router.router.auth_validate", lambda k: True)

        class _FailingZMQ:
            class Context:
                def socket(self, *a):
                    raise RuntimeError("zmq no disponible")

                def term(self):  # pragma: no cover
                    pass

        monkeypatch.setitem(sys.modules, "zmq", _FailingZMQ())
        h = _Harness()
        try:
            data = _extract_json(h.get("/supervisor"))
            assert data == {"error": "supervisor no accesible"}
        finally:
            h.close()

    @pytest.mark.slow
    def test_status_html_renders_empty_tasks(self, router_ctx, monkeypatch) -> None:
        class _FailingZMQ:
            class Context:
                def socket(self, *a):
                    raise RuntimeError("zmq no disponible")

                def term(self):  # pragma: no cover
                    pass

        monkeypatch.setitem(sys.modules, "zmq", _FailingZMQ())
        h = _Harness()
        try:
            resp = h.get("/status")
            assert b"URA System Status" in resp
            assert b"0/0" in resp
        finally:
            h.close()


class TestRouterHandlerSearch:
    @pytest.mark.slow
    def test_search_ok(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.search_engine.search", lambda q: [{"id": 1}])
        h = _Harness()
        try:
            data = _extract_json(h.get("/api/search?q=test"))
            assert data["total"] == 1
            assert data["results"] == [{"id": 1}]
        finally:
            h.close()

    @pytest.mark.slow
    def test_search_missing_q_400(self, router_ctx) -> None:
        h = _Harness()
        try:
            resp = h.get("/api/search")
            data = _extract_json(resp)
            assert _status(resp) == 400
            assert "parametro q requerido" in data["error"]
        finally:
            h.close()

    @pytest.mark.slow
    def test_search_engine_failure_degrades(self, router_ctx, monkeypatch) -> None:
        def boom(q):
            raise RuntimeError("fts caido")

        monkeypatch.setattr("core.search_engine.search", boom)
        h = _Harness()
        try:
            data = _extract_json(h.get("/api/search?q=x"))
            assert data["total"] == 0
        finally:
            h.close()


class TestRouterHandlerDashboard:
    @pytest.mark.slow
    def test_dashboard_html(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.dashboard._render_dashboard", lambda: "<html>dashboard</html>")
        h = _Harness()
        try:
            resp = h.get("/dashboard")
            assert b"<html>dashboard</html>" in resp
        finally:
            h.close()

    @pytest.mark.slow
    def test_dashboard_json(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.model_router.dashboard._dashboard_json",
            lambda client_ip="": '{"backend_label": "ASUS Remoto", "models": []}',
        )
        h = _Harness()
        try:
            data = _extract_json(h.get("/dashboard.json"))
            assert data["backend_label"] == "ASUS Remoto"
        finally:
            h.close()


class TestRouterHandlerPowerMode:
    @pytest.mark.slow
    def test_set_power_mode_query(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "AUTO")
        h = _Harness()
        try:
            data = _extract_json(h.post("/power_mode?mode=ECO"))
            assert data["power_mode"] == "ECO"
        finally:
            h.close()

    @pytest.mark.slow
    def test_set_power_mode_body(self, router_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "AUTO")
        h = _Harness()
        try:
            data = _extract_json(h.post("/power_mode", b"mode=TURBO"))
            assert data["power_mode"] == "TURBO"
        finally:
            h.close()

    @pytest.mark.slow
    def test_set_power_mode_invalid_400(self, router_ctx, monkeypatch) -> None:
        h = _Harness()
        try:
            resp = h.post("/power_mode", b"mode=LOCO")
            assert _status(resp) == 400
        finally:
            h.close()


class TestRouterHandlerPost:
    @pytest.mark.slow
    def test_post_cache_hit(self, router_ctx, monkeypatch) -> None:
        fake_cache = _FakeCache()
        fake_cache.set_hit({"choices": [{"message": {"content": "cached"}}]})
        monkeypatch.setattr("core.model_router.cache.prompt_cache", fake_cache)
        _patch_metrics(monkeypatch)
        h = _Harness()
        try:
            body = b'{"model":"auto","messages":[{"role":"user","content":"hola"}]}'
            data = _extract_json(h.post("/api/chat", body))
            assert data["choices"][0]["message"]["content"] == "cached"
        finally:
            h.close()

    @pytest.mark.slow
    def test_post_direct_model_selection(self, router_ctx, monkeypatch) -> None:
        _patch_metrics(monkeypatch)
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(
            "core.model_router.proxy._proxy_con_vram",
            lambda path, body, modelo=None, tipo=None, client_ip=None: (200, {"Content-Type": "application/json"}, b'{"ok":true}'),
        )
        monkeypatch.setattr("core.model_router.proxy._check_context_size", lambda x: {"level": "ok", "tokens": 10})
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        h = _Harness()
        try:
            body = b'{"model":"qwen3:32b","messages":[{"role":"user","content":"x"}]}'
            resp = h.post("/api/chat", body)
            assert b'{"ok":true}' in resp
        finally:
            h.close()

    @pytest.mark.slow
    def test_post_routed_when_model_unavailable(self, router_ctx, monkeypatch) -> None:
        _patch_metrics(monkeypatch)
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "qwen3:32b")
        monkeypatch.setattr(
            "core.model_router.proxy._proxy_con_vram",
            lambda path, body, modelo=None, tipo=None, client_ip=None: (200, {"Content-Type": "application/json"}, b'{"routed":true}'),
        )
        monkeypatch.setattr("core.model_router.proxy._check_context_size", lambda x: {"level": "ok", "tokens": 10})
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr("core.model_router.cache.prompt_cache", _FakeCache())
        h = _Harness()
        try:
            body = b'{"model":"modelo-inexistente","messages":[{"role":"user","content":"x"}]}'
            resp = h.post("/api/chat", body)
            assert b'{"routed":true}' in resp
        finally:
            h.close()

    @pytest.mark.slow
    def test_post_malformed_json_defaults(self, router_ctx, monkeypatch) -> None:
        _patch_metrics(monkeypatch)
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "qwen3:32b")
        monkeypatch.setattr(
            "core.model_router.proxy._proxy_con_vram",
            lambda path, body, modelo=None, tipo=None, client_ip=None: (200, {"Content-Type": "application/json"}, b'{"ok":true}'),
        )
        monkeypatch.setattr("core.model_router.proxy._check_context_size", lambda x: {"level": "ok", "tokens": 10})
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr("core.model_router.cache.prompt_cache", _FakeCache())
        h = _Harness()
        try:
            resp = h.post("/api/chat", b'{"not json')
            assert b'{"ok":true}' in resp
        finally:
            h.close()

    @pytest.mark.slow
    def test_post_context_critical_logged(self, router_ctx, monkeypatch) -> None:
        fake_metrics = _patch_metrics(monkeypatch)
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "qwen3:32b")
        monkeypatch.setattr(
            "core.model_router.proxy._proxy_con_vram",
            lambda path, body, modelo=None, tipo=None, client_ip=None: (200, {"Content-Type": "application/json"}, b'{"ok":true}'),
        )
        monkeypatch.setattr(
            "core.model_router.proxy._check_context_size",
            lambda x: {"level": "critical", "tokens": 999999, "message": "demasiado grande"},
        )
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr("core.model_router.cache.prompt_cache", _FakeCache())
        h = _Harness()
        try:
            h.post("/api/chat", b'{"model":"auto","messages":[{"role":"user","content":"x"}]}')
            assert any(name == "context_critical" for name, _ in fake_metrics.increments)
        finally:
            h.close()
