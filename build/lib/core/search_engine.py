#!/usr/bin/env python3
"""Search Engine - Búsqueda simple en documentos indexados."""

import logging

from core.memory_engine import query, rag_enabled

log = logging.getLogger(__name__)


def search(query_str: str, top_k: int = 5) -> list[dict]:
    """Busca documentos relevantes para una query.

    Args:
        query_str: La query de búsqueda
        top_k: Número máximo de resultados a devolver

    Returns:
        Lista de diccionarios con resultados {content, source, chunk_index, similarity}

    """
    if not rag_enabled():
        log.warning("RAG no está habilitado")
        return []

    if not query_str:
        log.warning("Query vacía")
        return []

    try:
        results = query(query_str, top_k=top_k)
        log.info(f"Búsqueda completada: {len(results)} resultados para '{query_str[:50]}...'")
        return results
    except Exception as e:
        log.exception(f"Error en búsqueda: {e}")
        return []
