"""Tests de validación de contrato de proveedores (F22-B1).

Verifica:
1. Proveedor válido pasa validación
2. Proveedor inválido es rechazado
3. Capacidades (métodos requeridos)
4. Compatibilidad con Registry
5. Compatibilidad con Router
6. Health check contract
"""

from __future__ import annotations

from motor.core.llm.base import BaseLLMProvider, ProviderValidationResult, validate_provider
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _ValidProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._provider_name = "valid_test"
    def generate(self, prompt, model=None, options=None):
        return "ok"
    def embed(self, texts, model=None):
        return [[0.0]]
    async def embed_async(self, texts, model=None):
        return [[0.0]]
    def health(self):
        return {"provider": "valid_test", "status": "ok", "latency_ms": 0}


class _NoNameProvider(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        return "ok"
    def embed(self, texts, model=None):
        return [[0.0]]
    async def embed_async(self, texts, model=None):
        return [[0.0]]
    def health(self):
        return {"status": "ok"}


class _MissingMethod(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        return "ok"
    # Falta embed y embed_async
    def health(self):
        return {"status": "ok"}


class _WrongReturn(BaseLLMProvider):
    def __init__(self) -> None:
        self._provider_name = "wrong_return"
    def generate(self, prompt, model=None, options=None):
        return 123  # Debe retornar str
    def embed(self, texts, model=None):
        return "not_a_list"  # Debe retornar list
    async def embed_async(self, texts, model=None):
        return [[0.0]]
    def health(self):
        return {"status": "ok"}


class TestProviderContractValidation:
    def test_valid_provider(self) -> None:
        result = validate_provider(_ValidProvider)
        assert result.valid, f"Errors: {result.errors}"
        assert result.provider_name == "valid_test"

    def test_invalid_provider_rejected(self) -> None:
        """Proveedor sin _provider_name debe fallar."""
        result = validate_provider(_NoNameProvider)
        assert not result.valid

    def test_missing_method_rejected(self) -> None:
        """Proveedor sin embed/embed_async debe fallar."""
        result = validate_provider(_MissingMethod)
        assert not result.valid
        assert any("embed" in e for e in result.errors)

    def test_wrong_return_type(self) -> None:
        """Proveedor con tipo de retorno incorrecto debe fallar."""
        result = validate_provider(_WrongReturn)
        assert not result.valid

    def test_non_subclass_rejected(self) -> None:
        """Clase que no hereda de BaseLLMProvider debe fallar."""
        class _NotAProvider:
            def generate(self, prompt, model=None, options=None):
                return "ok"
            def embed(self, texts, model=None):
                return [[0.0]]
            async def embed_async(self, texts, model=None):
                return [[0.0]]
            def health(self):
                return {"status": "ok"}
        result = validate_provider(_NotAProvider)
        assert not result.valid
        assert "No hereda" in result.errors[0]

    def test_provider_registry_compatibility(self) -> None:
        """Proveedor validado debe funcionar con el Registry."""
        result = validate_provider(_ValidProvider)
        assert result.valid
        reg = ProviderRegistry()
        reg.register("valid", _ValidProvider(), default=True)
        assert "valid" in reg
        assert reg.default is not None

    def test_provider_router_compatibility(self) -> None:
        """Proveedor validado debe funcionar con el Router."""
        reg = ProviderRegistry()
        reg.register("v", _ValidProvider(), default=True)
        router = LLMRouter(registry=reg)
        response = router.generate("test")
        assert response == "ok"

    def test_provider_health_contract(self) -> None:
        """health() debe retornar dict con status."""
        p = _ValidProvider()
        h = p.health()
        assert isinstance(h, dict)
        assert "status" in h

    def test_validation_result_repr(self) -> None:
        r = ProviderValidationResult(True, [], "test")
        assert "valid=True" in repr(r)
        r2 = ProviderValidationResult(False, ["error1"])
        assert "valid=False" in repr(r2)
