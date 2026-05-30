#!/usr/bin/env python3
"""
Search Callbacks - Paso 3A
───────────────────────────
Callbacks para búsqueda web.
"""

import logging

logger = logging.getLogger(__name__)


def _on_search_ready(window, result: dict):
    """Callback cuando la búsqueda está lista."""
    window.hide_progress()
    query = result.get("query", "?")
    summary = result.get("summary", "").strip() or "(sin resumen)"
    fuentes = result.get("results", []) or []

    window.chat_ura(f"🌐 Búsqueda: **{query}**\n\n{summary}")
    window.pending_ura_response = summary
    window.ura_pending_text.setPlainText(summary)

    # Abrir el primer resultado en el visor lateral si hay WebEngine
    from config.constants import WEBENGINE_AVAILABLE
    from PyQt5.QtCore import QUrl

    if WEBENGINE_AVAILABLE and getattr(window, "web_view", None) is not None and fuentes:
        first_url = next((r.get("href") for r in fuentes if r.get("href")), None)
        if first_url:
            try:
                window.web_view.setUrl(QUrl(first_url))
                window.viewer_title.setText(f"🌐 {query}")
                window._show_viewer(width=600)
            except Exception as e:
                logger.warning(f"Error abriendo URL: {e}")


def _on_search_failed(window, error: str):
    """Callback cuando la búsqueda falla."""
    window.hide_progress()
    window.chat_alert(f"Error en búsqueda: {error}")
