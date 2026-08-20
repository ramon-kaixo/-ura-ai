"""Tests cobertura mochila_server — lifespan/guardian/stream (split)."""
from __future__ import annotations

from _mochila_helpers import FakeProvider, HTTPException, Mock, TestClient, ms, pytest  # noqa: F401


class TestLifespan:
    def test_lifespan_arranca_y_cierra(self, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr(ms, "init_guardian", lambda: None)

        class ConAenter:
            def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            async def health(self) -> dict:
                return {"status": "ok"}

        ms.PROVIDERS["extra"] = ConAenter()
        try:
            with TestClient(ms.app) as c:
                resp = c.get("/health")
                assert resp.status_code == 200
        finally:
            ms.PROVIDERS.pop("extra")



class TestChatNoStream:
    async def test_ok_devuelve_chunk(self, ms):  # noqa: F811
        resp = await ms._chat_no_stream(ms.PROVIDERS["ollama"], "m", [{"role": "user", "content": "x"}], None, 100, 0.0)
        assert resp["id"] == "resp-1"

    async def test_provider_error_raise_http(self, ms):  # noqa: F811
        from core.mochila.providers import ProviderError

        class Explosivo(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("fuego", "ollama", 500)
                yield None  # pragma: no cover

        with pytest.raises(HTTPException) as excinfo:
            await ms._chat_no_stream(Explosivo("e"), "m", [], None, 100, 0.0)
        assert excinfo.value.status_code == 500

    async def test_provider_error_sin_status(self, ms):  # noqa: F811
        from core.mochila.providers import ProviderError

        class SinStatus(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("mal", "ollama")
                yield None  # pragma: no cover

        with pytest.raises(HTTPException) as excinfo:
            await ms._chat_no_stream(SinStatus("s"), "m", [], None, 100, 0.0)
        assert excinfo.value.status_code == 502

    async def test_vacio_devuelve_none(self, ms):  # noqa: F811
        class Vacio(FakeProvider):
            async def chat(self, *a, **k):
                if False:  # pragma: no cover
                    yield None

        assert await ms._chat_no_stream(Vacio("v"), "m", [], None, 100, 0.0) is None



class TestAbortajeGuardianSSE:
    async def test_no_aborta(self, ms):  # noqa: F811
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        ab, texto, sse = await ms._abortaje_guardian_sse(G(), {"choices": [{"delta": {"content": "a"}}]}, "acum", "m")
        assert ab is False
        assert texto == "acuma"
        assert sse == b""

    async def test_aborta(self, ms, monkeypatch):  # noqa: F811
        monkeypatch.setattr("core.mochila.mochila_server.log_event", lambda *a, **k: None)

        class G:
            def evaluar_texto_stream(self, texto):
                return False

            def generar_penalizacion(self):
                return {"pen": 1}

        _ab, _texto, sse = await ms._abortaje_guardian_sse(G(), {"choices": [{"delta": {"content": "malo"}}]}, "", "m")
        assert sse
        assert b"STREAM_ABORTED_BY_GUARDIAN" in sse
        assert b"[DONE]" in sse



class TestStreamProviderDirecto:
    async def _recoger(self, ms, provider, **kwargs):  # noqa: F811
        ms.PROVIDERS["directo"] = provider
        try:
            out = b""
            async for chunk in ms._stream_from_provider("directo", "m", [], None, 100, 0.0, **kwargs):
                out += chunk
            return out
        finally:
            ms.PROVIDERS.pop("directo", None)

    async def test_chunk_none_continua(self, ms):  # noqa: F811
        class ConNone(FakeProvider):
            async def chat(self, *a, **k):
                yield None
                yield {"choices": [{"index": 0, "delta": {"content": "x"}, "finish_reason": None}]}
                yield {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

        out = await self._recoger(ms, ConNone("c"))
        assert b"[DONE]" in out
        assert b"x" in out

    async def test_fin_normal_con_registros(self, ms):  # noqa: F811
        out = await self._recoger(ms, FakeProvider("f"))
        assert b"[DONE]" in out

    async def test_fin_sin_done_y_finally(self, ms):  # noqa: F811
        class SinFin(FakeProvider):
            async def chat(self, *a, **k):
                yield {"choices": [{"index": 0, "delta": {"content": "parcial"}, "finish_reason": None}]}

        out = await self._recoger(ms, SinFin("s"))
        assert b"data: [DONE]" in out

    async def test_guardian_aborta_stream(self, ms, monkeypatch):  # noqa: F811
        class G:
            def evaluar_texto_stream(self, texto):
                return False

            def generar_penalizacion(self):
                return {"pen": 1}

        monkeypatch.setattr("core.mochila.mochila_server.log_event", lambda *a, **k: None)
        out = await self._recoger(ms, FakeProvider("f"), is_opencode=True, guardian=G())
        assert b"STREAM_ABORTED_BY_GUARDIAN" in out
        assert b"[DONE]" in out

    async def test_guardian_no_aborta_stream(self, ms):  # noqa: F811
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        out = await self._recoger(ms, FakeProvider("f"), is_opencode=True, guardian=G())
        assert b"[DONE]" in out
        assert b"hola" in out

    async def test_timeout_error(self, ms):  # noqa: F811
        class TimeoutProvider(FakeProvider):
            async def chat(self, *a, **k):
                raise TimeoutError
                yield None  # pragma: no cover

        out = await self._recoger(ms, TimeoutProvider("t"))
        assert b"timeout_error" in out
        assert b"[DONE]" in out

    async def test_provider_error(self, ms):  # noqa: F811
        from core.mochila.providers import ProviderError

        class ErrorProvider(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("cae", "directo", 502)
                yield None  # pragma: no cover

        out = await self._recoger(ms, ErrorProvider("e"))
        assert b"provider_error" in out

    async def test_internal_error(self, ms):  # noqa: F811
        class Roto(FakeProvider):
            async def chat(self, *a, **k):
                raise RuntimeError("boom")
                yield None  # pragma: no cover

        out = await self._recoger(ms, Roto("r"))
        assert b"internal_error" in out



class TestProcesarUsage:
    def test_none_no_llama(self, ms):  # noqa: F811
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage(None, "ollama", "m")
        spy.assert_not_called()

    def test_con_uso(self, ms):  # noqa: F811
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage({"usage": {"prompt_tokens": 7, "completion_tokens": 3}}, "ollama", "m")
        spy.assert_called_once_with("ollama", "m", 7, 3)

    def test_uso_none_ceros(self, ms):  # noqa: F811
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage({"usage": None}, "ollama", "m")
        spy.assert_called_once_with("ollama", "m", 0, 0)



class TestEvaluarGuardian:
    def test_delta_no_bloquea(self, ms):  # noqa: F811
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        ab, texto, penalty = ms._evaluar_guardian(G(), {"choices": [{"delta": {"content": "ok"}}]}, "previo", "m")
        assert ab is False
        assert texto == "previook"
        assert penalty is None


