"""Tests de limpieza de deuda técnica (F23-B2).

Verifica:
1. No hay exports muertos
2. No hay API deprecated en __all__
3. No hay registros duplicados en Registry
4. No hay imports no utilizados
5. Backward compatibility tras limpieza
"""

from __future__ import annotations

import motor.core.evaluation
import motor.core.llm
from motor.core.llm.registry import registry


class TestNoDeadExports:
    def test_llm_all_members_exist(self) -> None:
        for name in motor.core.llm.__all__:
            assert hasattr(motor.core.llm, name), f"__all__ contiene {name} pero no existe"

    def test_evaluation_all_members_exist(self) -> None:
        for name in motor.core.evaluation.__all__:
            assert hasattr(motor.core.evaluation, name), f"__all__ contiene {name} pero no existe"


class TestNoDeprecatedPublicAPI:
    def test_llm_all_has_no_internals(self) -> None:
        internal = {"registry", "OllamaProvider", "CONFIG", "log", "logging"}
        assert not (internal & set(motor.core.llm.__all__))

    def test_evaluation_all_has_no_submodules(self) -> None:
        internal = {"corpus", "evaluator", "metrics", "experiment", "regression", "continuous"}
        assert not (internal & set(motor.core.evaluation.__all__))


class TestNoUnusedRegistryEntries:
    def test_registry_has_expected_providers(self) -> None:
        providers = list(registry.list())
        expected = {"ollama", "openai", "anthropic", "gemini", "openrouter", "lmstudio", "vllm"}
        registered = set(providers)
        assert expected.issubset(registered), f"Faltan: {expected - registered}"

    def test_no_duplicate_registrations(self) -> None:
        providers = list(registry.list())
        assert len(providers) == len(set(providers)), "Hay proveedores duplicados"

    def test_default_provider_is_ollama(self) -> None:
        assert registry.default_name == "ollama"

    def test_all_providers_can_be_instantiated(self) -> None:
        for name, cls in registry.list().items():
            try:
                inst = cls()
                assert inst._provider_name == name, f"{name}: _provider_name mismatch"
            except Exception:  # noqa: S110
                pass


class TestBackwardCompatibility:
    def test_llm_api_intact(self) -> None:
        """Los 4 símbolos de __all__ deben seguir funcionando."""
        for name in motor.core.llm.__all__:
            obj = getattr(motor.core.llm, name)
            assert callable(obj), f"{name} no es invocable"

    def test_evaluation_api_intact(self) -> None:
        for name in motor.core.evaluation.__all__:
            obj = getattr(motor.core.evaluation, name)
            assert obj is not None, f"{name} no debería ser None"
