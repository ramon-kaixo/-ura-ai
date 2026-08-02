"""Tests para core/debate/debate_engine.py."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import core.debate.debate_engine as de


class TestLoadConfig:
    def test_carga_json_valido(self) -> None:
        cfg = de.load_config()
        assert "models" in cfg
        assert cfg["consensus_threshold"] == 0.85


class TestValidarEsquema:
    def test_sin_esquema(self) -> None:
        assert de.validar_esquema_salida("cualquier cosa") is True

    def test_json_valido(self, monkeypatch) -> None:
        monkeypatch.setattr(de, "log_event", mock.Mock())
        assert de.validar_esquema_salida('{"score": 0.9, "reason": "ok", "risks": []}', {"score": float, "reason": str, "risks": list}) is True

    def test_con_markdown_json(self, monkeypatch) -> None:
        monkeypatch.setattr(de, "log_event", mock.Mock())
        out = '```json\n{"score": 1.0, "reason": "a", "risks": []}\n```'
        assert de.validar_esquema_salida(out, {"score": float}) is True

    def test_con_markdown_generico(self, monkeypatch) -> None:
        monkeypatch.setattr(de, "log_event", mock.Mock())
        out = '```\n{"score": 1.0, "reason": "a", "risks": []}\n```'
        assert de.validar_esquema_salida(out, {"score": float}) is True

    def test_key_faltante(self, monkeypatch) -> None:
        log = mock.Mock()
        monkeypatch.setattr(de, "log_event", log)
        assert de.validar_esquema_salida('{"reason": "x"}', {"score": float}) is False
        assert log.call_args.args[0] == "schema_validation_failed"
        assert "Missing key" in log.call_args.kwargs["reason"]

    def test_tipo_incorrecto(self, monkeypatch) -> None:
        log = mock.Mock()
        monkeypatch.setattr(de, "log_event", log)
        assert de.validar_esquema_salida('{"score": "texto", "reason": "x"}', {"score": float}) is False
        assert "expected float" in log.call_args.kwargs["reason"]

    def test_json_invalido(self, monkeypatch) -> None:
        log = mock.Mock()
        monkeypatch.setattr(de, "log_event", log)
        assert de.validar_esquema_salida("no es json", {"score": float}) is False
        log.assert_called_once()


class TestPrompts:
    def test_primary_con_contexto(self) -> None:
        prompt = de.build_primary_prompt("plan x", {"vram": 10})
        assert "plan x" in prompt
        assert '"vram": 10' in prompt
        assert "arquitecto" in prompt

    def test_primary_sin_contexto(self) -> None:
        prompt = de.build_primary_prompt("plan y")
        assert "No disponible" in prompt

    def test_auditor_con_contexto(self) -> None:
        prompt = de.build_auditor_prompt("plan", {"a": 1})
        assert "ABOGADO DEL DIABLO" in prompt
        assert '"a": 1' in prompt
        assert "requires_human" in prompt


class TestCallOllama:
    @pytest.mark.asyncio
    async def test_con_llm_ok(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = '{"score": 0.9, "reason": "ok", "risks": []}'
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        monkeypatch.setattr("core.debate.debate_engine.validar_esquema_salida", mock.Mock(return_value=True))
        out = await de.call_ollama("modelo", "prompt", llm=llm)
        assert out == {"score": 0.9, "reason": "ok", "risks": []}

    @pytest.mark.asyncio
    async def test_error_prefijo(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = "Error: fallo"
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        assert await de.call_ollama("m", "p", llm=llm) is None

    @pytest.mark.asyncio
    async def test_json_con_fences(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = '```\n{"score": 0.5, "reason": "r", "risks": []}\n```'
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        monkeypatch.setattr("core.debate.debate_engine.validar_esquema_salida", mock.Mock(return_value=True))
        out = await de.call_ollama("m", "p", llm=llm)
        assert out["score"] == 0.5

    @pytest.mark.asyncio
    async def test_json_invalido(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = "no json"
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        assert await de.call_ollama("m", "p", llm=llm) is None

    @pytest.mark.asyncio
    async def test_schema_invalido(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.return_value = '{"score": 0.9, "reason": "ok"}'
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        monkeypatch.setattr("core.debate.debate_engine.validar_esquema_salida", mock.Mock(return_value=False))
        assert await de.call_ollama("m", "p", llm=llm) is None

    @pytest.mark.asyncio
    async def test_excepcion_general(self, monkeypatch) -> None:
        llm = mock.Mock()
        llm.generate.side_effect = RuntimeError("boom")
        monkeypatch.setattr("core.debate.debate_engine.asyncio.to_thread", mock.AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k)))
        assert await de.call_ollama("m", "p", llm=llm) is None


class TestRunDebate:
    @pytest.mark.asyncio
    async def test_consensus_con_sugerencias(self, monkeypatch) -> None:
        cfg = {
            "models": {
                "primary": {"name": "p", "temperature": 0.1, "max_tokens": 10},
                "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10},
            },
            "consensus_threshold": 0.8,
        }
        primary = {"score": 0.9, "reason": "bien", "risks": [], "suggestions": ["mejora1", "mejora2", "mejora3", "mejora4"]}
        auditor = {"score": 0.85, "reason": "ok", "risks": [], "requires_human": False}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[primary, auditor]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "CONSENSUS"
        assert out["consensus"] == 0.85
        assert "mejora1" in out["plan_unified"]
        assert "mejora2" in out["plan_unified"]
        assert "mejora4" not in out["plan_unified"]  # solo primeras 3

    @pytest.mark.asyncio
    async def test_consensus_sin_sugerencias(self, monkeypatch) -> None:
        cfg = {"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.8}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[{"score": 0.9, "reason": "r", "risks": []}, {"score": 0.9, "reason": "r", "risks": [], "requires_human": False}]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "CONSENSUS"
        assert out["plan_unified"] == "plan"

    @pytest.mark.asyncio
    async def test_consensus_bajo_threshold(self, monkeypatch) -> None:
        cfg = {"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.8}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[{"score": 0.5, "reason": "r", "risks": []}, {"score": 0.9, "reason": "r", "risks": []}]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "HUMAN_ARBITRATION"

    @pytest.mark.asyncio
    async def test_requires_human(self, monkeypatch) -> None:
        cfg = {"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.8}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[{"score": 0.9, "reason": "r", "risks": []}, {"score": 0.9, "reason": "r", "risks": [], "requires_human": True}]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "HUMAN_ARBITRATION"

    @pytest.mark.asyncio
    async def test_primario_error(self, monkeypatch) -> None:
        cfg = {"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.8}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[None, {"score": 0.9, "reason": "r", "risks": []}]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "INCOMPLETE"
        assert out["primary_reason"] == "timeout/error"

    @pytest.mark.asyncio
    async def test_auditor_excepcion(self, monkeypatch) -> None:
        cfg = {"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.8}
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[{"score": 0.9, "reason": "r", "risks": []}, RuntimeError("boom")]))
        out = await de.run_debate("plan", config=cfg)
        assert out["verdict"] == "INCOMPLETE"

    @pytest.mark.asyncio
    async def test_config_default_carga_archivo(self, monkeypatch) -> None:
        monkeypatch.setattr(de, "load_config", mock.Mock(return_value={"models": {"primary": {"name": "p", "temperature": 0.1, "max_tokens": 10}, "auditor": {"name": "a", "temperature": 0.2, "max_tokens": 10}}, "consensus_threshold": 0.99}))
        monkeypatch.setattr(de, "call_ollama", mock.AsyncMock(side_effect=[{"score": 0.9, "reason": "r", "risks": []}, {"score": 0.9, "reason": "r", "risks": []}]))
        out = await de.run_debate("plan")
        assert out["verdict"] == "HUMAN_ARBITRATION"


class TestMainAsync:
    @pytest.mark.asyncio
    async def test_desde_stdin_consensus(self, monkeypatch) -> None:
        monkeypatch.setattr(de.sys, "argv", ["debate_engine.py"])
        monkeypatch.setattr(de.sys, "stdin", SimpleNamespace(read=lambda: json.dumps({"plan": "p", "context": {}})))
        monkeypatch.setattr(de, "run_debate", mock.AsyncMock(return_value={"verdict": "CONSENSUS"}))

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(de, "DebateLock", FakeLock)
        monkeypatch.setattr(de, "logger", mock.Mock())
        assert await de.main_async() == 0

    @pytest.mark.asyncio
    async def test_desde_archivo_rechazado(self, monkeypatch, tmp_path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({"plan": "p"}))
        monkeypatch.setattr(de.sys, "argv", ["debate_engine.py", "--plan", str(plan_file)])
        monkeypatch.setattr(de, "run_debate", mock.AsyncMock(return_value={"verdict": "REJECTED"}))

        class FakeLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(de, "DebateLock", FakeLock)
        monkeypatch.setattr(de, "logger", mock.Mock())
        assert await de.main_async() == 1
