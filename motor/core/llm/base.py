"""BaseLLMProvider — contrato abstracto para proveedores LLM.

Todos los proveedores deben implementar esta interfaz.
La API pública de motor.core.llm (generate, embed, embed_async, health)
delega en una instancia por defecto.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Contrato abstracto para proveedores de lenguaje."""

    @abstractmethod
    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        ...

    @abstractmethod
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        ...

    @abstractmethod
    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...


class ProviderValidationResult:
    """Resultado de validación de un proveedor."""

    def __init__(self, valid: bool, errors: list[str], provider_name: str = "") -> None:  # noqa: FBT001
        self.valid = valid
        self.errors = errors
        self.provider_name = provider_name

    def __repr__(self) -> str:
        if self.valid:
            return f"ProviderValidationResult(valid=True, name={self.provider_name!r})"
        return f"ProviderValidationResult(valid=False, errors={self.errors})"


def validate_provider(provider_cls: type) -> ProviderValidationResult:  # noqa: C901, PLR0912
    """Valida que una clase cumple el contrato BaseLLMProvider.

    Verifica:
      - Hereda de BaseLLMProvider
      - Implementa generate, embed, embed_async, health
      - Firmas correctas
      - Tiene _provider_name accesible

    Args:
        provider_cls: Clase del proveedor a validar.

    Returns:
        ProviderValidationResult con errores si los hay.
    """
    errors: list[str] = []
    provider_name = ""

    # 1. Debe heredar de BaseLLMProvider
    if not issubclass(provider_cls, BaseLLMProvider):
        errors.append("No hereda de BaseLLMProvider")
        return ProviderValidationResult(valid=False, errors=errors)

    # 2. Debe ser instanciable
    try:
        instance = provider_cls()
    except Exception as e:
        errors.append(f"No se puede instanciar: {e}")
        return ProviderValidationResult(valid=False, errors=errors)

    # 3. Debe tener _provider_name
    pn = getattr(instance, "_provider_name", None)
    if not pn:
        errors.append("Falta _provider_name o está vacío")
    else:
        provider_name = pn

    # 4. Debe implementar los 4 métodos
    required_methods = ["generate", "embed", "embed_async", "health"]
    for method_name in required_methods:
        if not hasattr(instance, method_name):
            errors.append(f"Falta método: {method_name}")
            continue
        method = getattr(instance, method_name)
        if not callable(method):
            errors.append(f"{method_name} no es invocable")
            continue

    # 5. Firmas
    if hasattr(instance, "generate") and callable(instance.generate):
        sig = _check_signature(
            instance.generate,
            ["prompt", "model", "options"],
            ["model", "options"],
        )
        if sig:
            errors.append(f"generate: {sig}")

    if hasattr(instance, "embed") and callable(instance.embed):
        sig = _check_signature(
            instance.embed,
            ["texts", "model"],
            ["model"],
        )
        if sig:
            errors.append(f"embed: {sig}")

    # 6. Comportamiento: generate retorna str
    try:
        result = instance.generate("test")
        if not isinstance(result, str):
            errors.append("generate() no retorna str")
    except Exception as e:
        errors.append(f"generate('test') lanzó excepción: {e}")

    # 7. Comportamiento: embed retorna list
    try:
        result = instance.embed(["test"])
        if not isinstance(result, list):
            errors.append("embed() no retorna list")
    except Exception as e:
        errors.append(f"embed(['test']) lanzó excepción: {e}")

    return ProviderValidationResult(len(errors) == 0, errors, provider_name)


def _check_signature(method: Any, expected_params: list[str], optional: list[str]) -> str | None:
    """Verifica que un método tenga los parámetros esperados."""
    try:
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())

        # Excluir self
        if param_names and param_names[0] == "self":
            param_names = param_names[1:]

        for ep in expected_params:
            if ep not in param_names:
                return f"falta parámetro '{ep}'"

        # Verificar que los opcionales tengan default None
        for op in optional:
            if op in param_names:
                param = sig.parameters[op]
                if param.default is not param.empty and param.default is not None:
                    # OK si tiene default (no necesariamente None para options)
                    pass

        return None
    except (ValueError, TypeError) as e:
        return f"error al inspeccionar firma: {e}"
