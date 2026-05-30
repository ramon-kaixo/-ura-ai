#!/usr/bin/env python3
"""
Vision Callbacks - Paso 3A
──────────────────────────
Callbacks para visión de pantalla.
"""

import logging

logger = logging.getLogger(__name__)


def _on_vision_ready(window, image_path: str, description: str):
    """Captura lista + descripción de llava."""
    window.hide_progress()
    # 1) Mensaje en el chat central (URA responde con lo que ha visto)
    window.chat_ura(f"👁️ Esto es lo que veo en tu pantalla:\n\n{description}")
    # 2) Previsualizar la imagen en el panel derecho
    from config.constants import WEBENGINE_AVAILABLE
    from PyQt5.QtCore import QUrl

    if WEBENGINE_AVAILABLE and getattr(window, "web_view", None) is not None:
        html = (
            "<html><body style='background:#1a1a2e; color:#eee; display:flex; align-items:center; justify-content:center; height:100vh;'>"
            f"<img src='file://{image_path}' style='max-width:95%; max-height:90%; border-radius:8px;' />"
            "</body></html>"
        )
        window.web_view.setHtml(html, QUrl.fromLocalFile(image_path))
        window.viewer_title.setText("👁️ URA ve tu pantalla")
        window._show_viewer(width=600)
    # 3) Contexto: dejarla como respuesta pendiente para Windsurf si quieres
    window.pending_ura_response = description
    window.ura_pending_text.setPlainText(description)
