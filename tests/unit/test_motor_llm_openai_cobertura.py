"""Cobertura 100x100 de motor/core/llm/openai.py (TASK-20260820-005).

Cubre las ramas restantes de OpenAIProvider:
- generate: timeout, HTTPStatusError, RequestError, excepción genérica
- generate_stream: status>=400, línea vacía/no-data, [DONE], JSON inválido,
  delta sin content, stream completo, error no capturado (RuntimeError)
- chat_generate: con/sin tools, status>=400
- embed: fallo batch -> reintento individual, error individual -> [0.0]*1536
- embed_async: fallo batch -> individual, error -> [0.0]*1536
- health: is_error, ok, excepción

Usa mock sobre el módulo (httpx global del módulo) y get_secret parcheado.
"""

from __future__ import annotations

from unittest import mock

import pytest

from motor.core.llm.openai import OpenAIProvider  # noqa: F401  (import sanity)

SECRETS = {
    "OPENAI_API_KEY": "secret-val",
    "OPENAI_BASE_URL": "https://example.com/v1",
    "OPENAI_MODEL": "mi-modelo",
    "OPENAI_EMBEDDING_MODEL": "mi-embed",
    "OPENAI_TIMEOUT": "60",
    "OPENAI_TEMPERATURE": "0.9",
    "OPENAI_MAX_TOKENS": "512",
}


@pytest.fixture()
def openai_mod():
    import motor.core.llm.openai

    return motor.core.llm.openai


@pytest.fixture()
def provider(openai_mod):
    def _get(name, default=None):
        return SECRETS.get(name, default)

    with mock.patch.object(openai_mod, "get_secret", side_effect=_get):
        return openai_mod.OpenAIProvider()


def _resp(status=200, json_body=None, text="", raise_for_status=True, is_error=None):
    r = mock.MagicMock()
    r.status_code = status
    r.json.return_value = json_body if json_body is not None else {}
    r.text = text
    r.raise_for_status.side_effect = (
        _http_status_error(status) if raise_for_status and status >= 400 else None
    )
    r.is_error = is_error if is_error is not None else status >= 400
    return r


def _http_status_error(status):
    from httpx import HTTPStatusError, Request

    return HTTPStatusError("err", request=Request("POST", "http://x"), response=mock.MagicMock(status_code=status))


def _stream_ctx(lines, status=200):
    class _Resp:
        def __init__(self) -> None:
            self.status_code = status
            self._lines = iter(lines)

        def iter_lines(self):
            return self._lines

    class _Ctx:
        def __init__(self) -> None:
            self._r = _Resp()

        def __enter__(self):
            return self._r

        def __exit__(self, *a):
            return None

    return _Ctx()


