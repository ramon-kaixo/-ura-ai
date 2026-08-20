"""Cobertura 100x100 de motor/assistant/llm_bridge.py (TASK-20260820-005).

Cubre: LLMBridge — build_messages, select_model, generate, generate_async,
generate_stream, _do_generate, _local_generate, _messages_to_prompt.

Dependencias externas mockeadas: engine.get_context, router.generate,
motor.core.llm.generate, httpx, concurrent.futures.
"""

from __future__ import annotations

import concurrent.futures
import json
from unittest import mock

import pytest

from motor.assistant.llm_bridge import LLMBridge
from motor.assistant.models import ConversationMode, Message


class _Msg:
    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


class _FakeEngine:
    def __init__(self, messages: list[Message] | None = None) -> None:
        self.messages = messages or []

    def get_context(self, conversation_id: str) -> list[Message]:
        return self.messages


def _bridge(
    engine=None,
    router=None,
    fallback=None,
    timeout=None,
) -> LLMBridge:
    return LLMBridge(
        engine or _FakeEngine(),
        router=router,
        fallback_model=fallback,
        timeout_seconds=timeout,
    )


class TestBuildMessages:
    def test_sin_context_sin_system(self) -> None:
        b = _bridge()
        assert b.build_messages("c1", user_message="hola") == [{"role": "user", "content": "hola"}]

    def test_con_system_prompt(self) -> None:
        b = _bridge()
        msgs = b.build_messages("c1", system_prompt="sys", user_message="hola")
        assert msgs[0] == {"role": "system", "content": "sys"}
        assert msgs[1] == {"role": "user", "content": "hola"}

    def test_context_reverso_con_sistema(self) -> None:
        eng = _FakeEngine([_Msg("user", "m1"), _Msg("assistant", "a1"), _Msg("user", "m2")])
        b = _bridge(engine=eng)
        msgs = b.build_messages("c1", system_prompt="sys")
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user", "assistant", "user"]

    def test_context_sin_sistema(self) -> None:
        eng = _FakeEngine([_Msg("user", "m1"), _Msg("assistant", "a1")])
        b = _bridge(engine=eng)
        msgs = b.build_messages("c1")
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant"]

    def test_max_context_recorta(self) -> None:
        # cada mensaje cuesta len//4 + 1 tokens; con max_context=2 solo cabe 1
        eng = _FakeEngine([_Msg("user", "x" * 20), _Msg("user", "y" * 20)])
        b = _bridge(engine=eng)
        msgs = b.build_messages("c1", max_context=6)
        assert len(msgs) == 1

    def test_duplicado_user_no_append(self) -> None:
        eng = _FakeEngine([_Msg("user", "hola")])
        b = _bridge(engine=eng)
        msgs = b.build_messages("c1", user_message="hola")
        assert len(msgs) == 1

    def test_sin_context_user_append(self) -> None:
        b = _bridge()
        msgs = b.build_messages("c1", user_message="nuevo")
        assert msgs == [{"role": "user", "content": "nuevo"}]

    def test_sin_user_sin_context(self) -> None:
        b = _bridge()
        assert b.build_messages("c1") == []


class TestSelectModel:
    def test_explicacion_usa_fallback(self) -> None:
        b = _bridge(fallback="modelo-x")
        assert b.select_model(ConversationMode.EXPLANATION) == "modelo-x"

    def test_trabajo_usa_coder(self) -> None:
        b = _bridge()
        assert b.select_model(ConversationMode.WORK) == "qwen2.5-coder:14b"

    def test_intent_command_usa_7b(self) -> None:
        b = _bridge()
        assert b.select_model(ConversationMode.CONVERSATION, "command") == "qwen2.5:7b"

    def test_intent_search_usa_7b(self) -> None:
        b = _bridge()
        assert b.select_model(ConversationMode.CONVERSATION, "search") == "qwen2.5:7b"

    def test_default_usa_fallback(self) -> None:
        b = _bridge(fallback="modelo-y")
        assert b.select_model(ConversationMode.CONVERSATION, "otro") == "modelo-y"


