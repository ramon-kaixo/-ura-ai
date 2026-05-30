#!/usr/bin/env python3
"""
Instagram Reader - Paso 1A
───────────────────────────
Lector de mensajes de Instagram con callbacks.
"""

from PyQt5.QtWidgets import QMessageBox
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # from main_final import URAMainWindowFinal  # archived
    pass


class InstagramReader:
    """Lector de mensajes de Instagram."""

    def __init__(self, parent: Any):
        """Inicializar lector de Instagram."""
        self.parent = parent
        self.thread = None

    def start(self):
        """Iniciar lectura de Instagram."""
        from services.messaging import read_instagram

        read_instagram(self.parent)

    def stop(self):
        """Detener lectura de Instagram."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def on_finished(self, messages):
        """Callback cuando la lectura termina."""
        try:
            from core.instagram_reader import mostrar_dms_instagram_en_consola

            mostrar_dms_instagram_en_consola(messages)
            if messages:
                summary = f"{len(messages)} DMs no leídos\n\n"
                for i, msg in enumerate(messages[:5], 1):
                    media_icon = (
                        "📷"
                        if msg.media_type == "photo"
                        else "🎥"
                        if msg.media_type == "video"
                        else ""
                    )
                    summary += f"{i}. @{msg.from_username}: {msg.text[:50]}... {media_icon}\n"
                if len(messages) > 5:
                    summary += f"... y {len(messages) - 5} más\n"
                QMessageBox.information(self.parent, "Instagram - DMs Leídos", summary)
            else:
                QMessageBox.information(self.parent, "Instagram", "No hay DMs no leídos")
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Error mostrando DMs: {str(e)}")

    def on_error(self, error_msg):
        """Callback cuando hay un error."""
        QMessageBox.warning(self.parent, "Error Instagram", f"Error: {error_msg}")