class TestGenerate:
    def test_ok(self, provider, openai_mod) -> None:
        body = {"choices": [{"message": {"content": "  hola  "}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            out = provider.generate("pregunta")
        assert out == "hola"
        m.assert_called_once()
        url = m.call_args.args[0]
        assert url == "https://example.com/v1/chat/completions"
        assert m.call_args.kwargs["json"]["model"] == "mi-modelo"
        assert m.call_args.kwargs["json"]["messages"] == [{"role": "user", "content": "pregunta"}]
        assert m.call_args.kwargs["json"]["temperature"] == 0.9

    def test_modelo_y_options_explicitas(self, provider, openai_mod) -> None:
        body = {"choices": [{"message": {"content": "x"}}]}
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            out = provider.generate("p", model="otro", options={"temperature": 0.1, "extra": 1})
        assert out == "x"
        assert m.call_args.kwargs["json"]["model"] == "otro"
        assert m.call_args.kwargs["json"]["temperature"] == 0.1
        assert m.call_args.kwargs["json"]["extra"] == 1

    def test_timeout(self, provider, openai_mod) -> None:
        from httpx import TimeoutException

        with mock.patch.object(openai_mod.httpx, "post", side_effect=TimeoutException("t")):
            out = provider.generate("p")
        assert "excedió" in out

    def test_http_status_error(self, provider, openai_mod) -> None:
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(429, raise_for_status=True)):
            out = provider.generate("p")
        assert "429" in out

    def test_request_error(self, provider, openai_mod) -> None:
        from httpx import RequestError

        with mock.patch.object(openai_mod.httpx, "post", side_effect=RequestError("conn")):
            out = provider.generate("p")
        assert "conectar" in out

    def test_error_generico(self, provider, openai_mod) -> None:
        with mock.patch.object(openai_mod.httpx, "post", side_effect=ValueError("boom")):
            out = provider.generate("p")
        assert "interno" in out


class TestGenerateStream:
    def test_stream_ok(self, provider, openai_mod) -> None:
        lines = [
            'data: {"choices": [{"delta": {"content": "hola"}}]}',
            'data: {"choices": [{"delta": {"content": " mundo"}}]}',
            "data: [DONE]",
        ]
        ctx = _stream_ctx(lines)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx):
            trozos = list(provider.generate_stream("p"))
        assert trozos == ["hola", " mundo"]

    def test_stream_linea_vacia_y_sin_data(self, provider, openai_mod) -> None:
        lines = [
            "",
            "no-data",
            'data: {"choices": [{"delta": {"content": "solo"}}]}',
            "data: [DONE]",
        ]
        ctx = _stream_ctx(lines)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx):
            trozos = list(provider.generate_stream("p"))
        assert trozos == ["solo"]

    def test_stream_json_invalido(self, provider, openai_mod) -> None:
        lines = [
            "data: no-es-json",
            'data: {"choices": [{"delta": {"content": "ok"}}]}',
            "data: [DONE]",
        ]
        ctx = _stream_ctx(lines)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx):
            trozos = list(provider.generate_stream("p"))
        assert trozos == ["ok"]

    def test_stream_delta_sin_content(self, provider, openai_mod) -> None:
        lines = [
            'data: {"choices": [{"delta": {"role": "assistant"}}]}',
            'data: {"choices": [{"delta": {"content": "a"}}]}',
            "data: [DONE]",
        ]
        ctx = _stream_ctx(lines)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx):
            trozos = list(provider.generate_stream("p"))
        assert trozos == ["a"]

    def test_stream_sin_done(self, provider, openai_mod) -> None:
        lines = [
            'data: {"choices": [{"delta": {"content": "fin"}}]}',
        ]
        ctx = _stream_ctx(lines)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx):
            trozos = list(provider.generate_stream("p"))
        assert trozos == ["fin"]

    def test_stream_status_error(self, provider, openai_mod) -> None:
        ctx = _stream_ctx([], status=500)
        with mock.patch.object(openai_mod.httpx, "stream", return_value=ctx), pytest.raises(RuntimeError):
            list(provider.generate_stream("p"))


class TestChatGenerate:
    def test_con_tools(self, provider, openai_mod) -> None:
        body = {
            "choices": [{"message": {"content": "resp", "tool_calls": [{"id": "1"}]}}],
            "usage": {"prompt_tokens": 1},
        }
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            out = provider.chat_generate([{"role": "user", "content": "h"}], tools=[{"type": "function"}])
        assert out["content"] == "resp"
        assert out["tool_calls"] == [{"id": "1"}]
        assert "tools" in m.call_args.kwargs["json"]

    def test_sin_tools(self, provider, openai_mod) -> None:
        body = {"choices": [{"message": {"content": "resp"}}]}
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            out = provider.chat_generate([{"role": "user", "content": "h"}])
        assert out["content"] == "resp"
        assert "tools" not in m.call_args.kwargs["json"]

    def test_status_error(self, provider, openai_mod) -> None:
        with (
            mock.patch.object(openai_mod.httpx, "post", return_value=_resp(500, raise_for_status=False)),
            pytest.raises(RuntimeError),
        ):
            provider.chat_generate([{"role": "user", "content": "h"}])


