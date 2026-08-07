"""BaseLLMProvider — contrato abstracto para proveedores LLM.

Todos los proveedores deben implementar esta interfaz.
La API pública de motor.core.llm (generate, embed, embed_async, health)
delega en una instancia por defecto.
"""

import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

FALLBACK_EMBEDDING_DIMENSION: int = 768

DEFAULT_PROVIDER_CAPABILITIES: dict[str, Any] = {
    "chat": True,
    "embeddings": True,
    "streaming": False,
    "tools": False,
    "json_mode": False,
    "multimodal": False,
    "vision": False,
    "max_context": 4096,
    "max_output": 1024,
}


class BaseLLMProvider(ABC):
    """Contrato abstracto para proveedores de lenguaje."""

    @property
    def capabilities(self) -> dict[str, Any]:
        """Capacidades declarativas del proveedor.

        Retorna dict con claves: chat, embeddings, streaming, tools,
        json_mode, multimodal, vision, max_context, max_output.
        Cada proveedor puede sobrescribir para declarar sus capacidades.
        """
        return dict(DEFAULT_PROVIDER_CAPABILITIES)

    def supports(self, capability: str) -> bool:
        """Verifica si el proveedor soporta una capacidad."""
        caps = self.capabilities
        if capability not in caps:
            return False
        value = caps[capability]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        return bool(value)

    @abstractmethod
    def generate(self, prompt: str, model: str | None = None, options: dict[str, Any] | None = None) -> str: ...

    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Genera con streaming incremental (aditivo, no abstracto).

        Degradación controlada: si el proveedor no implementa streaming real,
        emite el resultado completo de generate() como un único fragmento.
        Los proveedores que lo soporten deben sobrescribir este método.
        """
        yield self.generate(prompt, model, options)

    def chat_generate(
        self,
        mensajes: list,
        model: str | None = None,
        tools: list | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Chat con mensajes y tools opcionales (aditivo, no abstracto).

        Degradación controlada: si el proveedor no implementa tools/mensajes,
        se convierte la conversación a prompt plano y se delega en generate().
        El resultado tiene forma OpenAI: content, tool_calls, usage.
        """
        prompt = "\n".join(
            f"<{m.get('role', 'user')}>{m.get('content', '')}</{m.get('role', 'user')}>" for m in mensajes
        )
        texto = self.generate(prompt, model, options)
        return {"content": texto, "tool_calls": None, "usage": {}}

    @abstractmethod
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...

    @abstractmethod
    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...


class ProviderValidationResult:
    """Resultado de validación de un proveedor."""

    def __init__(self, valid: bool, errors: list[str], provider_name: str = "") -> None:
        self.valid = valid
        self.errors = errors
        self.provider_name = provider_name

    def __repr__(self) -> str:
        if self.valid:
            return f"ProviderValidationResult(valid=True, name={self.provider_name!r})"
        return f"ProviderValidationResult(valid=False, errors={self.errors})"


def validate_provider(provider_cls: type) -> ProviderValidationResult:
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

    if not _validar_heredero(provider_cls, errors):
        return ProviderValidationResult(valid=False, errors=errors)
    instance = _validar_instanciable(provider_cls, errors)
    if instance is None:
        return ProviderValidationResult(valid=False, errors=errors)
    provider_name = _validar_provider_name(instance, errors)
    _validar_metodos(instance, errors)
    _validar_firmas(instance, errors)
    _validar_capacidades(instance, errors)
    _validar_comportamiento(instance, errors)
    return ProviderValidationResult(len(errors) == 0, errors, provider_name)


def _validar_heredero(provider_cls: type, errors: list[str]) -> bool:
    if not issubclass(provider_cls, BaseLLMProvider):
        errors.append("No hereda de BaseLLMProvider")
        return False
    return True


def _validar_instanciable(provider_cls: type, errors: list[str]) -> BaseLLMProvider | None:
    try:
        return provider_cls()
    except Exception as e:
        errors.append(f"No se puede instanciar: {e}")
        return None


def _validar_provider_name(instance: BaseLLMProvider, errors: list[str]) -> str:
    pn = getattr(instance, "_provider_name", None)
    if not pn:
        errors.append("Falta _provider_name o está vacío")
        return ""
    return pn


def _validar_metodos(instance: BaseLLMProvider, errors: list[str]) -> None:
    required_methods = ["generate", "embed", "embed_async", "health"]
    for method_name in required_methods:
        if not hasattr(instance, method_name):
            errors.append(f"Falta método: {method_name}")
            continue
        method = getattr(instance, method_name)
        if not callable(method):
            errors.append(f"{method_name} no es invocable")


def _validar_firmas(instance: BaseLLMProvider, errors: list[str]) -> None:
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


def _validar_capacidades(instance: BaseLLMProvider, errors: list[str]) -> None:
    caps = instance.capabilities
    if not isinstance(caps, dict):
        errors.append("capabilities debe ser un dict")
    if "chat" not in caps:
        errors.append("Falta capacidad 'chat'")


def _validar_comportamiento(instance: BaseLLMProvider, errors: list[str]) -> None:
    try:
        result = instance.generate("test")
        if not isinstance(result, str):
            errors.append("generate() no retorna str")
    except Exception as e:
        errors.append(f"generate('test') lanzó excepción: {e}")

    try:
        result = instance.embed(["test"])
        if not isinstance(result, list):
            errors.append("embed() no retorna list")
    except Exception as e:
        errors.append(f"embed(['test']) lanzó excepción: {e}")


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

        return None
    except (ValueError, TypeError) as e:
        return f"error al inspeccionar firma: {e}"
