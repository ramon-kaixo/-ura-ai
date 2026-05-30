#!/usr/bin/env python3
"""
Email Reader - Paso 1A
────────────────────────
Lector de mensajes de Email con callbacks.
"""

from PyQt5.QtWidgets import QMessageBox
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # from main_final import URAMainWindowFinal  # archived
    pass


class EmailReader:
    """Lector de mensajes de Email."""

    def __init__(self, parent: Any):
        """Inicializar lector de Email."""
        self.parent = parent
        self.thread = None

    def start(self):
        """Iniciar lectura de Email."""
        from services.messaging import read_email

        read_email(self.parent)

    def stop(self):
        """Detener lectura de Email."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def on_finished(self, emails):
        """Callback cuando la lectura termina."""
        try:
            from core.email_reader import mostrar_correos_en_consola

            mostrar_correos_en_consola(emails)
            if emails:
                summary = f"{len(emails)} correos no leídos\n\n"
                for i, email in enumerate(emails[:5], 1):
                    attachment_info = " 📎" if email.has_attachments else ""
                    summary += f"{i}. {email.from_name}: {email.subject}{attachment_info}\n"
                if len(emails) > 5:
                    summary += f"... y {len(emails) - 5} más\n"
                QMessageBox.information(self.parent, "Correo - Mensajes Leídos", summary)
            else:
                QMessageBox.information(self.parent, "Correo", "No hay correos no leídos")
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Error mostrando correos: {str(e)}")

    def on_error(self, error_msg):
        """Callback cuando hay un error."""
        QMessageBox.warning(self.parent, "Error Correo", f"Error: {error_msg}")
