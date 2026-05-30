#!/usr/bin/env python3
"""
Telegram Reader - Paso 1A
──────────────────────────
Lector de mensajes de Telegram con callbacks.
"""

from PyQt5.QtWidgets import QMessageBox
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # from main_final import URAMainWindowFinal  # archived
    pass


class TelegramReader:
    """Lector de mensajes de Telegram."""

    def __init__(self, parent: Any):
        """Inicializar lector de Telegram."""
        self.parent = parent
        self.thread = None

    def start(self):
        """Iniciar lectura de Telegram."""
        from services.messaging import read_telegram

        read_telegram(self.parent)

    def stop(self):
        """Detener lectura de Telegram."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def on_finished(self, messages):
        """Callback cuando la lectura termina."""
        try:
            from core.telegram_reader import mostrar_mensajes_telegram_en_consola

            mostrar_mensajes_telegram_en_consola(messages)
            if messages:
                summary = f"{len(messages)} mensajes no leídos\n\n"
                for i, msg in enumerate(messages[:5], 1):
                    chat_type = "👥" if msg.is_group else "👤"
                    summary += f"{i}. {chat_type} {msg.chat_name}: {msg.from_name}\n"
                    summary += f"   💬 {msg.text[:50]}...\n"
                if len(messages) > 5:
                    summary += f"... y {len(messages) - 5} más\n"
                QMessageBox.information(self.parent, "Telegram - Mensajes Leídos", summary)
            else:
                QMessageBox.information(self.parent, "Telegram", "No hay mensajes no leídos")
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Error mostrando mensajes: {str(e)}")

    def on_error(self, error_msg):
        """Callback cuando hay un error."""
        QMessageBox.warning(self.parent, "Error Telegram", f"Error: {error_msg}")
