"""LLM — Cliente de inferencia unificado.

Exporta solo comportamiento:
    generate(prompt, model, options) -> str
    embed(texts, model) -> list[list[float]]
    health() -> dict
"""

from motor.core.llm.ollama import embed, embed_async, generate, health

__all__ = ["embed", "embed_async", "generate", "health"]
