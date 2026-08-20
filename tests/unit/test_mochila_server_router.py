"""Tests cobertura mochila_server — router/endpoints (split)."""
from __future__ import annotations

from pathlib import Path

from _mochila_helpers import (  # noqa: F401
    AsyncMock,
    FakeProvider,
    HTTPException,
    JSONResponse,
    MagicMock,
    Mock,
    client,
    httpx,
    ms,
    pytest,
    sys,
    tempfile,
    time,
)


class TestV1Models:
    def test_health_error_solo_auto(self, client, ms):  # noqa: F811
        class HealthErrorProvider(FakeProvider):
            async def health(self) -> dict:
                return {"status": "error"}

        ms.PROVIDERS["gemini"] = HealthErrorProvider("gemini")
        ms.CACHE_MODELS = []
        ms.CACHE_MODELS_TS = 0
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        ids = [m["id"] for m in resp.json()["data"]]
        assert "gemini/auto" in ids

    def test_health_ok_sin_modelos(self, client, ms):  # noqa: F811
        class SinModelos(FakeProvider):
            async def health(self) -> dict:
                return {"status": "ok"}

        ms.PROVIDERS["gemini"] = SinModelos("gemini")
        ms.CACHE_MODELS = []
        ms.CACHE_MODELS_TS = 0
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        ids = [m["id"] for m in resp.json()["data"]]
        assert "gemini/auto" in ids

    def test_cache_hit(self, client, ms):  # noqa: F811
        ms.CACHE_MODELS = [{"id": "ollama/auto", "provider": "ollama", "object": "model"}]
        ms.CACHE_MODELS_TS = time.time()
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        assert resp.json()["data"][0]["id"] == "ollama/auto"



class TestResolverRuta:
    async def test_no_provider_503(self, ms, monkeypatch):  # noqa: F811
        from core.mochila.mochila_server import ChatRequest
        from core.mochila.router import NoProviderAvailable

        def explota(*a, **k):
            raise NoProviderAvailable("nada")

        monkeypatch.setattr(ms.router, "route", explota)
        with pytest.raises(HTTPException) as excinfo:
            await ms._resolver_ruta(ChatRequest(model="auto", messages=[]))
        assert excinfo.value.status_code == 503



