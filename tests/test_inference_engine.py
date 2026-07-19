"""Tests para InferenciaStreamEngine (core/inferencia/engine.py)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.inferencia.engine import InferenciaStreamEngine


@pytest.fixture
def mock_router():
    router = MagicMock()
    router.adquirir_slot_vram = AsyncMock()
    router.liberar_slot_vram = AsyncMock()
    return router


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat = AsyncMock()
    return client


@pytest.fixture
def engine(mock_router, mock_client):
    return InferenciaStreamEngine(mock_router, mock_client)


class TestInferenciaStreamEngine:
    @pytest.mark.asyncio
    async def test_slot_denied_yields_error(self, engine, mock_router, mock_client) -> None:
        mock_router.adquirir_slot_vram.return_value = False
        tokens = []
        async for chunk in engine.ejecutar_inferencia_RAG(
            "modelo-test",
            {"messages": [{"role": "user", "content": "hi"}], "tokens_estimados": 10},
        ):
            tokens.append(chunk)  # noqa: PERF401
        assert tokens
        assert "504" in tokens[0]
        mock_router.liberar_slot_vram.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancelled_during_acquisition(self, engine, mock_router, mock_client) -> None:
        mock_router.adquirir_slot_vram = AsyncMock(side_effect=asyncio.CancelledError())
        tokens = []
        with pytest.raises(asyncio.CancelledError):
            async for chunk in engine.ejecutar_inferencia_RAG(
                "modelo-test",
                {"messages": [{"role": "user", "content": "hi"}], "tokens_estimados": 10},
            ):
                tokens.append(chunk)  # noqa: PERF401
        assert tokens == []

    @pytest.mark.asyncio
    async def test_streaming_happy_path(self, engine, mock_router, mock_client) -> None:
        mock_router.adquirir_slot_vram.return_value = True

        async def _mock_chat(*args, **kwargs):
            for token in ["a", "b", "c"]:
                yield {"message": {"content": token}}
                await asyncio.sleep(0)

        mock_client.chat.return_value = _mock_chat()
        tokens = []
        async for chunk in engine.ejecutar_inferencia_RAG(
            "modelo-test",
            {"messages": [{"role": "user", "content": "hi"}], "tokens_estimados": 10},
        ):
            tokens.append(chunk)  # noqa: PERF401
        assert tokens == ["a", "b", "c"]
        mock_router.liberar_slot_vram.assert_awaited_once_with("modelo-test")

    @pytest.mark.asyncio
    async def test_slot_released_on_stream_cancel(self, engine, mock_router, mock_client) -> None:
        mock_router.adquirir_slot_vram.return_value = True

        async def _mock_chat(*args, **kwargs):
            yield {"message": {"content": "a"}}
            await asyncio.sleep(0)
            raise asyncio.CancelledError

        mock_client.chat.return_value = _mock_chat()
        tokens = []
        with pytest.raises(asyncio.CancelledError):
            async for chunk in engine.ejecutar_inferencia_RAG(
                "modelo-test",
                {"messages": [{"role": "user", "content": "hi"}], "tokens_estimados": 10},
            ):
                tokens.append(chunk)  # noqa: PERF401
        mock_router.liberar_slot_vram.assert_awaited_once_with("modelo-test")

    @pytest.mark.asyncio
    async def test_stream_error_yields_error_chunk(self, engine, mock_router, mock_client) -> None:
        mock_router.adquirir_slot_vram.return_value = True

        async def _mock_chat(*args, **kwargs):
            yield {"message": {"content": "a"}}
            msg = "connection lost"
            raise RuntimeError(msg)

        mock_client.chat.return_value = _mock_chat()
        tokens = []
        async for chunk in engine.ejecutar_inferencia_RAG(
            "modelo-test",
            {"messages": [{"role": "user", "content": "hi"}], "tokens_estimados": 10},
        ):
            tokens.append(chunk)  # noqa: PERF401
        assert "Fallo" in tokens[-1]
        mock_router.liberar_slot_vram.assert_awaited_once_with("modelo-test")
