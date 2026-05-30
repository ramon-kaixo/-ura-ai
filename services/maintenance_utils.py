#!/usr/bin/env python3
"""
Maintenance Utils - Paso 3A
────────────────────────────
Utilidades para mantenimiento del sistema.
"""

import logging

logger = logging.getLogger(__name__)


def _on_maintenance_report(window, report):
    """URA ha actuado por su cuenta: se lo cuenta a Ramón."""
    try:
        summary = report.summary_text()
    except Exception:
        summary = "🤖 Mantenimiento automático ejecutado."
    # Solo notificamos si hubo acciones reales, para no molestar con "nada que hacer"
    if getattr(report, "actions", None):
        window.chat_ura(summary)
        logger.info("[autonomous_maintenance] %s", summary.replace("\n", " | "))


def _check_disk_space(window):
    """Verificar espacio en disco y advertir si es bajo."""
    if not config.disk_monitor_available:
        return

    import shutil

    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024**3)

    if free_gb < 20 and not window._disk_warning_shown:
        window.chat_alert(f"⚠️ Espacio en disco bajo: {free_gb:.1f} GB restantes")
        window._disk_warning_shown = True
    elif free_gb >= 20:
        window._disk_warning_shown = False

    logger.debug(f"Espacio en disco: {free_gb:.1f} GB libre")


def _run_port_scan(window):
    """Ejecutar escaneo de puertos."""
    if window.network_audit:
        try:
            window.network_audit.run_port_scan()
            logger.info("Port scan completado")
        except Exception as e:
            logger.warning(f"Port scan falló: {e}")


def _run_thread_clean(window):
    """Limpieza periódica de hilos zombie (QTimer 5 min)."""
    try:
        import threading

        threading.Thread(target=window.thread_cleaner.full_cleanup, daemon=True).start()
        logger.debug("Thread clean iniciado en background")
    except Exception as exc:
        logger.warning("Thread clean falló: %s", exc)
