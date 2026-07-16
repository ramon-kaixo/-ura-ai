"""LLM — Cliente de inferencia unificado.

Exporta solo comportamiento:
    generate(prompt, model, options) -> str
    embed(texts, model) -> list[list[float]]
    embed_async(texts, model) -> list[list[float]]
    health() -> dict

La instancia por defecto es OllamaProvider. La selección de proveedor
se realiza mediante router + registry (ver F18).
"""

from motor.core.llm.ollama import OllamaProvider

_default = OllamaProvider()
generate = _default.generate
embed = _default.embed
embed_async = _default.embed_async
health = _default.health

__all__ = ["embed", "embed_async", "generate", "health"]
