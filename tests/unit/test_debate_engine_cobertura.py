"""Tests de cobertura para core/debate/debate_engine.py (ramas faltantes)."""

from __future__ import annotations

import json
import runpy
import sys
import types
from types import SimpleNamespace
from unittest import mock

import pytest

import core.debate.debate_engine as de


class TestCallOllamaSinLLM:
    @pytest.mark.asyncio
    async def test_sin_llm_usa_generate_importado(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "motor.core.llm.generate",
            mock.Mock(return_value='{"score": 0.8, "reason": "ok", "risks": []}'),
        )
        out = await de.call_ollama("m", "p")
        assert out is not None
        assert out["score"] == 0.8
        assert out["reason"] == "ok"

    @pytest.mark.asyncio
    async def test_fences_json_una_linea(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = '```{"score": 0.5, "reason": "r", "risks": []}```'
        monkeypatch.setattr(
            "core.debate.debate_engine.asyncio.to_thread",
            mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)),
        )
        monkeypatch.setattr("core.debate.debate_engine.validar_esquema_salida", mock.Mock(return_value=True))
        out = await de.call_ollama("m", "p", llm=llm)
        assert out["score"] == 0.5


class TestMain:
    def test_main_cierra_con_exit_code(self, monkeypatch) -> None:
        def _fake_run(coro):
            coro.close()
            return 5

        monkeypatch.setattr(de.asyncio, "run", mock.Mock(side_effect=_fake_run))
        with pytest.raises(SystemExit) as exc:
            de.main()
        assert exc.value.code == 5


class TestMainGuard:
    def test_guard_main_consensus(self, monkeypatch) -> None:
        fake_logging = types.ModuleType("motor.observability.logging")
        fake_logging.setup_logging = mock.Mock()
        monkeypatch.setitem(sys.modules, "motor.observability.logging", fake_logging)

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr("core.debate.lockfile.DebateLock", FakeLock)
        monkeypatch.setattr(
            "motor.core.llm.generate",
            mock.Mock(return_value='{"score": 0.9, "reason": "ok", "risks": []}'),
        )
        monkeypatch.setattr(de.sys, "argv", ["debate_engine.py"])
        monkeypatch.setattr(
            de.sys, "stdin", SimpleNamespace(read=lambda: json.dumps({"plan": "plan x", "context": {"a": 1}}))
        )
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(de.__file__), run_name="__main__")
        assert exc.value.code == 0
        fake_logging.setup_logging.assert_called_once_with(level="WARNING")

    def test_guard_main_con_plan_archivo(self, monkeypatch, tmp_path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({"plan": "plan y"}))
        monkeypatch.setattr(
            "motor.core.llm.generate",
            mock.Mock(return_value='{"score": 0.1, "reason": "malo", "risks": []}'),
        )

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr("core.debate.lockfile.DebateLock", FakeLock)
        monkeypatch.setattr(de.sys, "argv", ["debate_engine.py", "--plan", str(plan_file)])
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(de.__file__), run_name="__main__")
        assert exc.value.code == 1
