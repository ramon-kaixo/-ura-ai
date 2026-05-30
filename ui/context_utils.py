#!/usr/bin/env python3
"""
Context Utils - Paso 3A
────────────────────────
Utilidades para gestión de contexto.
"""

import logging

logger = logging.getLogger(__name__)


def clear_context(window):
    """Limpiar contexto completo."""
    window.windsurf_history_text.clear()
    window.ura_history_text.clear()
    window.ura_pending_text.clear()
    window.windsurf_context_text.clear()
    window.ura_context_text.clear()
    logger.info("Contexto limpiado")
