#!/usr/bin/env python3
"""
Chat Utils - Paso 3A
────────────────────
Utilidades para chat y mensajes en UI.
"""

import logging
import time

logger = logging.getLogger(__name__)


def chat_user(window, text: str) -> None:
    """Mostrar mensaje del usuario en el chat."""
    timestamp = time.strftime("%H:%M:%S")
    html = (
        f"<div style='margin:6px 0; color:#6c757d; font-weight:400;'>"
        f"<span style='color:#888; font-weight:400;'>[{timestamp}]</span> "
        f"<span style='color:#28a745; font-weight:600;'>Tú:</span> "
        f"{escape_html(text)}</div>"
    )
    window.ura_history_text.append(html)


def chat_ura(window, text: str) -> None:
    """Mostrar mensaje de URA en el chat."""
    timestamp = time.strftime("%H:%M:%S")
    html = (
        f"<div style='margin:6px 0; color:#007bff; font-weight:600;'>"
        f"<span style='color:#888; font-weight:400;'>[{timestamp}]</span> "
        f"<span style='color:#007bff; font-weight:600;'>URA:</span> "
        f"{escape_html(text)}</div>"
    )
    window.ura_history_text.append(html)


def chat_alert(window, text: str, target: str = "ura") -> None:
    """Mostrar alerta en el chat."""
    timestamp = time.strftime("%H:%M:%S")
    html = (
        f"<div style='margin:6px 0; color:#dc3545; font-weight:600;'>"
        f"<span style='color:#888; font-weight:400;'>[{timestamp}]</span> "
        f"<span style='color:#dc3545; font-weight:600;'>⚠️ {target.upper()}:</span> "
        f"{escape_html(text)}</div>"
    )
    window.ura_history_text.append(html)


def escape_html(text: str) -> str:
    """Escapar caracteres HTML para visualización segura."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    )
