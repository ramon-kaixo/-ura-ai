"""Tests para infraestructura mochila: _state, helpers, adapter, interfaces, routes.

Cubre:
- core/mochila/_state.py: MochilaState dataclass + build_state()
- core/mochila/helpers.py: _procesar_usage
- core/mochila/adapter.py: _messages_to_prompt + _MotorChatAdapter
- core/interfaces/*: protocols runtime_checkable
- core/mochila/routes/: health, breaker, metrics
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from core.mochila._state import MochilaState, build_state
from core.mochila.adapter import _messages_to_prompt, _MotorChatAdapter
from core.mochila.helpers import _procesar_usage


class TestMochilaState:
    def test_dataclass_defaults(self) -> None:
        st = MochilaState(providers={}, provider_timeouts={})
        assert st.cache_models == []
        assert st.cache_models_ts == 0.0
        assert st.scheduler is None
        assert st.router is None
        assert st.circuit_breaker is None
        assert st.rate_limiter is None
        assert st.cost_tracker is None

    def test_build_state(self) -> None:
        st = build_state()
        assert set(st.providers) == {"ollama", "openrouter", "gemini"}
        assert st.provider_timeouts["ollama"] == 120.0
        assert st.provider_timeouts["openrouter"] == 60.0
        assert st.provider_timeouts["gemini"] == 30.0
        assert st.scheduler is not None
        assert st.router is not None
        assert st.circuit_breaker is not None
        assert st.rate_limiter is not None
        assert st.cost_tracker is not None
        assert all(hasattr(p, "chat") for p in st.providers.values())


class TestMessagesToPrompt:
    def test_roles_y_contenido_simple(self) -> None:
        msgs = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "mundo"}]
        assert _messages_to_prompt(msgs) == "<user>hola</user>\n<assistant>mundo</assistant>"

    def test_content_lista_texto(self) -> None:
        msgs = [
            {
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "image", "text": "ignorado"},
                    {"type": "text", "text": "b"},
                ]
            }
        ]
        assert _messages_to_prompt(msgs) == "<user>a\nb</user>"

    def test_content_lista_sin_text(self) -> None:
        msgs = [{"content": [{"type": "image", "url": "x"}]}]
        assert _messages_to_prompt(msgs) == "<user></user>"

    def test_sin_role_ni_content(self) -> None:
        assert _messages_to_prompt([{}]) == "<user></user>"


class TestMotorChatAdapter:
    def test_nombre(self) -> None:
        adapter = _MotorChatAdapter("ollama", mock.Mock())
        assert adapter.nombre == "ollama"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_chat_ok_no_stream_message_shape(self) -> None:
        provider = mock.Mock()
        provider.generate.return_value = "respuesta"
        adapter = _MotorChatAdapter("ollama", provider)
        out = [d async for d in adapter.chat("m1", [{"role": "user", "content": "hi"}])]
        assert len(out) == 1
        assert out[0]["model"] == "m1"
        choice = out[0]["choices"][0]
        assert choice["message"]["content"] == "respuesta"
        assert choice["finish_reason"] == "stop"
        assert out[0]["usage"]["total_tokens"] == 0
        provider.generate.assert_called_once_with("<user>hi</user>", "m1", {"temperature": 0.0, "num_predict": 4096})

    @pytest.mark.asyncio
    async def test_chat_stream_usa_generate_stream(self) -> None:
        provider = mock.Mock()
        provider.generate_stream.return_value = iter(["hola", "mundo"])
        adapter = _MotorChatAdapter("ollama", provider)
        out = [d async for d in adapter.chat("m1", [], stream=True, max_tokens=100, temperature=0.5)]
        deltas = [c["choices"][0]["delta"]["content"] for c in out if c["choices"][0]["delta"].get("content")]
        assert deltas == ["hola", "mundo"]
        assert out[-1]["choices"][0]["delta"] == {}
        assert out[-1]["choices"][0]["finish_reason"] == "stop"
        provider.generate_stream.assert_called_once_with("", "m1", {"temperature": 0.5, "num_predict": 100})

    @pytest.mark.asyncio
    async def test_chat_stream_degradado_sin_generate_stream(self) -> None:
        provider = mock.Mock()
        del provider.generate_stream
        provider.generate.return_value = "x"
        adapter = _MotorChatAdapter("ollama", provider)
        out = [d async for d in adapter.chat("m1", [], stream=True)]
        assert out[0]["choices"][0]["delta"]["content"] == "x"
        assert out[-1]["choices"][0]["delta"] == {}

    @pytest.mark.asyncio
    async def test_chat_tools_usa_chat_generate(self) -> None:
        provider = mock.Mock()
        provider.chat_generate.return_value = {
            "content": "",
            "tool_calls": [{"id": "call_0", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        adapter = _MotorChatAdapter("ollama", provider)
        out = [d async for d in adapter.chat("m1", [{"role": "user", "content": "q"}], tools=[{"t": 1}])]
        assert out[0]["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "f"
        assert out[0]["choices"][0]["finish_reason"] == "tool_calls"
        assert out[0]["usage"]["total_tokens"] == 8
        provider.chat_generate.assert_called_once()
        provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_error_string_motor_lanza_provider_error(self) -> None:
        from core.mochila.providers.base import ProviderError

        provider = mock.Mock()
        provider.generate.return_value = "Error: El servicio respondió con código 401."
        adapter = _MotorChatAdapter("ollama", provider)
        with pytest.raises(ProviderError) as exc_info:
            _ = [d async for d in adapter.chat("m1", [])]
        assert exc_info.value.status_code == 502
        assert exc_info.value.provider == "ollama"

    @pytest.mark.asyncio
    async def test_chat_provider_error(self) -> None:
        from core.mochila.providers.base import ProviderError

        provider = mock.Mock()
        provider.generate.side_effect = RuntimeError("boom")
        adapter = _MotorChatAdapter("ollama", provider)
        with pytest.raises(ProviderError):
            _ = [d async for d in adapter.chat("m1", [])]

    @pytest.mark.asyncio
    async def test_chat_provider_error_no_mensaje(self) -> None:
        from core.mochila.providers.base import ProviderError

        provider = mock.Mock()
        provider.generate.side_effect = ValueError()
        adapter = _MotorChatAdapter("ollama", provider)
        with pytest.raises(ProviderError):
            _ = [d async for d in adapter.chat("m1", [])]

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_health_delega(self) -> None:
        provider = mock.Mock()
        provider.health.return_value = {"ok": True}
        adapter = _MotorChatAdapter("ollama", provider)
        assert await adapter.health() == {"ok": True}


class TestProcesarUsage:
    def test_respuesta_con_usage(self) -> None:
        ct = mock.Mock()
        _procesar_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 5}}, "ollama", "m1", ct)
        ct.registrar.assert_called_once_with("ollama", "m1", 10, 5)

    @pytest.mark.slow
    def test_respuesta_sin_usage(self) -> None:
        ct = mock.Mock()
        _procesar_usage({"usage": None}, "ollama", "m1", ct)
        ct.registrar.assert_called_once_with("ollama", "m1", 0, 0)

    def test_respuesta_none(self) -> None:
        ct = mock.Mock()
        _procesar_usage(None, "ollama", "m1", ct)
        ct.registrar.assert_not_called()

    def test_usage_parcial(self) -> None:
        ct = mock.Mock()
        _procesar_usage({"usage": {"prompt_tokens": 7}}, "ollama", "m1", ct)
        ct.registrar.assert_called_once_with("ollama", "m1", 7, 0)


class TestInterfaces:
    """Protocols runtime_checkable: isinstance con objetos que cumplen el contrato."""

    def test_illm_client(self) -> None:
        from core.interfaces.llm import ILLMClient

        class Cliente:
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "ok"

            def health(self) -> dict:
                return {}

        assert isinstance(Cliente(), ILLMClient)

    def test_iexecutor(self) -> None:
        from core.interfaces.executor import IExecutor, IProcessResult

        class Resultado:
            ok = True
            returncode = 0
            stdout = ""
            stderr = ""
            duration_ms = 1.0
            timed_out = False
            error = ""

        class Ejecutor:
            def run(
                self, cmd: list[str], timeout: int = 30, cwd: str | None = None, env: dict | None = None
            ) -> Resultado:
                return Resultado()

        assert isinstance(Ejecutor(), IExecutor)
        assert isinstance(Resultado(), IProcessResult)

    def test_iconfig_provider(self) -> None:
        from core.interfaces.config import IConfigProvider

        campos = [
            "qdrant_host",
            "qdrant_port",
            "deploy_dir",
            "data_dir",
            "log_level",
            "ollama_host",
            "ollama_port",
            "ollama_model",
            "ollama_embedding_model",
            "ollama_timeout",
            "ollama_temperature",
            "ollama_max_tokens",
            "llm_provider",
            "is_vm",
            "asus_host",
            "asus_port",
            "tailscale_iface",
            "timer_interval_min",
            "failure_knowledge_path",
            "baseline_path",
            "auto_verify",
            "schema_version",
        ]
        Config = type("Config", (), dict.fromkeys(campos))
        assert isinstance(Config(), IConfigProvider)

    def test_ivector_store(self) -> None:
        from core.interfaces.repository import IVectorStore

        class Store:
            def guardar_incidente(self, incidente: dict) -> bool:
                return True

            def buscar_similares(self, vector: list[float], limite: int = 5) -> list[dict]:
                return []

        assert isinstance(Store(), IVectorStore)

    def test_isecret_store(self) -> None:
        from core.interfaces.secrets import ISecretStore

        class Store:
            def get_secret(self, name: str, default: str | None = None) -> str | None:
                return default

        assert isinstance(Store(), ISecretStore)


@pytest.fixture
def mochila_state() -> MochilaState:
    providers = {
        "ollama": mock.AsyncMock(),
        "gemini": mock.AsyncMock(),
    }
    providers["ollama"].health.return_value = {"ok": True}
    providers["gemini"].health.return_value = {"ok": True}
    st = MochilaState(
        providers=providers,
        provider_timeouts={"ollama": 120.0, "gemini": 30.0},
        circuit_breaker=SimpleNamespace(estado=lambda p: {"ok": True}, reset=lambda p: None),
        rate_limiter=SimpleNamespace(estado=lambda p: {"tokens": 10}),
        cost_tracker=SimpleNamespace(resumen_hoy=lambda: {"total": 0}),
        scheduler=mock.AsyncMock(),
    )
    return st


class TestRoutes:
    def test_health_router(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.health import create_health_router

        app = FastAPI()
        app.include_router(create_health_router(mochila_state))
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert set(data["providers"]) == {"ollama", "gemini"}

    def test_breaker_router_status(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.breaker import create_breaker_router

        app = FastAPI()
        app.include_router(create_breaker_router(mochila_state))
        client = TestClient(app)
        r = client.get("/breaker")
        assert r.status_code == 200
        assert r.json() == {"ollama": {"ok": True}, "gemini": {"ok": True}}

    def test_breaker_router_reset(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.breaker import create_breaker_router

        app = FastAPI()
        app.include_router(create_breaker_router(mochila_state))
        client = TestClient(app)
        r = client.post("/breaker/reset/ollama")
        assert r.status_code == 200
        assert r.json() == {"status": "reset", "provider": "ollama"}

    def test_breaker_router_reset_404(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.breaker import create_breaker_router

        app = FastAPI()
        app.include_router(create_breaker_router(mochila_state))
        client = TestClient(app)
        r = client.post("/breaker/reset/noexiste")
        assert r.status_code == 404

    def test_metrics_rate(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.metrics import create_metrics_router

        app = FastAPI()
        app.include_router(create_metrics_router(mochila_state))
        client = TestClient(app)
        r = client.get("/metrics/rate/ollama")
        assert r.status_code == 200
        assert r.json() == {"tokens": 10}

    def test_metrics_rate_404(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.metrics import create_metrics_router

        app = FastAPI()
        app.include_router(create_metrics_router(mochila_state))
        client = TestClient(app)
        r = client.get("/metrics/rate/nada")
        assert r.status_code == 404

    def test_metrics_cost(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.metrics import create_metrics_router

        app = FastAPI()
        app.include_router(create_metrics_router(mochila_state))
        client = TestClient(app)
        r = client.get("/metrics/cost")
        assert r.status_code == 200
        assert r.json() == {"total": 0}

    def test_metrics_acquire_vram(self, mochila_state: MochilaState) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.metrics import create_metrics_router

        app = FastAPI()
        app.include_router(create_metrics_router(mochila_state))
        client = TestClient(app)
        r = client.post("/admin/acquire_boot_vram", params={"mb": 512})
        assert r.status_code == 200
        assert r.json() == {"status": "granted"}
        mochila_state.scheduler.acquire_boot_vram.assert_awaited_once_with(512)
