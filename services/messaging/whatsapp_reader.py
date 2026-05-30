#!/usr/bin/env python3
"""
WhatsApp Reader - Paso 1A
─────────────────────────
Lector de mensajes de WhatsApp con callbacks.
"""

from PyQt5.QtWidgets import QMessageBox
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # from main_final import URAMainWindowFinal  # archived
    pass


class WhatsAppReader:
    """Lector de mensajes de WhatsApp."""

    def __init__(self, parent: Any):
        """Inicializar lector de WhatsApp."""
        self.parent = parent
        self.thread = None

    def start(self):
        """Iniciar lectura de WhatsApp."""
        from services.messaging import read_whatsapp

        read_whatsapp(self.parent)

    def stop(self):
        """Detener lectura de WhatsApp."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def on_finished(self, chats):
        """Callback cuando la lectura termina."""
        try:
            from core.whatsapp_reader import mostrar_mensajes_en_consola

            mostrar_mensajes_en_consola(chats)
            if chats:
                total_unread = sum(chat["unread_count"] for chat in chats)
                summary = f"{len(chats)} chats con {total_unread} mensajes no leídos\n\n"
                for i, chat in enumerate(chats[:5], 1):
                    summary += f"{i}. {chat['name']}: {chat['unread_count']} mensajes\n"
                if len(chats) > 5:
                    summary += f"... y {len(chats) - 5} más\n"
                QMessageBox.information(self.parent, "WhatsApp - Mensajes Leídos", summary)
            else:
                QMessageBox.information(self.parent, "WhatsApp", "No hay mensajes no leídos")
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Error mostrando mensajes: {str(e)}")

    def on_error(self, error_msg):
        """Callback cuando hay un error."""
        QMessageBox.warning(self.parent, "Error WhatsApp", f"Error: {error_msg}")
