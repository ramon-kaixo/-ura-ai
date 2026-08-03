"""Tests para motor/core/llm/__init__.py — API unificada lazy."""
from __future__ import annotations

from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    import motor.core.llm as llm

    monkeypatch.setattr(llm, "_LLM_STATE", None)
    yield
    monkeypatch.setattr(llm, "_LLM_STATE", None)


class FakeState:
    def __init__(self):
        self.generate = mock.Mock(return_value="generado")
        self.embed = mock.Mock(return_value=[[0.1]])
        self.embed_async = mock.AsyncMock(return_value=[[0.2]])
        self.health = mock.Mock(return_value={"status": "ok"})


class TestLLMInit:
    def test_all(self) -> None:
        import motor.core.llm as llm

        assert set(llm.__all__) == {"embed", "embed_async", "generate", "health"}

    def test_generate_delega(self, monkeypatch) -> None:
        import motor.core.llm as llm

        state = FakeState()
        monkeypatch.setattr(llm, "_get_state", mock.Mock(return_value=state))
        r = llm.generate("prompt", model="m", options={"t": 0.1})
        assert r == "generado"
        state.generate.assert_called_once_with("prompt", "m", {"t": 0.1})

    def test_embed_delega(self, monkeypatch) -> None:
        import motor.core.llm as llm

        state = FakeState()
        monkeypatch.setattr(llm, "_get_state", mock.Mock(return_value=state))
        r = llm.embed(["texto"])
        assert r == [[0.1]]
        state.embed.assert_called_once_with(["texto"], None)

    @pytest.mark.asyncio
    async def test_embed_async_delega(self, monkeypatch) -> None:
        import motor.core.llm as llm

        state = FakeState()
        monkeypatch.setattr(llm, "_get_state", mock.Mock(return_value=state))
        r = await llm.embed_async(["texto"], "m2")
        assert r == [[0.2]]
        state.embed_async.assert_awaited_once_with(["texto"], "m2")

    def test_health_delega(self, monkeypatch) -> None:
        import motor.core.llm as llm

        state = FakeState()
        monkeypatch.setattr(llm, "_get_state", mock.Mock(return_value=state))
        assert llm.health() == {"status": "ok"}

    def test_get_state_lazy(self, monkeypatch) -> None:
        import motor.core.llm as llm

        state = FakeState()
        builder = mock.Mock(return_value=state)
        monkeypatch.setattr("motor.core.llm._state.build_llm_state", builder)
        s1 = llm._get_state()
        s2 = llm._get_state()
        assert s1 is s2 is state
        builder.assert_called_once()  # singleton lazy