class TestToolCalls:
    def test_tool_calls_ok(self, client, ms, monkeypatch):  # noqa: F811

        class ToolProvider(FakeProvider):
            async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
                if not any(m.get("role") == "tool" for m in mensajes):
                    yield {
                        "id": "r1",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "function": {"name": "get_time", "arguments": '{"tz": "UTC"}'},
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                    }
                else:
                    yield {
                        "id": "r2",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "final"}}],
                        "usage": {"prompt_tokens": 6, "completion_tokens": 3},
                    }

        tool_mock = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(ms, "ejecutar_tool", tool_mock)
        ms.PROVIDERS["ollama"] = ToolProvider("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "que hora es"}], "tools": True},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200
            assert resp.json()["choices"][0]["message"]["content"] == "final"
            tool_mock.assert_awaited_once_with("get_time", {"tz": "UTC"})
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")

    def test_tool_call_arguments_invalidos(self, client, ms, monkeypatch):  # noqa: F811
        class ToolProvider(FakeProvider):
            async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
                if not any(m.get("role") == "tool" for m in mensajes):
                    yield {
                        "id": "r1",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "index": 2,
                                            "function": {"name": "get_time", "arguments": "{mal"},
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": None,
                    }
                else:
                    yield {
                        "id": "r2",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "final2"}}],
                        "usage": None,
                    }

        tool_mock = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(ms, "ejecutar_tool", tool_mock)
        ms.PROVIDERS["ollama"] = ToolProvider("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}], "tools": True},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200
            tool_mock.assert_awaited_once_with("get_time", {})
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")



class TestProxyGateway:
    def test_get_ok(self, client, ms, monkeypatch):  # noqa: F811
        async def fake_get(request, headers):
            return JSONResponse(content={"ok": True}, status_code=200)

        monkeypatch.setattr(ms, "_get_upstream", fake_get)
        resp = client.get("/api/foo", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_get_connect_error(self, client, ms, monkeypatch):  # noqa: F811
        async def fake_get(request, headers):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(ms, "_get_upstream", fake_get)
        resp = client.get("/api/foo", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 502

    def test_post_stream(self, client, ms, monkeypatch):  # noqa: F811
        async def fake_proxy_stream(request, body, headers, is_opencode, guardian, path):
            yield b'{"x": 1}\n'

        monkeypatch.setattr(ms, "_proxy_stream", fake_proxy_stream)
        resp = client.post(
            "/api/chat",
            json={"model": "llama3", "stream": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert b'"x": 1' in resp.content

    def test_post_stream_opencode_guardian(self, client, ms, monkeypatch):  # noqa: F811
        capturado: dict = {}

        async def fake_proxy_stream(request, body, headers, is_opencode, guardian, path):
            capturado["is_opencode"] = is_opencode
            capturado["guardian"] = guardian
            yield b'{"x": 2}\n'

        monkeypatch.setattr(ms, "_proxy_stream", fake_proxy_stream)
        resp = client.post(
            "/api/chat",
            json={"model": "opencode/llama3", "stream": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert capturado["is_opencode"] is True
        assert capturado["guardian"] is not None

    def test_post_no_stream(self, client, ms, monkeypatch):  # noqa: F811
        async def fake_post(request, body, headers):
            return JSONResponse(content={"ok": 2}, status_code=200)

        monkeypatch.setattr(ms, "_post_upstream", fake_post)
        resp = client.post(
            "/api/embed",
            json={"model": "m", "stream": False},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": 2}

    def test_vram_denegada(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "_adquirir_vram", AsyncMock(return_value=None))
        resp = client.post("/api/chat", json={"model": "m"}, headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 503
        assert "VRAM admission denied" in resp.json()["error"]



class TestAdquirirVram:
    async def test_con_modelo(self, ms):  # noqa: F811
        req = await ms._adquirir_vram({"model": "llama3"}, "chat")
        assert req == "req-1"
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "llama3"

    async def test_path_con_slash(self, ms):  # noqa: F811
        await ms._adquirir_vram(None, "api/chat")
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "api"

    async def test_path_sin_slash(self, ms):  # noqa: F811
        await ms._adquirir_vram(None, "single")
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "single"



class TestAdminVRAM:
    def test_acquire_boot_grant(self, client, ms):  # noqa: F811
        ms.scheduler.acquire_boot_vram = AsyncMock(return_value=True)
        resp = client.post("/admin/acquire_boot_vram?mb=100", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "granted"}



class TestMemoriaEndpoints:
    def test_analizar(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "analizar", AsyncMock(return_value={"resultado": "analizado"}))
        resp = client.post(
            "/memoria/analizar", json={"peticion": "x"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "analizado"

    def test_sintetizar(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "sintetizar", AsyncMock(return_value={"resultado": "sintesis"}))
        resp = client.post(
            "/memoria/sintetizar", json={"peticion": "x"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_saber(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "fase_saber", AsyncMock(return_value={"resultado": "saber"}))
        resp = client.post(
            "/memoria/fase/saber", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_hacer(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "fase_hacer", AsyncMock(return_value={"resultado": "hacer"}))
        resp = client.post(
            "/memoria/fase/hacer", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_comprar(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "fase_comprar", AsyncMock(return_value={"resultado": "comprar"}))
        resp = client.post(
            "/memoria/fase/comprar", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_vigilancia_parte(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "generar_parte", AsyncMock(return_value={"parte": "ok"}))
        resp = client.get("/memoria/vigilancia/parte", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200

    def test_consultar(self, client, ms, monkeypatch):  # noqa: F811
        spy = AsyncMock(return_value={"resultado": "q"})
        monkeypatch.setattr(ms, "memoria_consultar", spy)
        resp = client.post(
            "/memoria/consultar",
            json={"query": "pregunta", "forzar_web": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        spy.assert_awaited_once_with("pregunta", True)

    def test_ingestar(self, client, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "procesar_inbox_completo", AsyncMock(return_value={"ok": 1}))
        resp = client.post("/memoria/ingestar", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200

    def test_ingestar_video_404(self, client):  # noqa: F811
        resp = client.post(
            "/memoria/ingestar/video",
            json={"path": "/no/existe/ruta.mp4"},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 404

    def test_ingestar_video_ok(self, client):  # noqa: F811
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            resp = client.post(
                "/memoria/ingestar/video",
                json={"path": f.name},
                headers={"Authorization": "Bearer test-key"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stub"

    def test_memoria_health_ok(self, client, ms, monkeypatch):  # noqa: F811
        info = MagicMock()
        info.points_count = 42
        info.config.params.vectors = MagicMock()
        fake_client = MagicMock()
        fake_client.get_collection = Mock(return_value=info)
        monkeypatch.setattr("core.memoria.qdrant_store._get_client", lambda: fake_client)
        resp = client.get("/memoria/health", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["puntos"] == 42

    def test_memoria_health_error(self, client, ms, monkeypatch):  # noqa: F811
        def explota():
            raise RuntimeError("qdrant caido")

        monkeypatch.setattr("core.memoria.qdrant_store._get_client", explota)
        resp = client.get("/memoria/health", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"



class TestStatusEndpoint:
    def test_status_ok(self, client):  # noqa: F811
        resp = client.get("/status", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert "mochila" in resp.json()



class TestMotorV2:
    def test_branch_motor_v2(self, monkeypatch):
        import importlib.util

        ruta = Path(__file__).resolve().parents[2] / "core/mochila/mochila_server.py"
        spec = importlib.util.spec_from_file_location("mochila_server_v2_test", str(ruta))
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["mochila_server_v2_test"] = mod
        monkeypatch.setenv("URA_MOCHILA_MOTOR_V2", "1")
        spec.loader.exec_module(mod)
        assert mod._USAR_MOTOR_V2 is True
        assert sorted(mod.PROVIDERS) == ["gemini", "ollama", "openrouter"]
