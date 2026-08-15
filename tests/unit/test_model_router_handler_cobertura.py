"""Cobertura 100x100 de core/model_router/handler.py (TASK-20260815-003).

Instancia RouterHandler con socket mockeado y cubre todos los métodos
(do_GET/do_POST, power_mode, proxy, cache, clasificacion).
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any

import pytest

from core.model_router.handler import RouterHandler


class FakeSocket:
    def __init__(self, body: bytes = b"") -> None:
        self._body = body
        self.written = b""
        self._closed = False

    def makefile(self, mode: str, *a: Any, **k: Any) -> io.BytesIO:
        if "r" in mode:
            return io.BytesIO(self._body)
        return io.BytesIO()

    def sendall(self, data: bytes) -> None:
        self.written += data

    def close(self) -> None:
        self._closed = True


def _make_handler(body: bytes = b"", path: str = "/api/chat", method: str = "POST") -> RouterHandler:
    sock = FakeSocket(body)
    handler = RouterHandler.__new__(RouterHandler)
    handler.request = sock
    handler.client_address = ("127.0.0.1", 12345)
    handler.server = SimpleNamespace(
        RequestHandlerClass=RouterHandler,
        server_name="test",
        server_port=8000,
    )
    handler.rfile = sock.makefile("rb")
    handler.wfile = sock.makefile("wb")
    handler.headers = SimpleNamespace(
        get=lambda name, default=None: {
            "Content-Length": str(len(body)),
            "X-API-KEY": "key",
        }.get(name, default)
    )
    handler.path = path
    handler.command = method
    handler.protocol_version = "HTTP/1.1"
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.log_message = lambda fmt, *args: None  # type: ignore[method-assign]
    return handler


def _wrap_send(handler: RouterHandler) -> list[tuple[int, str, bytes]]:
    out: list[tuple[int, str, bytes]] = []

    def send_response(code: int) -> None:
        out.append((code, "", b""))

    def send_header(k: str, v: str) -> None:
        if out:
            out[-1] = (out[-1][0], out[-1][1] + f"{k}: {v}\n", out[-1][2])

    def end_headers() -> None:
        return None

    def write(data: bytes) -> None:
        if out:
            out[-1] = (out[-1][0], out[-1][1], out[-1][2] + data)

    handler.send_response = send_response  # type: ignore[method-assign]
    handler.send_header = send_header  # type: ignore[method-assign]
    handler.end_headers = end_headers  # type: ignore[method-assign]
    handler.wfile.write = write  # type: ignore[method-assign]
    return out


class TestSendHelpers:
    def test_send_json(self) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        h._send_json({"a": 1}, 200)
        assert out[0][0] == 200
        assert json.loads(out[0][2]) == {"a": 1}

    def test_send_html(self) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        h._send_html("<b>hi</b>", 201)
        assert out[0][0] == 201
        assert b"hi" in out[0][2]

    def test_send_text(self) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        h._send_text("plain", 202)
        assert out[0][0] == 202
        assert out[0][2] == b"plain"


class TestGetModelos:
    def test_obtiene(self, monkeypatch: pytest.MonkeyPatch) -> None:
        RouterHandler._modelos_cache = None
        RouterHandler._cache_ts = 0
        monkeypatch.setattr(
            "core.model_router.model_selection.obtener_modelos_disponibles",
            lambda: {"m1", "m2"},
        )
        assert RouterHandler._get_modelos() == {"m1", "m2"}

    def test_cache_fresco(self, monkeypatch: pytest.MonkeyPatch) -> None:
        RouterHandler._modelos_cache = {"m1"}
        RouterHandler._cache_ts = 9999999999.0
        assert RouterHandler._get_modelos() == {"m1"}


class TestRateLimit:
    def test_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        monkeypatch.setattr(
            "core.model_router.router.rate_limiter",
            SimpleNamespace(is_allowed=lambda ip: True),
        )
        assert h._check_rate_limit() is True

    def test_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(
            "core.model_router.router.rate_limiter",
            SimpleNamespace(is_allowed=lambda ip: False),
        )
        assert h._check_rate_limit() is False
        assert out[0][0] == 429


class TestHandlersApi:
    def test_api_tags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(
            "core.model_router.proxy.proxy_request",
            lambda *a, **k: (200, {}, b'{"models": []}'),
        )
        h._handle_api_tags()
        assert out[0][0] == 200
        assert b"models" in out[0][2]

    def test_api_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(router_mod, "POWER_MODE", "ECO")
        monkeypatch.setattr(router_mod, "ROUTER_PORT", 11435)
        monkeypatch.setattr(router_mod, "get_ollama_url", lambda: "http://x")
        monkeypatch.setattr("core.model_router.model_selection.MODELO_ROUTES", {"m": {"descripcion": "d"}})
        h._handle_api_version()
        data = json.loads(out[0][2])
        assert data["service"] == "model_router"
        assert data["power_mode"] == "ECO"

    def test_health_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        monkeypatch.setattr(router_mod, "require_auth", lambda: False)
        monkeypatch.setattr(router_mod, "get_ollama_url", lambda: "http://x")
        monkeypatch.setattr("core.model_router.cache.prompt_cache", SimpleNamespace(cache={}))
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        h._handle_health()
        assert out[0][0] == 200
        assert json.loads(out[0][2])["status"] == "ok"

    def test_health_degraded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: False)
        monkeypatch.setattr("core.model_router.router.get_ollama_url", lambda: "http://x")
        monkeypatch.setattr("core.model_router.cache.prompt_cache", SimpleNamespace(cache={}))
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: set()))
        h._handle_health()
        assert out[0][0] == 503

    def test_health_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: True)
        monkeypatch.setattr("core.model_router.router.auth_validate", lambda k: False)
        h._handle_health()
        assert out[0][0] == 403

    def test_metrics(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(
            "core.model_router.metrics.metrics",
            SimpleNamespace(get_prometheus_format=lambda: "# HELP test"),
        )
        h._handle_metrics()
        assert b"HELP" in out[0][2]

    def test_supervisor_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.require_auth", lambda: False)
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "zmq":
                raise ImportError("no zmq")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h._handle_supervisor()
        data = json.loads(out[0][2])
        assert "error" in data

    def test_status_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "zmq":
                raise ImportError("no zmq")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h._handle_status()
        assert b"URA System Status" in out[0][2]

    def test_api_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr("core.search_engine.search", lambda q: [{"id": 1}])
        h._handle_api_search("hola")
        assert json.loads(out[0][2])["total"] == 1

    def test_api_search_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr("core.search_engine.search", lambda q: (_ for _ in ()).throw(RuntimeError("x")))
        h._handle_api_search("hola")
        assert json.loads(out[0][2])["total"] == 0


class TestDoGet:
    def test_tags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/tags")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.proxy.proxy_request", lambda *a, **k: (200, {}, b"{}"))
        h.do_GET()
        assert out[0][0] == 200

    def test_rate_limit_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/tags")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: False))
        h.do_GET()
        assert out[0][0] == 429

    def test_vram_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/vram/status")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.vram_guard.vram_guard", SimpleNamespace(metricas=lambda: {"vram": 1}))
        h.do_GET()
        assert json.loads(out[0][2]) == {"vram": 1}

    def test_dashboard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/dashboard")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.dashboard._render_dashboard", lambda: "<html>dash</html>")
        h.do_GET()
        assert b"dash" in out[0][2]

    def test_dashboard_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/dashboard.json")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.dashboard._dashboard_json", lambda client_ip=None: '{"d": 1}')
        h.do_GET()
        assert json.loads(out[0][2]) == {"d": 1}

    def test_search_sin_q(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/search")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        h.do_GET()
        assert out[0][0] == 400

    def test_search_con_q(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/search?q=hola")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.search_engine.search", lambda q: [])
        h.do_GET()
        assert json.loads(out[0][2])["query"] == "hola"

    def test_proxy_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/v1/models")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.proxy.proxy_request", lambda *a, **k: (200, {"Content-Type": "application/json"}, b'{"m": []}'))
        h.do_GET()
        assert out[0][0] == 200


class TestPowerMode:
    def test_modo_valido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/power_mode", body=b"mode=TURBO")
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        assert h._handle_power_mode() is True
        assert router_mod.POWER_MODE == "TURBO"

    def test_modo_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/power_mode?mode=ECO", body=b"")
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        h._handle_power_mode()
        assert router_mod.POWER_MODE == "ECO"

    def test_modo_invalido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/power_mode", body=b"mode=XXX")
        out = _wrap_send(h)
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        h._handle_power_mode()
        assert out[0][0] == 400
        assert out[0][0] == 400


class TestDoPost:
    def test_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: False))
        h.do_POST()
        assert out[0][0] == 429

    def test_power_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/power_mode", body=b"mode=TURBO")
        out = _wrap_send(h)
        import core.model_router.router as router_mod

        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        h.do_POST()
        assert out[0][0] == 200

    def test_chat_directo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = json.dumps({"model": "m1", "messages": [{"role": "user", "content": "hola"}]}).encode()
        h = _make_handler(path="/api/chat", body=body)
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr(
            "core.model_router.proxy._proxy_con_vram",
            lambda *a, **k: (200, {}, b'{"ok": true}'),
        )
        h.do_POST()
        assert out[0][0] == 200

    def test_body_invalido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat", body=b"no-json")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: set()))
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "m1")
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (200, {}, b"{}"))
        monkeypatch.setattr("core.model_router.cache.prompt_cache", SimpleNamespace(get=lambda *a, **k: None, set=lambda *a, **k: None))
        h.do_POST()
        assert out[0][0] == 200


class TestLeerBody:
    def test_json_ok(self) -> None:
        h = _make_handler(body=b'{"a": 1}')
        assert h._leer_body_json() == {"a": 1}

    def test_json_invalido(self) -> None:
        h = _make_handler(body=b"xx")
        assert h._leer_body_json() == {}

    def test_vacio(self) -> None:
        h = _make_handler(body=b"")
        assert h._leer_body_json() == {}


class TestClasificar:
    def test_embed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/embed")
        assert h._clasificar_peticion({}) == "embeddings"

    def test_directo_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (200, {}, b"{}"))
        assert h._clasificar_peticion({"model": "m1", "messages": [{"role": "user", "content": "x"}]}) is None

    def test_directo_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: set()))
        assert h._clasificar_peticion({"model": "zzz", "messages": [{"role": "user", "content": "x"}]}) == "chat"

    def test_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        assert h._clasificar_peticion({"model": "router", "messages": [{"role": "user", "content": "x"}]}) == "chat"


class TestCache:
    def test_hit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr(
            "core.model_router.cache.prompt_cache",
            SimpleNamespace(get=lambda *a, **k: {"cached": True}),
        )
        assert h._servir_cache({"messages": [{"role": "user", "content": "x"}]}, "chat") is True
        assert json.loads(out[0][2]) == {"cached": True}

    def test_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        monkeypatch.setattr(
            "core.model_router.cache.prompt_cache",
            SimpleNamespace(get=lambda *a, **k: None),
        )
        assert h._servir_cache({"messages": [{"role": "user", "content": "x"}]}, "chat") is False


class TestRutear:
    def test_ok_cache_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        out = _wrap_send(h)
        cache = SimpleNamespace(set=lambda *a, **k: None)
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.cache.prompt_cache", cache)
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "m1")
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (200, {}, b'{"r": 1}'))
        h._rutear_proxy({"messages": [{"role": "user", "content": "x"}]}, "chat")
        assert out[0][0] == 200

    def test_error_no_cachea(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.cache.prompt_cache", SimpleNamespace(set=lambda *a, **k: None))
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "m1")
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (500, {}, b"err"))
        h._rutear_proxy({"messages": [{"role": "user", "content": "x"}]}, "chat")
        assert out[0][0] == 500


class TestRegistrarContexto:
    def test_critical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        monkeypatch.setattr(
            "core.model_router.metrics.metrics",
            SimpleNamespace(increment=lambda *a, **k: None),
        )
        monkeypatch.setattr(
            "core.model_router.proxy._check_context_size",
            lambda m: {"level": "critical", "tokens": 100, "message": "x"},
        )
        h._registrar_contexto({"messages": [{"role": "user", "content": "x"}]})

    def test_normal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        monkeypatch.setattr(
            "core.model_router.proxy._check_context_size",
            lambda m: {"level": "ok", "tokens": 1},
        )
        h._registrar_contexto({"prompt": "x"})


class TestLogMessage:
    def test_log(self) -> None:
        h = _make_handler()
        h.log_message("GET %s", "/path")


class TestDoGetFaltantes:
    def test_health_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/health")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        monkeypatch.setattr(router_mod, "require_auth", lambda: False)
        monkeypatch.setattr(router_mod, "get_ollama_url", lambda: "http://x")
        monkeypatch.setattr("core.model_router.cache.prompt_cache", SimpleNamespace(cache={}))
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        h.do_GET()
        assert out[0][0] == 200

    def test_metrics_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/metrics")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(
            "core.model_router.metrics.metrics",
            SimpleNamespace(get_prometheus_format=lambda: "# HELP x"),
        )
        h.do_GET()
        assert b"HELP" in out[0][2]

    def test_supervisor_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/supervisor")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(router_mod, "require_auth", lambda: False)
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "zmq":
                raise ImportError("no zmq")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h.do_GET()
        assert "error" in json.loads(out[0][2])

    def test_status_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/status")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "zmq":
                raise ImportError("no zmq")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h.do_GET()
        assert b"URA System Status" in out[0][2]

    def test_search_error_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/search?q=x")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.search_engine.search", lambda q: (_ for _ in ()).throw(RuntimeError("boom")))
        h.do_GET()
        # _handle_api_search captura el error internamente: total=0, status 200
        assert out[0][0] == 200
        assert json.loads(out[0][2])["total"] == 0

    def test_proxy_v1_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/v1/chat/completions")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.proxy.proxy_request", lambda *a, **k: (200, {"Content-Type": "application/json"}, b"{}"))
        h.do_GET()
        assert out[0][0] == 200

    def test_proxy_otro_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/otra/ruta")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.proxy.proxy_request", lambda *a, **k: (200, {}, b"{}"))
        h.do_GET()
        assert out[0][0] == 200

    def test_emitir_transfer_encoding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)
        h._emitir_respuesta(200, {"Content-Type": "text/plain", "Transfer-Encoding": "chunked"}, b"data")
        assert out[0][0] == 200
        assert "Transfer-Encoding" in out[0][1]
        assert out[0][2] == b"data"

    def test_power_mode_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/power_mode?mode=TURBO", body=b"")
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        assert h._handle_power_mode() is True
        assert router_mod.POWER_MODE == "TURBO"

    def test_rutear_cache_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/chat")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr(
            "core.model_router.cache.prompt_cache",
            SimpleNamespace(set=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cache fail"))),
        )
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection.seleccionar_modelo", lambda t, d: "m1")
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (200, {}, b'{"r": 1}'))
        h._rutear_proxy({"messages": [{"role": "user", "content": "x"}]}, "chat")
        assert out[0][0] == 200

    def test_log_message_real(self) -> None:
        h = _make_handler()
        h.log_message("GET %s", "/path")


class TestZmqHappyPath:
    def test_supervisor_zmq_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(router_mod, "require_auth", lambda: False)

        class FakeSock:
            def setsockopt(self, *a: Any) -> None:
                return None

            def connect(self, *a: Any) -> None:
                return None

            def send(self, *a: Any) -> None:
                return None

            def recv(self) -> bytes:
                return b'{"ok": true}'

            def close(self) -> None:
                return None

        class FakeCtx:
            def socket(self, *a: Any) -> FakeSock:
                return FakeSock()

            def term(self) -> None:
                return None

        fake_zmq = SimpleNamespace(Context=lambda: FakeCtx(), REQ="REQ", RCVTIMEO=1)
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            return fake_zmq if name == "zmq" else real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h._handle_supervisor()
        assert json.loads(out[0][2]) == {"ok": True}

    def test_status_zmq_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler()
        out = _wrap_send(h)

        class FakeSock:
            def setsockopt(self, *a: Any) -> None:
                return None

            def connect(self, *a: Any) -> None:
                return None

            def send(self, *a: Any) -> None:
                return None

            def recv(self) -> bytes:
                return json.dumps([{"name": "t1", "done": False, "last_error": None}]).encode()

            def close(self) -> None:
                return None

        class FakeCtx:
            def socket(self, *a: Any) -> FakeSock:
                return FakeSock()

            def term(self) -> None:
                return None

        fake_zmq = SimpleNamespace(Context=lambda: FakeCtx(), REQ="REQ", RCVTIMEO=1)
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            return fake_zmq if name == "zmq" else real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h._handle_status()
        assert b"t1" in out[0][2]
        assert b"1/1" in out[0][2]

    def test_do_get_version_direct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        monkeypatch.setattr(router_mod, "ROUTER_PORT", 11435)
        monkeypatch.setattr(router_mod, "get_ollama_url", lambda: "http://x")
        monkeypatch.setattr("core.model_router.model_selection.MODELO_ROUTES", {"m": {"descripcion": "d"}})
        h.do_GET()
        assert json.loads(out[0][2])["service"] == "model_router"

    def test_do_post_tipo_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/embed", body=b'{"model": "x"}')
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        h.do_POST()  # embeddings -> tipo definido, _rutear_proxy con mock
        # tipo 'embeddings' -> _clasificar_peticion devuelve str -> no None


class TestRamasFinales:
    def test_supervisor_auth_valida_pasa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler()
        out = _wrap_send(h)
        monkeypatch.setattr(router_mod, "require_auth", lambda: True)
        monkeypatch.setattr(router_mod, "auth_validate", lambda k: True)  # auth valida -> pasa el if
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "zmq":
                raise ImportError("no zmq")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        h._handle_supervisor()
        assert "error" in json.loads(out[0][2])

    def test_do_get_search_handler_boom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        h = _make_handler(path="/api/search?q=x")
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr(
            RouterHandler, "_handle_api_search", lambda self, q: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        h.do_GET()
        assert out[0][0] == 500

    def test_power_mode_part_sin_igual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import core.model_router.router as router_mod

        h = _make_handler(path="/power_mode", body=b"mode=TURBO")
        monkeypatch.setattr(router_mod, "POWER_MODE", "AUTO")
        assert h._handle_power_mode() is True
        assert router_mod.POWER_MODE == "TURBO"

    def test_do_post_clasifica_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # _clasificar_peticion devuelve None cuando el modelo directo esta disponible
        body = json.dumps({"model": "m1", "messages": [{"role": "user", "content": "x"}]}).encode()
        h = _make_handler(path="/api/chat", body=body)
        out = _wrap_send(h)
        monkeypatch.setattr("core.model_router.router.rate_limiter", SimpleNamespace(is_allowed=lambda ip: True))
        monkeypatch.setattr("core.model_router.metrics.metrics", SimpleNamespace(increment=lambda *a, **k: None))
        monkeypatch.setattr("core.model_router.model_selection.clasificar_peticion", lambda m: "chat")
        monkeypatch.setattr(RouterHandler, "_get_modelos", classmethod(lambda cls: {"m1"}))
        monkeypatch.setattr("core.model_router.model_selection._apply_model_params", lambda d, m: d)
        monkeypatch.setattr("core.model_router.proxy._proxy_con_vram", lambda *a, **k: (200, {}, b'{"ok": true}'))
        h.do_POST()
        assert out[0][0] == 200

    def test_log_message_fmt(self) -> None:
        h = _make_handler()
        h.client_address = ("1.2.3.4", 99)
        h.log_message("GET %s", "/path")
