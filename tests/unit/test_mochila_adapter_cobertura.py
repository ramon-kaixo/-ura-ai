"""Cobertura 100x100 de core/mochila/adapter.py (TASK-20260815-003).

Cubre el adaptador de paridad v1 (motor.core.llm v2 -> contrato mochila v1):
_MotorChatAdapter (chat/stream/no_stream/health), _messages_to_prompt,
_extraer_tool_call, _next_trozo, _chunk_delta, _chunk_fin. Usa providers
falsos (no httpx: el adaptador no toca red, delega en el provider inyectado).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.mochila import adapter as adapter_mod
from core.mochila.adapter import (
    _FIN_ITER,
    _chunk_delta,
    _chunk_fin,
    _extraer_tool_call,
    _messages_to_prompt,
    _MotorChatAdapter,
    _next_trozo,
)
from core.mochila.providers.base import ProviderError


class FakeProvider:
    """Provider falso sincrono (se invoca via run_in_executor)."""

    def __init__(
        self,
        *,
        timeout: int | None = None,
        generate_result: Any = "texto",
        chat_generate_result: dict | None = None,
        stream_sequence: list[str] | None = None,
        error: Exception | None = None,
        provider_error: bool = False,
        health_result: dict | None = None,
    ) -> None:
        self._timeout = timeout
        self._generate_result = generate_result
        self._chat_generate_result = chat_generate_result
        self._stream_sequence = stream_sequence
        if stream_sequence is not None:
            self.generate_stream = self._generar_stream  # type: ignore[assignment]
        self._error = error
        self._provider_error = provider_error
        self._health_result = health_result or {"ok": True}
        self.generates: list[tuple] = []
        self.chat_generates: list[tuple] = []
        self.stream_calls = 0

    def generate(self, prompt: str, modelo: str, options: dict) -> Any:
        self.generates.append((prompt, modelo, options))
        if self._error is not None:
            raise self._error
        return self._generate_result

    def chat_generate(self, mensajes: list, modelo: str, tools: list, options: dict) -> dict:
        self.chat_generates.append((mensajes, modelo, tools, options))
        if self._error is not None:
            raise self._error
        return self._chat_generate_result or {}

    def _generar_stream(self, prompt: str, modelo: str, options: dict):
        return iter(self._stream_sequence or [])

    def health(self) -> dict:
        return self._health_result


# ---------------------------------------------------------------------------
# _messages_to_prompt
# ---------------------------------------------------------------------------


class TestMessagesToPrompt:
    def test_content_str(self) -> None:
        prompt = _messages_to_prompt([{"role": "user", "content": "hola"}])
        assert prompt == "<user>hola</user>"

    def test_role_default_user(self) -> None:
        prompt = _messages_to_prompt([{"content": "sin rol"}])
        assert prompt == "<user>sin rol</user>"

    def test_content_list_filtra_texto(self) -> None:
        mensajes = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "uno"},
                    {"type": "image", "text": "no"},
                    {"type": "text", "text": "dos"},
                ],
            }
        ]
        assert _messages_to_prompt(mensajes) == "<assistant>uno\ndos</assistant>"

    def test_varios_mensajes(self) -> None:
        prompt = _messages_to_prompt([{"role": "a", "content": "1"}, {"role": "b", "content": "2"}])
        assert prompt == "<a>1</a>\n<b>2</b>"

    def test_content_ausente(self) -> None:
        assert _messages_to_prompt([{"role": "user"}]) == "<user></user>"


# ---------------------------------------------------------------------------
# _extraer_tool_call
# ---------------------------------------------------------------------------


class TestExtraerToolCall:
    def test_json_valido_args_str(self) -> None:
        calls = _extraer_tool_call(json.dumps({"name": "f", "arguments": '{"x": 1}'}))
        assert calls is not None
        assert calls[0]["id"] == "call_0"
        assert calls[0]["type"] == "function"
        assert calls[0]["function"]["name"] == "f"
        assert calls[0]["function"]["arguments"] == '{"x": 1}'

    def test_json_valido_args_dict(self) -> None:
        calls = _extraer_tool_call(json.dumps({"name": "f", "arguments": {"x": 1}}, ensure_ascii=False))
        assert calls is not None
        assert json.loads(calls[0]["function"]["arguments"]) == {"x": 1}

    def test_json_invalido(self) -> None:
        assert _extraer_tool_call("no-json{") is None

    def test_content_no_str(self) -> None:
        assert _extraer_tool_call(None) is None
        assert _extraer_tool_call({"a": 1}) is None

    def test_dict_sin_name_o_arguments(self) -> None:
        assert _extraer_tool_call('{"name": "f"}') is None
        assert _extraer_tool_call('{"arguments": "{}"}') is None
        assert _extraer_tool_call('{"otra": "cosa"}') is None

    def test_typeerror_en_json_loads(self, monkeypatch) -> None:
        def _explota(_s: str):
            raise TypeError("boom")

        monkeypatch.setattr(adapter_mod.json, "loads", _explota)
        assert _extraer_tool_call('{"name": "f", "arguments": "{}"}') is None


# ---------------------------------------------------------------------------
# _next_trozo
# ---------------------------------------------------------------------------


class TestNextTrozo:
    def test_retorna_elemento(self) -> None:
        assert _next_trozo(iter([1, 2])) == 1

    def test_stop_iteration(self) -> None:
        assert _next_trozo(iter([])) is _FIN_ITER


# ---------------------------------------------------------------------------
# _chunk_delta / _chunk_fin
# ---------------------------------------------------------------------------


class TestChunks:
    def test_chunk_delta(self) -> None:
        c = _chunk_delta("m1", {"content": "x"}, None)
        assert c["object"] == "chat.completion.chunk"
        assert c["model"] == "m1"
        assert c["choices"][0]["delta"] == {"content": "x"}
        assert c["choices"][0]["finish_reason"] is None
        assert c["id"].startswith("mochila-")

    def test_chunk_delta_con_finish(self) -> None:
        c = _chunk_delta("m1", {}, "stop")
        assert c["choices"][0]["finish_reason"] == "stop"

    def test_chunk_fin_sin_usage(self) -> None:
        c = _chunk_fin("m1", {})
        assert c["choices"][0]["delta"] == {}
        assert c["choices"][0]["finish_reason"] == "stop"
        assert c["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_chunk_fin_con_usage(self) -> None:
        c = _chunk_fin("m1", {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8})
        assert c["usage"]["prompt_tokens"] == 3
        assert c["usage"]["completion_tokens"] == 5
        assert c["usage"]["total_tokens"] == 8

    def test_chunk_fin_usage_parcial(self) -> None:
        c = _chunk_fin("m1", {"prompt_tokens": 1})
        assert c["usage"]["completion_tokens"] == 0


# ---------------------------------------------------------------------------
# _MotorChatAdapter: propiedades
# ---------------------------------------------------------------------------


class TestAdapterPropiedades:
    def test_nombre(self) -> None:
        a = _MotorChatAdapter("prov", FakeProvider())
        assert a.nombre == "prov"

    def test_timeout_con_atributo(self) -> None:
        a = _MotorChatAdapter("prov", FakeProvider(timeout=42))
        assert a.timeout == 42

    def test_timeout_sin_atributo_default_60(self) -> None:
        class SinTimeout:
            pass

        a = _MotorChatAdapter("prov", SinTimeout())
        assert a.timeout == 60

    async def test_health(self) -> None:
        a = _MotorChatAdapter("prov", FakeProvider(health_result={"ok": False}))
        assert await a.health() == {"ok": False}


# ---------------------------------------------------------------------------
# _MotorChatAdapter: chat() no-stream
# ---------------------------------------------------------------------------


class TestChatNoStream:
    async def test_no_stream_yield_respuesta(self) -> None:
        provider = FakeProvider(generate_result="respuesta")
        a = _MotorChatAdapter("prov", provider)
        resultado = [item async for item in a.chat("modelo", [{"content": "q"}])]
        assert len(resultado) == 1
        r = resultado[0]
        assert r["object"] == "chat.completion"
        assert r["model"] == "modelo"
        assert r["choices"][0]["message"]["content"] == "respuesta"
        assert r["choices"][0]["finish_reason"] == "stop"
        assert r["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        assert provider.generates[0][0] == "<user>q</user>"
        assert provider.generates[0][2] == {"temperature": 0.0, "num_predict": 4096}

    async def test_no_stream_texto_error(self) -> None:
        a = _MotorChatAdapter("prov", FakeProvider(generate_result="Error: boom"))
        with pytest.raises(ProviderError) as ei:
            await anext(a.chat("m", [{"content": "q"}]))
        assert ei.value.status_code == 502
        assert ei.value.provider == "prov"

    async def test_no_stream_texto_no_str(self) -> None:
        provider = FakeProvider(generate_result={"no": "str"})
        a = _MotorChatAdapter("prov", provider)
        r = await anext(a.chat("m", [{"content": "q"}]))
        assert r["choices"][0]["message"]["content"] == {"no": "str"}

    async def test_no_stream_con_tools_chat_generate(self) -> None:
        provider = FakeProvider(
            chat_generate_result={
                "content": "llamando",
                "tool_calls": [{"name": "t"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        )
        a = _MotorChatAdapter("prov", provider)
        r = await anext(a.chat("m", [{"content": "q"}], tools=[{"x": 1}]))
        assert r["choices"][0]["message"]["content"] == "llamando"
        assert r["choices"][0]["message"]["tool_calls"] == [{"name": "t"}]
        assert r["choices"][0]["finish_reason"] == "tool_calls"
        assert r["usage"] == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
        assert provider.chat_generates[0][2] == [{"x": 1}]

    async def test_no_stream_tools_sin_tool_calls(self) -> None:
        provider = FakeProvider(chat_generate_result={"content": "sin tools"})
        a = _MotorChatAdapter("prov", provider)
        r = await anext(a.chat("m", [{"content": "q"}], tools=[{"x": 1}]))
        assert "tool_calls" not in r["choices"][0]["message"]
        assert r["choices"][0]["finish_reason"] == "stop"

    async def test_no_stream_provider_error_propaga(self) -> None:
        provider = FakeProvider(
            provider_error=True,
            chat_generate_result={"content": "x"},
        )
        provider.chat_generate = lambda *a, **k: (_ for _ in ()).throw(  # type: ignore[assignment]
            ProviderError("rechazado", provider="prov", status_code=429)
        )
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            await anext(a.chat("m", [{"content": "q"}], tools=[{"x": 1}]))
        assert ei.value.status_code == 429

    async def test_no_stream_excepcion_generica(self) -> None:
        provider = FakeProvider(error=ValueError("muy mal"))
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            await anext(a.chat("m", [{"content": "q"}]))
        assert ei.value.status_code == 502
        assert "muy mal" in str(ei.value)

    async def test_no_stream_excepcion_generica_en_chat_generate(self) -> None:
        provider = FakeProvider(error=RuntimeError("r"), chat_generate_result={})
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            await anext(a.chat("m", [{"content": "q"}], tools=[{"x": 1}]))
        assert ei.value.status_code == 502

    async def test_temperature_y_max_tokens(self) -> None:
        provider = FakeProvider(generate_result="r")
        a = _MotorChatAdapter("prov", provider)
        await anext(a.chat("m", [{"content": "q"}], max_tokens=100, temperature=0.7))
        assert provider.generates[0][2] == {"temperature": 0.7, "num_predict": 100}

    async def test_tool_call_desde_texto(self) -> None:
        contenido = json.dumps({"name": "buscar", "arguments": {"q": "x"}}, ensure_ascii=False)
        a = _MotorChatAdapter("prov", FakeProvider(generate_result=contenido))
        r = await anext(a.chat("m", [{"content": "q"}]))
        assert r["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "buscar"
        assert r["choices"][0]["finish_reason"] == "tool_calls"


# ---------------------------------------------------------------------------
# _MotorChatAdapter: chat() stream
# ---------------------------------------------------------------------------


class TestChatStream:
    async def test_stream_con_chat_generate(self) -> None:
        provider = FakeProvider(chat_generate_result={"content": "hola", "usage": {"prompt_tokens": 2}})
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True, tools=[{"x": 1}])]
        assert len(items) == 2
        assert items[0]["choices"][0]["delta"]["content"] == "hola"
        assert items[1]["choices"][0]["delta"] == {}
        assert items[1]["choices"][0]["finish_reason"] == "stop"
        assert items[1]["usage"]["prompt_tokens"] == 2

    async def test_stream_con_chat_generate_content_vacio(self) -> None:
        provider = FakeProvider(chat_generate_result={"content": ""})
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True, tools=[{"x": 1}])]
        assert len(items) == 1
        assert items[0]["choices"][0]["delta"] == {}

    async def test_stream_con_generate_stream(self) -> None:
        provider = FakeProvider(stream_sequence=["a", "", "b"])
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True)]
        assert hasattr(provider, "generate_stream")
        deltas = [i["choices"][0]["delta"].get("content") for i in items]
        assert deltas == ["a", "b", None]

    async def test_stream_generate_stream_vacio(self) -> None:
        provider = FakeProvider(stream_sequence=[])
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True)]
        assert len(items) == 1
        assert items[0]["choices"][0]["delta"] == {}
        assert items[0]["choices"][0]["finish_reason"] == "stop"

    async def test_stream_degradado_a_generate(self) -> None:
        provider = FakeProvider(generate_result="respuesta larga")
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True)]
        assert len(items) == 2
        assert items[0]["choices"][0]["delta"]["content"] == "respuesta larga"

    async def test_stream_degradado_texto_vacio(self) -> None:
        provider = FakeProvider(generate_result="")
        a = _MotorChatAdapter("prov", provider)
        items = [i async for i in a.chat("m", [{"content": "q"}], stream=True)]
        assert len(items) == 1
        assert items[0]["choices"][0]["delta"] == {}

    async def test_stream_degradado_error(self) -> None:
        provider = FakeProvider(generate_result="Error: mal")
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            async for _ in a.chat("m", [{"content": "q"}], stream=True):
                pass
        assert ei.value.status_code == 502

    async def test_stream_provider_error_propaga(self) -> None:
        provider = FakeProvider(stream_sequence=["x"])
        provider.generate_stream = lambda *a, **k: (_ for _ in ()).throw(  # type: ignore[assignment]
            ProviderError("stream roto", provider="prov", status_code=500)
        )
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            async for _ in a.chat("m", [{"content": "q"}], stream=True):
                pass
        assert ei.value.status_code == 500

    async def test_stream_excepcion_generica(self) -> None:
        provider = FakeProvider(stream_sequence=["x"])
        provider.generate_stream = lambda *a, **k: (_ for _ in ()).throw(  # type: ignore[assignment]
            ValueError("v")
        )
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            async for _ in a.chat("m", [{"content": "q"}], stream=True):
                pass
        assert ei.value.status_code == 502

    async def test_stream_error_en_trozos(self) -> None:
        def _gen():
            yield "a"
            raise ValueError("a mitad")

        provider = FakeProvider()
        provider.generate_stream = lambda *a, **k: _gen()  # type: ignore[assignment]
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            async for _ in a.chat("m", [{"content": "q"}], stream=True):
                pass
        assert ei.value.status_code == 502

    async def test_stream_error_en_chat_generate(self) -> None:
        provider = FakeProvider(chat_generate_result={}, error=ValueError("cg"))
        a = _MotorChatAdapter("prov", provider)
        with pytest.raises(ProviderError) as ei:
            async for _ in a.chat("m", [{"content": "q"}], stream=True, tools=[{"x": 1}]):
                pass
        assert ei.value.status_code == 502
