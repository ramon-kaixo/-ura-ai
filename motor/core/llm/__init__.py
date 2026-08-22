"""LLM — Cliente de inferencia unificado.

Etiqueta v4.0: CANÓNICO 🟢 — providers v2 (motor). Unificación de providers = Fase 2 (Ramón).

Exporta solo comportamiento:
    generate(prompt, model, options) -> str
    embed(texts, model) -> list[list[float]]
    embed_async(texts, model) -> list[list[float]]
    health() -> dict

La selección de proveedor se difiere hasta el primer uso
(build_llm_state en _state.py).
"""

import logging

log = logging.getLogger(__name__)

from typing import Any

_LLM_STATE: Any = None


def _get_state() -> Any:
    global _LLM_STATE  # noqa: PLW0603
    if _LLM_STATE is None:
        from motor.core.llm._state import build_llm_state

        _LLM_STATE = build_llm_state()
    return _LLM_STATE


def generate(prompt: str, model: str | None = None, options: dict[str, object] | None = None) -> str:
    estado = _get_state()
    resultado = estado.generate(prompt, model, options)
    return resultado if isinstance(resultado, str) else str(resultado)


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    estado = _get_state()
    resultado = estado.embed(texts, model)
    return resultado if isinstance(resultado, list) else []


async def embed_async(texts: list[str], model: str | None = None) -> list[list[float]]:
    estado = _get_state()
    resultado = await estado.embed_async(texts, model)
    return resultado if isinstance(resultado, list) else []


def health() -> dict[str, Any]:
    estado = _get_state()
    resultado = estado.health()
    return resultado if isinstance(resultado, dict) else {}


__all__ = ["embed", "embed_async", "generate", "health"]
