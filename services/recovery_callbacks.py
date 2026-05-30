#!/usr/bin/env python3
"""
Recovery Callbacks - Paso 3A
──────────────────────────────
Callbacks para recuperación y limpieza.
"""

import logging
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QUrl

logger = logging.getLogger(__name__)


def _on_recovery_finished(window, report):
    """Callback al terminar Recuperación Inteligente: abre el visor con el informe HTML."""
    window.hide_progress()
    window.smart_recovery_button.setEnabled(True)
    window.smart_recovery_button.setText("🛟 Recuperación Inteligente")

    html = report.to_html()
    from config.constants import WEBENGINE_AVAILABLE, APP_PATH

    if WEBENGINE_AVAILABLE and getattr(window, "web_view", None) is not None:
        window.web_view.setHtml(html, QUrl("about:blank"))
        window.viewer_title.setText("🛟 Recuperación Inteligente · Informe")
        window._show_viewer(width=600)
    else:
        # Fallback: guardar el informe y avisar
        report_path = (
            APP_PATH
            / "logs"
            / f"recuperacion_inteligente_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        try:
            report_path.write_text(html, encoding="utf-8")
            QMessageBox.information(
                window, "Recuperación Inteligente", f"Informe guardado en:\n{report_path}"
            )
        except Exception as e:
            logger.error(f"Error guardando informe: {e}")
            QMessageBox.warning(window, "Error", f"No se pudo guardar el informe: {e}")


def _on_clean_list_ready(window, list_path_str: str, contenido: str):
    """Lista generada en segundo plano → pintar visor y pedir Face ID."""
    list_path = Path(list_path_str)
    html = (
        "<html><body style='font-family:monospace; background:#fffbe6; color:#222; padding:14px;'>"
        "<h2 style='color:#b45309;'>🧹 Limpieza Segura · Vista previa</h2>"
        "<p><b>Nada se ha borrado todavía.</b> Revisa la lista y confirma con Face ID.</p>"
        f"<pre style='white-space:pre-wrap; font-size:12px;'>{window._escape_html(contenido)}</pre>"
        "</body></html>"
    )
    from config.constants import WEBENGINE_AVAILABLE

    if WEBENGINE_AVAILABLE and getattr(window, "web_view", None) is not None:
        window.web_view.setHtml(html, QUrl("about:blank"))
        window.viewer_title.setText("🧹 Limpieza Segura · Candidatos")
        window._show_viewer(width=600)

    window.chat_ura(
        "🧹 Lista de limpieza generada. Revisa el visor y confirma con Face ID para proceder."
    )

    if not config.security_policy_available or require_authorization is None:
        window.chat_alert("Módulo de seguridad no disponible; no se procederá al borrado.")
        window.clean_safe_button.setEnabled(True)
        window.clean_safe_button.setText("🧹 Limpieza Segura")
        return

    # Autorización y borrado también en hilo (require_authorization puede bloquear)
    window.clean_safe_button.setText("🧹 Esperando Face ID…")
    window._auth_thread = _CleanSafeAuthThread(list_path, contenido)
    window._auth_thread.finished_auth.connect(window._on_clean_done)
    window._auth_thread.start()


def _on_clean_list_failed(window, error: str):
    """Callback cuando falla la generación de lista de limpieza."""
    window.clean_safe_button.setEnabled(True)
    window.clean_safe_button.setText("🧹 Limpieza Segura")
    window.chat_alert(f"No se pudo generar la lista de limpieza: {error}")


def _on_vision_failed(window, error: str):
    """Callback cuando falla la visión."""
    window.hide_progress()
    window.chat_alert(f"No pude mirar la pantalla: {error}")
