"""Tests de cobertura P3 para motor/core/config.py — funciones _apply_*.

Cubre _apply_legacy_config (path/URA_CONFIG, JSON inválido, atributos),
_apply_config_overrides (CONFIG completo, None, dict vacío) y
_apply_env_overrides (todas las env vars, log_level inválido) que no tenían
tests directos (179 mutantes survived en el reporte 2026-08-16).
"""

from __future__ import annotations

import json
import os
import warnings
from unittest import mock

import pytest

from motor.core.config import UraConfig, _apply_config_overrides, _apply_env_overrides, _apply_legacy_config


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limpia todas las env vars URA_* para que los defaults manden."""
    for k in list(os.environ):
        if k.startswith("URA_"):
            monkeypatch.delenv(k, raising=False)


def _fake_cfg(data: dict) -> mock.Mock:
    """Mock de CONFIG desde config_manager."""
    return mock.patch("motor.core.config_manager.CONFIG", data)


class TestApplyLegacyConfig:
    def test_sin_fuentes(self) -> None:
        c = UraConfig()
        _apply_legacy_config(c)
        assert c.data_dir  # defaults intactos

    def test_path_valida(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        p = tmp_path / "legacy.json"
        p.write_text(json.dumps({"qdrant_host": "10.0.0.1", "ollama_port": 9999}))
        c = UraConfig()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            _apply_legacy_config(c, str(p))
        assert c.qdrant_host == "10.0.0.1"
        assert c.ollama_port == 9999

    def test_path_no_existe(self, tmp_path) -> None:
        c = UraConfig()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            _apply_legacy_config(c, str(tmp_path / "nope.json"))
        assert c.qdrant_host == "localhost"

    def test_json_invalido(self, tmp_path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{no es json")
        c = UraConfig()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            _apply_legacy_config(c, str(p))
        assert c.qdrant_host == "localhost"

    def test_env_ura_config(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        p = tmp_path / "env.json"
        p.write_text(json.dumps({"timer_interval_min": 7}))
        monkeypatch.setenv("URA_CONFIG", str(p))
        c = UraConfig()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            _apply_legacy_config(c)
        assert c.timer_interval_min == 7

    def test_atributo_no_existe_ignorado(self, tmp_path) -> None:
        p = tmp_path / "extra.json"
        p.write_text(json.dumps({"no_existe": 1, "qdrant_host": "x"}))
        c = UraConfig()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            _apply_legacy_config(c, str(p))
        assert c.qdrant_host == "x"

    def test_warning_deprecation(self, tmp_path) -> None:
        p = tmp_path / "w.json"
        p.write_text("{}")
        with pytest.warns(FutureWarning):
            _apply_legacy_config(UraConfig(), str(p))


class TestApplyConfigOverrides:
    def test_sin_config(self) -> None:
        with mock.patch("motor.core.config._load_config_dict", return_value=None):
            c = UraConfig()
            _apply_config_overrides(c)
            assert c.log_level == "INFO"

    def test_config_completo(self) -> None:
        data = {
            "paths": {"data": "/tmp/data-x"},
            "log_level": "DEBUG",
            "ollama": {"host": "h1", "port": "1234"},
            "llm": {
                "model": "m1",
                "embedding_model": "e1",
                "timeout": "60",
                "temperature": "0.7",
                "max_tokens": "512",
                "provider": "deepseek",
            },
        }
        with mock.patch("motor.core.config._load_config_dict", return_value=data):
            c = UraConfig()
            _apply_config_overrides(c)
        assert c.data_dir == "/tmp/data-x"
        assert c.log_level == "DEBUG"
        assert c.ollama_host == "h1"
        assert c.ollama_port == 1234
        assert c.ollama_model == "m1"
        assert c.ollama_embedding_model == "e1"
        assert c.ollama_timeout == 60
        assert c.ollama_temperature == 0.7
        assert c.ollama_max_tokens == 512
        assert c.llm_provider == "deepseek"

    def test_config_parcial(self) -> None:
        with mock.patch("motor.core.config._load_config_dict", return_value={"paths": {}}):
            c = UraConfig()
            _apply_config_overrides(c)
            assert c.ollama_host == "localhost"  # defaults intactos


class TestApplyEnvOverrides:
    def test_env_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        monkeypatch.setenv("URA_QDRANT_HOST", "10.1.1.1")
        monkeypatch.setenv("URA_QDRANT_PORT", "6334")
        monkeypatch.setenv("URA_TIMER_INTERVAL_MIN", "9")
        monkeypatch.setenv("URA_LOG_LEVEL", "error")
        monkeypatch.setenv("URA_OLLAMA_HOST", "oh")
        monkeypatch.setenv("URA_OLLAMA_PORT", "11435")
        monkeypatch.setenv("URA_OLLAMA_MODEL", "om")
        monkeypatch.setenv("URA_OLLAMA_EMBEDDING_MODEL", "em")
        monkeypatch.setenv("URA_OLLAMA_TIMEOUT", "30")
        monkeypatch.setenv("URA_OLLAMA_TEMPERATURE", "0.9")
        monkeypatch.setenv("URA_OLLAMA_MAX_TOKENS", "2048")
        monkeypatch.setenv("URA_LLM_PROVIDER", "groq")
        c = UraConfig()
        _apply_env_overrides(c)
        assert c.qdrant_host == "10.1.1.1"
        assert c.qdrant_port == 6334
        assert c.timer_interval_min == 9
        assert c.log_level == "ERROR"  # upper()
        assert c.ollama_host == "oh"
        assert c.ollama_port == 11435
        assert c.ollama_model == "om"
        assert c.ollama_embedding_model == "em"
        assert c.ollama_timeout == 30
        assert c.ollama_temperature == 0.9
        assert c.ollama_max_tokens == 2048
        assert c.llm_provider == "groq"

    def test_env_log_invalido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        monkeypatch.setenv("URA_LOG_LEVEL", "bogus")
        c = UraConfig()
        _apply_env_overrides(c)
        assert c.log_level == "INFO"

    def test_sin_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        c = UraConfig()
        _apply_env_overrides(c)
        assert c.log_level == "INFO"
        assert c.ollama_model == "qwen2.5:3b"


class TestUraConfigDefaults:
    def test_post_init_completa_rutas(self) -> None:
        c = UraConfig()
        assert c.data_dir.endswith("/data")
        assert c.failure_knowledge_path.endswith("failure_knowledge_inicial.json")
        assert c.baseline_path.endswith("baseline_inicial.json")

    def test_post_init_log_invalido(self) -> None:
        c = UraConfig(log_level="nope")
        assert c.log_level == "INFO"

    def test_load_full(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_env(monkeypatch)
        c = UraConfig.load()
        assert isinstance(c.schema_version, int)
        assert c.log_level in {"INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"}
        assert c.data_dir
