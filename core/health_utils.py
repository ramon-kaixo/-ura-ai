#!/usr/bin/env python3
"""
Health Utils - Paso 3A
───────────────────────
Utilidades para informes de salud.
"""

import logging

logger = logging.getLogger(__name__)


def handle_health_report_command(window):
    """Manejar comando de voz 'informe de salud'."""
    from handlers.handler_utils import get_health_report_from_file

    report = get_health_report_from_file()
    if report:
        window.chat_ura(report)
    else:
        window.chat_alert("No se pudo generar informe de salud")