class TestEmbed:
    def test_ok(self, provider, openai_mod) -> None:
        body = {"data": [{"embedding": [0.1, 0.2]}]}
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            out = provider.embed(["txt1"])
        assert out == [[0.1, 0.2]]
        assert m.call_args.kwargs["json"]["model"] == "mi-embed"

    def test_fallo_batch_reintento_individual_ok(self, provider, openai_mod) -> None:
        body = {"data": [{"embedding": [0.5]}]}
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=[_resp(500, raise_for_status=True), _resp(200, body), _resp(200, body)]
        ):
            out = provider.embed(["a", "b"])
        assert out == [[0.5], [0.5]]

    def test_fallo_batch_y_individual(self, provider, openai_mod) -> None:
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=[_resp(500, raise_for_status=True), _resp(500, raise_for_status=True)]
        ):
            out = provider.embed(["a"])
        assert out == [[0.0] * 1536]

    def test_fallo_batch_con_modelo_distinto(self, provider, openai_mod) -> None:
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=[_resp(500, raise_for_status=True), _resp(500, raise_for_status=True)]
        ):
            out = provider.embed(["a"], model="otro-embed")
        # modelo != embedding_model -> no loguea warning; reintenta individual y falla
        assert out == [[0.0] * 1536]

    def test_modelo_explicito(self, provider, openai_mod) -> None:
        body = {"data": [{"embedding": [1.0]}]}
        with mock.patch.object(openai_mod.httpx, "post", return_value=_resp(200, body)) as m:
            provider.embed(["a"], model="otro-embed")
        assert m.call_args.kwargs["json"]["model"] == "otro-embed"


class TestEmbedAsync:
    @pytest.mark.asyncio
    async def test_ok(self, provider, openai_mod) -> None:
        resp = mock.MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"data": [{"embedding": [0.1]}]}
        client = mock.MagicMock()
        client.post = mock.AsyncMock(return_value=resp)
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        with mock.patch.object(openai_mod.httpx, "AsyncClient", return_value=client):
            out = await provider.embed_async(["txt"])
        assert out == [[0.1]]

    @pytest.mark.asyncio
    async def test_fallo_batch_reintento_ok(self, provider, openai_mod) -> None:
        bad = mock.MagicMock()
        bad.raise_for_status.side_effect = RuntimeError("down")
        good = mock.MagicMock()
        good.raise_for_status.return_value = None
        good.json.return_value = {"data": [{"embedding": [0.9]}]}

        class _Client:
            def __init__(self) -> None:
                self._i = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, *a, **k):
                self._i += 1
                return bad if self._i == 1 else good

        client = _Client()
        with mock.patch.object(openai_mod.httpx, "AsyncClient", return_value=client):
            out = await provider.embed_async(["a", "b"])
        assert out == [[0.9], [0.9]]

    @pytest.mark.asyncio
    async def test_fallo_batch_y_individual(self, provider, openai_mod) -> None:
        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, *a, **k):
                raise RuntimeError("down")

        with mock.patch.object(openai_mod.httpx, "AsyncClient", return_value=_Client()):
            out = await provider.embed_async(["a"])
        assert out == [[0.0] * 1536]


class TestHealth:
    def test_ok(self, provider, openai_mod) -> None:
        resp = mock.MagicMock()
        resp.is_error = False
        resp.json.return_value = {"data": [{"id": "m1"}, {"id": "m2"}]}
        with mock.patch.object(openai_mod.httpx, "get", return_value=resp):
            out = provider.health()
        assert out["status"] == "ok"
        assert out["modelos_disponibles"] == ["m1", "m2"]
        assert out["provider"] == "openai"

    def test_is_error(self, provider, openai_mod) -> None:
        resp = mock.MagicMock()
        resp.is_error = True
        resp.status_code = 401
        resp.text = "no auth"
        with mock.patch.object(openai_mod.httpx, "get", return_value=resp):
            out = provider.health()
        assert out["status"] == "error"
        assert "no auth" in out["detail"]

    def test_excepcion(self, provider, openai_mod) -> None:
        with mock.patch.object(openai_mod.httpx, "get", side_effect=RuntimeError("net")):
            out = provider.health()
        assert out["status"] == "error"
        assert "net" in out["detail"]