class TestGenerate:
    def test_generate_con_router_ok(self) -> None:
        router = mock.Mock()
        router.generate.return_value = "respuesta del router"
        b = _bridge(router=router)
        r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "respuesta del router"
        router.generate.assert_called_once()

    def test_generate_router_error_fallback_local(self) -> None:
        router = mock.Mock()
        router.generate.side_effect = RuntimeError("boom")
        b = _bridge(router=router)
        with mock.patch("motor.assistant.llm_bridge.LLMBridge._local_generate", return_value="local-ok"):
            r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "local-ok"

    def test_generate_router_respuesta_error_local(self) -> None:
        router = mock.Mock()
        router.generate.return_value = "[Error algo"
        b = _bridge(router=router)
        with mock.patch("motor.assistant.llm_bridge.LLMBridge._local_generate", return_value="local-ok"):
            r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "local-ok"

    def test_generate_timeout(self) -> None:
        b = _bridge(timeout=1)
        with mock.patch.object(b, "_do_generate") as do_gen:
            do_gen.side_effect = concurrent.futures.TimeoutError
            r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert "no respondió" in r

    def test_generate_excepcion_hilo_fallback_local(self) -> None:
        b = _bridge(timeout=1)
        with (
            mock.patch.object(b, "_do_generate", side_effect=RuntimeError("boom")),
            mock.patch("motor.assistant.llm_bridge.LLMBridge._local_generate", return_value="local-ok"),
        ):
            r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "local-ok"

    def test_generate_sin_router_local(self) -> None:
        b = _bridge()
        with mock.patch("motor.assistant.llm_bridge.LLMBridge._local_generate", return_value="local-ok") as local:
            r = b.generate("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "local-ok"
        local.assert_called_once()

    def test_do_generate_router_ok(self) -> None:
        router = mock.Mock()
        router.generate.return_value = "respuesta"
        b = _bridge(router=router)
        r = b._do_generate([{"role": "user", "content": "hola"}], "m1")
        assert r == "respuesta"

    def test_do_generate_router_exc(self) -> None:
        router = mock.Mock()
        router.generate.side_effect = RuntimeError("boom")
        b = _bridge(router=router)
        with mock.patch.object(b, "_local_generate", return_value="local") as local:
            r = b._do_generate([{"role": "user", "content": "hola"}], "m1")
        assert r == "local"
        local.assert_called_once()

    def test_local_generate_ok(self) -> None:
        b = _bridge()
        with mock.patch("motor.core.llm.generate", return_value="core-ok") as core_gen:
            r = b._local_generate([{"role": "user", "content": "hola"}], "m1")
        assert r == "core-ok"
        core_gen.assert_called_once()

    def test_local_generate_error(self) -> None:
        b = _bridge()
        with mock.patch("motor.core.llm.generate", side_effect=RuntimeError("down")):
            r = b._local_generate([{"role": "user", "content": "hola"}], "m1")
        assert "Error al conectar" in r

    def test_messages_to_prompt(self) -> None:
        b = _bridge()
        p = b._messages_to_prompt(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "adiós"},
            ]
        )
        assert p == "System: sys\nUser: hola\nAssistant: adiós\nAssistant: "


class TestGenerateAsync:
    @pytest.mark.asyncio
    async def test_generate_async(self) -> None:
        b = _bridge()
        with mock.patch.object(b, "generate", return_value="ok") as gen:
            r = await b.generate_async("c1", "hola", ConversationMode.CONVERSATION)
        assert r == "ok"
        gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_stream_ok(self) -> None:
        lines = [
            "",
            json.dumps({"response": "", "done": False}),
            "no-json",
            json.dumps({"response": "hola", "done": False}),
            json.dumps({"response": " mundo", "done": True}),
        ]

        class FakeStreamResponse:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def aiter_lines(self):
                return _LineIter(lines)

        class _LineIter:
            def __init__(self, lines) -> None:
                self._lines = lines

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._lines:
                    return self._lines.pop(0)
                raise StopAsyncIteration

        class FakeClient:
            def __init__(self, *a, **k) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def stream(self, *a, **k):
                return FakeStreamResponse()

        fake_httpx = mock.MagicMock()
        fake_httpx.AsyncClient = FakeClient
        fake_httpx.Timeout = lambda t: t
        b = _bridge()
        with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
            tokens = []
            async for tok in b.generate_stream("c1", "hola", ConversationMode.CONVERSATION):
                tokens.append(tok)
        assert "hola" in tokens
        assert "hola mundo" in tokens

    @pytest.mark.asyncio
    async def test_generate_stream_sin_done(self) -> None:
        lines = [json.dumps({"response": "final", "done": False})]

        class _LineIter:
            def __init__(self, lines) -> None:
                self._lines = lines

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._lines:
                    return self._lines.pop(0)
                raise StopAsyncIteration

        class FakeStreamResponse:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def aiter_lines(self):
                return _LineIter(lines)

        class FakeClient:
            def __init__(self, *a, **k) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def stream(self, *a, **k):
                return FakeStreamResponse()

        fake_httpx = mock.MagicMock()
        fake_httpx.AsyncClient = FakeClient
        fake_httpx.Timeout = lambda t: t
        b = _bridge()
        with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
            tokens = []
            async for tok in b.generate_stream("c1", "hola", ConversationMode.CONVERSATION):
                tokens.append(tok)
        assert "final" in tokens
        assert tokens[-1] == "final"  # yield full final

    @pytest.mark.asyncio
    async def test_generate_stream_error(self) -> None:
        class FailClient:
            def __init__(self, *a, **k) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def stream(self, *a, **k):
                raise RuntimeError("down")

        fake_httpx = mock.MagicMock()
        fake_httpx.AsyncClient = FailClient
        fake_httpx.Timeout = lambda t: t
        b = _bridge()
        with mock.patch.dict("sys.modules", {"httpx": fake_httpx}):
            tokens = []
            async for tok in b.generate_stream("c1", "hola", ConversationMode.CONVERSATION):
                tokens.append(tok)
        assert any("[Error de streaming" in t for t in tokens)
