#!/usr/bin/env python3
"""
Clean Utils - Paso 3A
──────────────────────
Utilidades para limpieza segura.
"""

import logging

logger = logging.getLogger(__name__)


def _on_clean_done(window, authorized: bool, borrados: int, errores: int):
    """Callback cuando la limpieza está completa."""
    window.clean_safe_button.setEnabled(True)
    window.clean_safe_button.setText("🧹 Limpieza Segura")
    if not authorized:
        window.chat_ura(
            "Limpieza cancelada: autorización no concedida. Ningún archivo ha sido borrado."
        )
        return
    window.chat_ura(f"🧹 Limpieza completada: {borrados} elementos eliminados, {errores} errores.")
