from __future__ import annotations

import pytest

"""Tests para core/voice/__init__.py, core/model_router/__main__.py y core/inferencia/engine.py."""

from unittest import mock

import pytest

import core.inferencia.engine as ie
import core.voice as voice
from core.voice import PiperUraTTS, PiperTTSMotor


class TestVoiceInit:
    def test_exports_presentes(self) -> None:
        assert "AnkerDeterministicPipeline" in voice.__all__
        assert "AnkerMacPipeline" in voice.__all__
        assert "PiperTTSMotor" in voice.__all__

    def test_piper_ura_tts_alias(self) -> None:
        assert PiperUraTTS is PiperTTSMotor


class TestMainModelRouter:
    def test_main_estructura(self) -> None:
        """__main__ solo importa setup_path + main — cobertura por ejecucion."""
        import runpy

        with mock.patch("core.model_router.cli.main") as main_mock:
            runpy.run_module("core.model_router.__main__", run_name="__main__")
        main_mock.assert_called_once()


class TestInferenciaStreamEngine:
    @pytest.mark.asyncio
    async def test_cancelado_antes_de_slot(self) -> None:
        router = mock.Mock()
        router.adquirir_slot_vram = mock.AsyncMock(side_effect=asyncio_CancelledError())
        engine = ie.InferenciaStreamEngine(router, mock.Mock())
        with pytest.raises(asyncio_CancelledError()):
            async for _ in engine.ejecutar_inferencia_RAG("m", {"tokens_estimados": 1}):
                pass

    @pytest.mark.asyncio
    async def test_slot_no_adquirido_yield_504(self) -> None:
        router = mock.Mock()
        router.adquirir_slot_vram = mock.AsyncMock(return_value=False)
        router.liberar_slot_vram = mock.AsyncMock()
        engine = ie.InferenciaStreamEngine(router, mock.Mock())
        out = [t async for t in engine.ejecutar_inferencia_RAG("m", {})]
        assert out == ["Error 504: Tiempo de espera en cola excedido sin slots de GPU disponibles."]
        router.liberar_slot_vram.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_ok(self) -> None:
        router = mock.Mock()
        router.adquirir_slot_vram = mock.AsyncMock(return_value=True)
        router.liberar_slot_vram = mock.AsyncMock()

        async def _chat(**kwargs):
            async def _inner():
                for chunk in [{"message": {"content": "hola"}}, {"message": {"content": " mundo"}}]:
                    yield chunk
            return _inner()

        client = mock.Mock()
        client.chat = _chat
        engine = ie.InferenciaStreamEngine(router, client)
        out = [t async for t in engine.ejecutar_inferencia_RAG("m", {"messages": [], "tokens_estimados": 5})]
        assert out == ["hola", " mundo"]
        router.liberar_slot_vram.assert_awaited_once_with("m")

    @pytest.mark.asyncio
    async def test_cancelado_mid_stream_libera_slot(self) -> None:
        router = mock.Mock()
        router.adquirir_slot_vram = mock.AsyncMock(return_value=True)
        router.liberar_slot_vram = mock.AsyncMock()

        async def _chat(**kwargs):
            async def _inner():
                yield {"message": {"content": "a"}}
                raise asyncio_CancelledError()
            return _inner()

        client = mock.Mock()
        client.chat = _chat
        engine = ie.InferenciaStreamEngine(router, client)
        with pytest.raises(asyncio_CancelledError()):
            async for _ in engine.ejecutar_inferencia_RAG("m", {"messages": []}):
                pass
        router.liberar_slot_vram.assert_awaited_once_with("m")

    @pytest.mark.asyncio
    async def test_error_generico_yield_fallo(self) -> None:
        router = mock.Mock()
        router.adquirir_slot_vram = mock.AsyncMock(return_value=True)
        router.liberar_slot_vram = mock.AsyncMock()

        async def _chat(**kwargs):
            async def _inner():
                raise RuntimeError("modelo caido")
                yield  # pragma: no cover
            return _inner()

        client = mock.Mock()
        client.chat = _chat
        engine = ie.InferenciaStreamEngine(router, client)
        out = [t async for t in engine.ejecutar_inferencia_RAG("m", {"messages": []})]
        assert len(out) == 1
        assert "Fallo en la respuesta del modelo" in out[0]
        router.liberar_slot_vram.assert_awaited_once_with("m")


def asyncio_CancelledError():
    import asyncio

    return asyncio.CancelledError
