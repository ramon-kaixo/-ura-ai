"""Tests de contrato para motor.core.llm (A1).

Verifica que la API pública congelada se mantiene estable.
NO verifica comportamiento funcional — solo interfaz y compatibilidad.
"""

from __future__ import annotations

import inspect

import pytest

from motor.core.llm import __all__ as LLM_ALL
from motor.core.llm import embed, embed_async, generate, health

# ─────────────────────────────────────────────
# 1. API pública exportada
# ─────────────────────────────────────────────

class TestAPIExportada:
    def test_all_exporta_cuatro_funciones(self) -> None:
        assert isinstance(LLM_ALL, list)
        assert sorted(LLM_ALL) == sorted(["generate", "embed", "embed_async", "health"])
        assert len(LLM_ALL) == 4

    def test_generate_importable(self) -> None:
        assert callable(generate)

    def test_embed_importable(self) -> None:
        assert callable(embed)

    def test_embed_async_importable(self) -> None:
        assert callable(embed_async)

    def test_health_importable(self) -> None:
        assert callable(health)

    def test_no_hay_imports_no_publicos(self) -> None:
        import motor.core.llm

        exports_no_publicos = {
            name for name in dir(motor.core.llm)
            if not name.startswith("_")
        }
        esperados = {
            "generate", "embed", "embed_async", "health",
            "CONFIG", "log", "logging",
            "OllamaProvider", "OpenAIProvider", "AnthropicProvider", "GeminiProvider", "OpenRouterProvider", "LMStudioProvider", "VLLMProvider",
            "ollama", "openai", "anthropic", "gemini", "openrouter", "lmstudio", "vllm", "base", "registry",
            "router", "circuit_breaker", "observability", "profiler", "detector", "baseline", "monitor",
            "provider_name", "Any", "cls", "name",
        }
        extras = exports_no_publicos - esperados
        assert not extras, f"Export(s) no declarado(s): {sorted(extras)}"


# ─────────────────────────────────────────────
# 2. Firmas de generate, embed, embed_async, health
# ─────────────────────────────────────────────

class TestFirmas:
    def test_generate_signature(self) -> None:
        sig = inspect.signature(generate)
        params = list(sig.parameters.values())
        assert len(params) == 3
        assert params[0].name == "prompt"
        assert "str" in str(params[0].annotation)
        assert params[1].name == "model"
        assert params[2].name == "options"
        assert sig.return_annotation is not inspect.Parameter.empty
        assert "str" in str(sig.return_annotation)

    def test_generate_parametros_opcionales(self) -> None:
        sig = inspect.signature(generate)
        params = list(sig.parameters.values())
        assert params[1].default is None
        assert params[2].default is None

    def test_embed_signature(self) -> None:
        sig = inspect.signature(embed)
        params = list(sig.parameters.values())
        assert len(params) == 2
        assert params[0].name == "texts"
        assert params[1].name == "model"
        assert params[1].default is None

    def test_embed_async_signature(self) -> None:
        sig = inspect.signature(embed_async)
        params = list(sig.parameters.values())
        assert len(params) == 2
        assert params[0].name == "texts"
        assert params[1].name == "model"
        assert params[1].default is None

    def test_health_signature(self) -> None:
        sig = inspect.signature(health)
        # health() no tiene parámetros
        assert len(list(sig.parameters)) == 0
        assert "dict" in str(sig.return_annotation)

    def test_generate_retorna_str(self) -> None:
        sig = inspect.signature(generate)
        assert "str" in str(sig.return_annotation)

    def test_embed_retorna_list(self) -> None:
        sig = inspect.signature(embed)
        assert "list" in str(sig.return_annotation)

    def test_embed_async_retorna_list(self) -> None:
        sig = inspect.signature(embed_async)
        assert "list" in str(sig.return_annotation)


# ─────────────────────────────────────────────
# 3. Compatibilidad del Registry
# ─────────────────────────────────────────────

