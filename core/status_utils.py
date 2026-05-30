#!/usr/bin/env python3
"""
Status Utils - Paso 3A
───────────────────────
Utilidades para generación de status diario.
"""

import logging
import threading

logger = logging.getLogger(__name__)


def _generate_daily_status(window):
    """Generar reporte de status diario."""
    try:
        window.chat_alert("📊 Generando reporte de status diario...")

        def _gen():
            try:
                from handlers.handler_utils import save_status_report

                path = save_status_report()
                logger.info("STATUS.md generado: %s", path)
                window.chat_alert(f"✅ Status diario generado: {path}")
            except Exception as exc:
                logger.warning("daily_status_report falló: %s", exc)
                window.chat_alert("❌ Error generando status diario")

        threading.Thread(target=_gen, daemon=True).start()
    except Exception as exc:
        logger.warning("_generate_daily_status falló: %s", exc)
