#!/usr/bin/env python3
"""
core/langchain_bridge.py - Wrapper inactivo para LangChain
Solo importa LangChain si está disponible y expone is_available()
No conecta a nada de URA todavía.
"""

import logging

logger = logging.getLogger(__name__)

# Intentar importar LangChain si está disponible
_LANGCHAIN_AVAILABLE = False
_LANGCHAIN_ERROR = None

try:
    from langchain_ollama import OllamaLLM

    _LANGCHAIN_AVAILABLE = True
    logger.info("LangChain disponible")
except ImportError as e:
    _LANGCHAIN_AVAILABLE = False
    _LANGCHAIN_ERROR = str(e)
    logger.info(f"LangChain no disponible: {e}")


def is_available() -> bool:
    """Devuelve True si LangChain está instalado y disponible"""
    return _LANGCHAIN_AVAILABLE


def get_error() -> str | None:
    """Devuelve el error si LangChain no está disponible"""
    return _LANGCHAIN_ERROR


def get_ollama_llm(model: str = None, **kwargs):
    """
    Devuelve una instancia de OllamaLLM si LangChain está disponible
    Args:
        model: Modelo a usar
        **kwargs: Argumentos adicionales para OllamaLLM
    Returns:
        OllamaLLM si LangChain está disponible, None en caso contrario
    """
    if not _LANGCHAIN_AVAILABLE:
        logger.warning("LangChain no disponible, no se puede crear OllamaLLM")
        return None

    try:
        if model:
            return OllamaLLM(model=model, **kwargs)
        else:
            return OllamaLLM(**kwargs)
    except Exception as e:
        logger.error(f"Error creando OllamaLLM: {e}")
        return None


if __name__ == "__main__":
    print(f"LangChain disponible: {is_available()}")
    if not is_available():
        print(f"Error: {get_error()}")