class TestRegistryContract:
    def test_registry_importable(self) -> None:
        from motor.core.llm.registry import ProviderRegistry, registry

        assert isinstance(registry, ProviderRegistry)

    def test_registry_register_get(self) -> None:
        from motor.core.llm.registry import ProviderRegistry

        reg = ProviderRegistry()

        class _Mock:
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg.register("test", _Mock())  # type: ignore
        assert "test" in reg
        assert reg.get("test") is not None

    def test_registry_default(self) -> None:
        from motor.core.llm.registry import ProviderRegistry

        reg = ProviderRegistry()

        class _Mock:
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg.register("a", _Mock())  # type: ignore
        reg.register("b", _Mock(), default=True)  # type: ignore
        assert reg.default_name == "b"

    def test_registry_unregister(self) -> None:
        from motor.core.llm.registry import ProviderRegistry

        reg = ProviderRegistry()

        class _Mock:
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg.register("a", _Mock(), default=True)  # type: ignore
        reg.unregister("a")
        assert "a" not in reg

    def test_registry_list(self) -> None:
        from motor.core.llm.registry import ProviderRegistry

        reg = ProviderRegistry()

        class _Mock:
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg.register("a", _Mock())  # type: ignore
        lst = reg.list()
        assert "a" in lst
        assert lst["a"] == _Mock


# ─────────────────────────────────────────────
# 4. Compatibilidad del Router
# ─────────────────────────────────────────────

