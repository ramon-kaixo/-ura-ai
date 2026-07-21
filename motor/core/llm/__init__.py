"""LLM — Cliente de inferencia unificado.

Exporta solo comportamiento:
    generate(prompt, model, options) -> str
    embed(texts, model) -> list[list[float]]
    embed_async(texts, model) -> list[list[float]]
    health() -> dict

La selección de proveedor se difiere hasta el primer uso
(build_llm_state en _state.py).
"""

import logging
import warnings

log = logging.getLogger(__name__)

_LLM_STATE = None


def _get_state():
    global _LLM_STATE  # noqa: PLW0603
    if _LLM_STATE is None:
        from motor.core.llm._state import build_llm_state

        _LLM_STATE = build_llm_state()
    return _LLM_STATE


def generate(prompt: str, model: str | None = None, options: dict | None = None) -> str:
    return _get_state().generate(prompt, model, options)


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    return _get_state().embed(texts, model)


async def embed_async(texts: list[str], model: str | None = None) -> list[list[float]]:
    return await _get_state().embed_async(texts, model)


def health() -> dict:
    return _get_state().health()


def __getattr__(name):
    if name == "registry":
        warnings.warn(
            "motor.core.llm.registry is deprecated. Use motor.core.llm._state.build_llm_state().registry.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _get_state().registry
    if name == "_default":
        warnings.warn(
            "motor.core.llm._default is deprecated. Use motor.core.llm._state.build_llm_state().default_provider.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _get_state().default_provider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["embed", "embed_async", "generate", "health"]
