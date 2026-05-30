#!/usr/bin/env python3
"""
Panel Utils - Paso 3A
──────────────────────
Utilidades para paneles y visores.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def show_progress(window):
    """Mostrar barra de progreso."""
    if hasattr(window, "progress_bar"):
        window.progress_bar.setVisible(True)
        window.progress_bar.setRange(0, 0)  # Indeterminado


def hide_progress(window):
    """Ocultar barra de progreso."""
    if hasattr(window, "progress_bar"):
        window.progress_bar.setVisible(False)


def show_web_url(window, url: str):
    """Mostrar URL en visor web."""
    if hasattr(window, "web_view") and window.web_view:
        window.web_view.setUrl(url)
        window.viewer_title.setText(f"Web: {url}")
        window._show_viewer(width=800)


def show_pdf_file(window, path: str):
    """Mostrar PDF en visor."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        window.chat_alert(f"PDF no encontrado: {path}")
        return

    if hasattr(window, "web_view") and window.web_view:
        window.web_view.setUrl(f"file://{pdf_path}")
        window.viewer_title.setText(f"PDF: {pdf_path.name}")
        window._show_viewer(width=800)


def hide_viewer(window):
    """Ocultar el visor lateral."""
    if hasattr(window, "viewer_panel"):
        window.viewer_panel.hide()


def load_url_from_input(window):
    """Cargar URL desde input del visor."""
    url = window.viewer_url_input.text().strip()
    if not url:
        return
    show_web_url(window, url)


def show_progress(window):
    """Mostrar barra de progreso neón."""
    window.progress_bar.show()


def hide_progress(window):
    """Ocultar barra de progreso neón."""
    window.progress_bar.hide()
