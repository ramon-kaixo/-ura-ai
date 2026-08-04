"""Tests para motor/core/llm/__init__.py — API pública unificada.

La selección de proveedor se difiere a _get_state(); se verifica que
las 4 funciones delegan y que el estado se cachea.
"""
from __future__ import annotations

import asyncio
from unittest import mock

import motor.core.llm as llm_api


class TestApiPublica:
    def _fake_state(self) -> mock.Mock:
        state = mock.Mock()
        state.generate.return_value = "gen"
        state.embed.return_value = [[0.1]]
        state.embed_async.return_value = [[0.2]]
        state.health.return_value = {"status": "ok"}
        return state

    def _patched_build(self) -> tuple[mock.Mock, mock.Mock]:
        llm_api._LLM_STATE = None
        state = self._fake_state()
        build = mock.patch("motor.core.llm._state.build_llm_state", return_value=state)
        build.start()
        return build, state

    def test_generate_delega(self) -> None:
        build, state = self._patched_build()
        try:
            result = llm_api.generate("p", model="m", options={"x": 1})
        finally:
            build.stop()
        assert result == "gen"
        state.generate.assert_called_with("p", "m", {"x": 1})

    def test_embed_delega(self) -> None:
        build, state = self._patched_build()
        try:
            result = llm_api.embed(["a"])
        finally:
            build.stop()
        assert result == [[0.1]]
        state.embed.assert_called_with(["a"], None)

    def test_embed_async_delega(self) -> None:
        build, state = self._patched_build()
        try:
            result = asyncio.run(llm_api.embed_async(["a"]))
        finally:
            build.stop()
        assert result == [[0.2]]
        state.embed_async.assert_called_with(["a"], None)

    def test_health_delega(self) -> None:
        build, state = self._patched_build()
        try:
            result = llm_api.health()
        finally:
            build.stop()
        assert result == {"status": "ok"}
        state.health.assert_called_once()

    def test_estado_cacheado(self) -> None:
        llm_api._LLM_STATE = None
        state = self._fake_state()
        with mock.patch("motor.core.llm._state.build_llm_state", return_value=state) as build:
            llm_api.generate("a")
            llm_api.embed(["b"])
            llm_api.health()
        assert build.call_count == 1

    def test_all(self) -> None:
        assert set(llm_api.__all__) == {"embed", "embed_async", "generate", "health"}