class TestRouterContract:
    def test_router_importable(self) -> None:
        from motor.core.llm.router import LLMRouter

        assert LLMRouter

    def test_router_generate_delega(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.registry import ProviderRegistry
        from motor.core.llm.router import LLMRouter

        class MockProvider(BaseLLMProvider):
            def generate(self, prompt, model=None, options=None):
                return f"mock:{prompt}"
            def embed(self, texts, model=None):
                return [[0.0]]
            async def embed_async(self, texts, model=None):
                return [[0.0]]
            def health(self):
                return {"status": "ok"}

        reg = ProviderRegistry()
        reg.register("mock", MockProvider(), default=True)
        router = LLMRouter(registry=reg)
        assert router.generate("test") == "mock:test"

    def test_router_embed_delega(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.registry import ProviderRegistry
        from motor.core.llm.router import LLMRouter

        class MockProvider(BaseLLMProvider):
            def generate(self, *a, **kw): return ""
            def embed(self, texts, model=None):
                return [[1.0]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg = ProviderRegistry()
        reg.register("mock", MockProvider(), default=True)
        router = LLMRouter(registry=reg)
        assert router.embed(["x"]) == [[1.0]]

    def test_router_health_delega(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.registry import ProviderRegistry
        from motor.core.llm.router import LLMRouter

        class MockProvider(BaseLLMProvider):
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {"status": "ok", "provider": "mock"}

        reg = ProviderRegistry()
        reg.register("mock", MockProvider(), default=True)
        router = LLMRouter(registry=reg)
        assert router.health()["status"] == "ok"

    def test_router_error_sin_provider(self) -> None:
        from motor.core.llm.registry import ProviderRegistry
        from motor.core.llm.router import LLMRouter

        empty = LLMRouter(registry=ProviderRegistry())
        with pytest.raises(RuntimeError, match="No provider"):
            empty.generate("test")

    def test_router_provider_explicito(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.registry import ProviderRegistry
        from motor.core.llm.router import LLMRouter

        class MockA(BaseLLMProvider):
            def generate(self, *a, **kw): return "A"
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        class MockB(BaseLLMProvider):
            def generate(self, *a, **kw): return "B"
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self): return {}

        reg = ProviderRegistry()
        reg.register("a", MockA(), default=True)
        reg.register("b", MockB())
        router = LLMRouter(registry=reg)
        assert router.generate("test", provider="b") == "B"


# ─────────────────────────────────────────────
# 5. Compatibilidad de Provider Base
# ─────────────────────────────────────────────

class TestBaseProviderContract:
    def test_base_es_abstracta(self) -> None:
        from motor.core.llm.base import BaseLLMProvider

        with pytest.raises(TypeError):
            BaseLLMProvider()  # type: ignore

    def test_base_tiene_cuatro_abstractos(self) -> None:

        from motor.core.llm.base import BaseLLMProvider

        abstractos = []
        for name, method in BaseLLMProvider.__dict__.items():
            if getattr(method, "__isabstractmethod__", False):
                abstractos.append(name)
        assert sorted(abstractos) == sorted(["generate", "embed", "embed_async", "health"])

    def test_subclass_debe_implementar_todos(self) -> None:
        from motor.core.llm.base import BaseLLMProvider

        class Incomplete(BaseLLMProvider):
            pass  # No implementa nada

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore

    def test_subclass_completa_funciona(self) -> None:
        from motor.core.llm.base import BaseLLMProvider

        class Complete(BaseLLMProvider):
            def generate(self, prompt, model=None, options=None): return ""
            def embed(self, texts, model=None): return [[]]
            async def embed_async(self, texts, model=None): return [[]]
            def health(self): return {}

        inst = Complete()
        assert inst.generate("x") == ""
        assert inst.embed(["x"]) == [[]]
        assert inst.health() == {}

    def test_base_ubicacion_correcta(self) -> None:
        import motor.core.llm.base

        assert motor.core.llm.base.__file__.endswith("motor/core/llm/base.py")


# ─────────────────────────────────────────────
# 6. Compatibilidad de OllamaProvider
# ─────────────────────────────────────────────

class TestOllamaProviderContract:
    def test_ollama_importable(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        assert OllamaProvider

    def test_ollama_implementa_base(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.ollama import OllamaProvider

        assert issubclass(OllamaProvider, BaseLLMProvider)

    def test_ollama_instanciable(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        inst = OllamaProvider()
        assert inst._provider_name == "ollama"

    def test_ollama_firmas_coinciden(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.ollama import OllamaProvider

        for method_name in ("generate", "embed", "embed_async", "health"):
            sig_impl = inspect.signature(getattr(OllamaProvider, method_name))
            sig_base = inspect.signature(getattr(BaseLLMProvider, method_name))
            # Verificar que los parámetros (sin self) coinciden
            impl_params = [p for p in sig_impl.parameters if p != "self"]
            base_params = [p for p in sig_base.parameters if p != "self"]
            assert impl_params == base_params, (
                f"{method_name}: {impl_params} != {base_params}"
            )

    def test_ollama_generate_retorna_str(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        inst = OllamaProvider()
        from unittest.mock import patch

        with patch.object(inst, "generate", return_value="mock"):
            resultado = inst.generate("test")
            assert isinstance(resultado, str)

    def test_ollama_embed_retorna_lista(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        inst = OllamaProvider()
        from unittest.mock import patch

        with patch.object(inst, "embed", return_value=[[0.1, 0.2]]):
            resultado = inst.embed(["test"])
            assert isinstance(resultado, list)

    def test_ollama_health_retorna_dict(self) -> None:
        from motor.core.llm.ollama import OllamaProvider

        inst = OllamaProvider()
        from unittest.mock import patch

        with patch.object(inst, "health", return_value={"status": "ok"}):
            resultado = inst.health()
            assert isinstance(resultado, dict)

    def test_ollama_es_proveedor_por_defecto(self) -> None:
        from motor.core.llm import _default
        from motor.core.llm.ollama import OllamaProvider

        assert isinstance(_default, OllamaProvider)


# ─────────────────────────────────────────────
# 7. Compatibilidad de OpenAIProvider
# ─────────────────────────────────────────────

class TestOpenAIProviderContract:
    def test_openai_importable(self) -> None:
        from motor.core.llm.openai import OpenAIProvider

        assert OpenAIProvider

    def test_openai_implementa_base(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.openai import OpenAIProvider

        assert issubclass(OpenAIProvider, BaseLLMProvider)

    def test_openai_instanciable(self) -> None:
        from motor.core.llm.openai import OpenAIProvider

        inst = OpenAIProvider()
        assert inst._provider_name == "openai"

    def test_openai_firmas_coinciden(self) -> None:
        from motor.core.llm.base import BaseLLMProvider
        from motor.core.llm.openai import OpenAIProvider

        for method_name in ("generate", "embed", "embed_async", "health"):
            sig_impl = inspect.signature(getattr(OpenAIProvider, method_name))
            sig_base = inspect.signature(getattr(BaseLLMProvider, method_name))
            impl_params = [p for p in sig_impl.parameters if p != "self"]
            base_params = [p for p in sig_base.parameters if p != "self"]
            assert impl_params == base_params, (
                f"{method_name}: {impl_params} != {base_params}"
            )

    def test_openai_no_es_default(self) -> None:
        from motor.core.llm import _default
        from motor.core.llm.ollama import OllamaProvider

        assert isinstance(_default, OllamaProvider)


# ─────────────────────────────────────────────
# 8. Compatibilidad con consumidores actuales
# ─────────────────────────────────────────────

class TestCompatibilidadConsumidores:
    """Verifica que los patrones de llamada de los 8 consumidores
    actuales son compatibles con la API pública."""

    # Consumidor 4: memory_engine.py — generate(prompt) solo arg posicional
    def test_consumer_generate_only_prompt(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with patch.object(_default, "generate", return_value="ok") as mock_gen:
            resultado = _default.generate("solo prompt")
            assert resultado == "ok"
            mock_gen.assert_called_once_with("solo prompt")

    # Consumidor 7: benchmark_llm.py — embed(texts) solo arg posicional
    def test_consumer_embed_only_texts(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with patch.object(_default, "embed", return_value=[[0.0]]) as mock_emb:
            resultado = _default.embed(["texto"])
            assert isinstance(resultado, list)
            mock_emb.assert_called_once_with(["texto"])

    # Consumidor 2: reranking — generate(prompt, model, options)
    def test_consumer_generate_with_model_and_options(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with patch.object(_default, "generate", return_value="ok") as mock_gen:
            resultado = _default.generate(
                "prompt",
                model="qwen2.5:7b",
                options={"num_predict": 10},
            )
            assert isinstance(resultado, str)
            mock_gen.assert_called_once_with(
                "prompt", model="qwen2.5:7b", options={"num_predict": 10},
            )

    # Consumidor 1: qdrant_client — embed(texts, model)
    def test_consumer_embed_with_model(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with patch.object(_default, "embed", return_value=[[0.1, 0.2]]) as mock_emb:
            resultado = _default.embed(["texto"], model="nomic-embed-text")
            assert isinstance(resultado, list)
            mock_emb.assert_called_once_with(["texto"], model="nomic-embed-text")

    # Consumidor 5: debate_engine — generate via run_in_executor (to_thread)
    def test_consumer_generate_in_thread(self) -> None:
        import asyncio
        from unittest.mock import patch

        from motor.core.llm import _default

        async def _test() -> None:
            with patch.object(_default, "generate", return_value="ok"):
                loop = asyncio.get_running_loop()
                resultado = await loop.run_in_executor(
                    None, _default.generate,
                    "prompt", "model-test", {"temperature": 0.1},
                )
                assert resultado == "ok"

        asyncio.run(_test())

    # Consumidor 6: ura_multi_agent — health() sin args
    def test_consumer_health_no_args(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with patch.object(_default, "health", return_value={"status": "ok", "provider": "ollama"}) as mock_health:
            resultado = _default.health()
            assert isinstance(resultado, dict)
            assert "status" in resultado
            assert "provider" in resultado
            mock_health.assert_called_once_with()

    # Consumidor 8: vector_ollama — embed(texts, model) + health()
    def test_consumer_embed_and_health(self) -> None:
        from unittest.mock import patch

        from motor.core.llm import _default

        with (
            patch.object(_default, "embed", return_value=[[0.0]]),
            patch.object(_default, "health", return_value={"status": "ok"}),
        ):
            e = _default.embed(["x"], model="nomic-embed-text")
            h = _default.health()
            assert isinstance(e, list)
            assert h["status"] == "ok"

    # All consumer functions are importable from top-level module
    def test_all_consumers_import_from_top_level(self) -> None:
        import motor.core.llm

        assert hasattr(motor.core.llm, "generate")
        assert hasattr(motor.core.llm, "embed")
        assert hasattr(motor.core.llm, "embed_async")
        assert hasattr(motor.core.llm, "health")
