"""Interfaz de cliente LLM (definición canónica en motor/)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ILLMClient(Protocol):
    """Contrato para inferencia LLM (generate + health)."""

    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str: ...

    def health(self) -> dict: ...
