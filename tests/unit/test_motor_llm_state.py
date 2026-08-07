"""Tests para motor/core/llm/_state.py — LLMState y build_llm_state.

Cubre la selección de proveedor por config y los fallos de import
de proveedores opcionales.
"""
from __future__ import annotations

import builtins
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.llm._state import LLMState, _get_optional_providers, build_llm_state


class TestLLMState:
    def test_dataclass_campos(self) -> None:
        state = LLMState(
            registry="r",
            default_provider="d",
            generate="g",
            embed="e",
            embed_async="ea",
            health="h",
        )
        assert state.registry == "r"
        assert state.default_provider == "d"
        assert state.generate == "g"
        assert state.embed == "e"
        assert state.embed_async == "ea"
        assert state.health == "h"


class TestGetOptionalProviders:
    def test_importa_todos(self) -> None:
        providers = _get_optional_providers()
        names = [name for _cls, name in providers]
        assert set(names) == {"openai", "anthropic", "gemini", "openrouter", "lmstudio", "vllm", "groq"}

    @pytest.mark.parametrize(
        "modulo",
        [
            "motor.core.llm.openai",
            "motor.core.llm.anthropic",
            "motor.core.llm.gemini",
            "motor.core.llm.openrouter",
            "motor.core.llm.lmstudio",
            "motor.core.llm.vllm",
            "motor.core.llm.groq",
        ],
    )
    def test_falla_import_silencioso(self, modulo: str) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
            if name == modulo:
                raise ImportError("no disponible")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            providers = _get_optional_providers()
        names = [name for _cls, name in providers]
        assert modulo.rsplit(".", 1)[-1] not in names


class TestBuildLlmState:
    def test_config_none_carga_config(self) -> None:
        cfg = SimpleNamespace(llm_provider="ollama")
        with mock.patch("motor.core.config.UraConfig.load", return_value=cfg), mock.patch(
            "motor.core.llm.ollama.OllamaProvider"
        ) as ollama_cls, mock.patch("motor.core.llm.registry.registry") as reg:
            state = build_llm_state()
        assert state.default_provider is ollama_cls.return_value
        reg.register.assert_any_call("ollama", ollama_cls.return_value, default=True)

    @pytest.mark.parametrize(
        ("provider_name", "patch_path", "nombre_registro"),
        [
            ("openai", "motor.core.llm.openai.OpenAIProvider", "openai"),
            ("anthropic", "motor.core.llm.anthropic.AnthropicProvider", "anthropic"),
            ("gemini", "motor.core.llm.gemini.GeminiProvider", "gemini"),
            ("openrouter", "motor.core.llm.openrouter.OpenRouterProvider", "openrouter"),
            ("lmstudio", "motor.core.llm.lmstudio.LMStudioProvider", "lmstudio"),
            ("vllm", "motor.core.llm.vllm.VLLMProvider", "vllm"),
        ],
    )
    def test_provider_por_config(
        self,
        provider_name: str,
        patch_path: str,
        nombre_registro: str,
    ) -> None:
        config = SimpleNamespace(llm_provider=provider_name)
        with mock.patch(patch_path) as ProvCls, mock.patch(
            "motor.core.llm.ollama.OllamaProvider"
        ), mock.patch("motor.core.llm.registry.registry") as reg:
            state = build_llm_state(config)
        assert state.default_provider is ProvCls.return_value
        reg.register.assert_any_call(nombre_registro, ProvCls.return_value, default=True)
        reg.register.assert_any_call("ollama", mock.ANY)
        assert state.generate == ProvCls.return_value.generate
        assert state.health == ProvCls.return_value.health

    def test_ollama_default_por_config(self) -> None:
        config = SimpleNamespace(llm_provider="ollama")
        with mock.patch("motor.core.llm.ollama.OllamaProvider") as ollama_cls, mock.patch(
            "motor.core.llm.registry.registry"
        ) as reg:
            state = build_llm_state(config)
        assert state.default_provider is ollama_cls.return_value
        reg.register.assert_any_call("ollama", ollama_cls.return_value, default=True)

    def test_provider_desconocido_usa_ollama(self) -> None:
        config = SimpleNamespace(llm_provider="weirdo")
        with mock.patch("motor.core.llm.ollama.OllamaProvider") as ollama_cls, mock.patch(
            "motor.core.llm.registry.registry"
        ) as reg:
            state = build_llm_state(config)
        assert state.default_provider is ollama_cls.return_value
        reg.register.assert_any_call("ollama", ollama_cls.return_value, default=True)

    def test_error_instanciacion_proveedor_opcional(self) -> None:
        config = SimpleNamespace(llm_provider="ollama")

        class Exploding:
            def __init__(self) -> None:
                raise RuntimeError("boom")

        with mock.patch("motor.core.config.UraConfig.load", return_value=config), mock.patch(
            "motor.core.llm.ollama.OllamaProvider"
        ), mock.patch("motor.core.llm.openai.OpenAIProvider", Exploding), mock.patch(
            "motor.core.llm.registry.registry"
        ) as reg:
            state = build_llm_state()
        assert state.default_provider is not None
        assert reg.register.call_count >= 1
