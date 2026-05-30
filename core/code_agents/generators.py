"""Stub: Generador de código automático para auto-repair."""

import logging

log = logging.getLogger(__name__)


def generar(spec: str, language: str = "python") -> str:
    """Genera código basado en una especificación. TODO: integrar con LLM."""
    log.info("Generador invocado (stub): %s", spec[:50] if spec else "")
    return f"# TODO: implementar — {spec}"
