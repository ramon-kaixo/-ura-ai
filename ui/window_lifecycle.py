#!/usr/bin/env python3
"""
Window Lifecycle - Paso 3A
───────────────────────────
Ciclo de vida de la ventana (closeEvent, etc.).
"""

import logging

logger = logging.getLogger(__name__)


def close_event(window, event):
    """Manejar evento de cierre de ventana."""
    # Indicar que la aplicación se está cerrando
    window._is_closing = True

    # Detener mantenimiento autónomo
    if hasattr(window, "_autonomous_maintenance"):
        window._autonomous_maintenance.detener()

    # Ejecutar limpieza completa de hilos
    if window.thread_cleaner:
        try:
            logger.info("Ejecutando limpieza completa de hilos al cerrar...")
            cleanup_results = window.thread_cleaner.full_cleanup()
            logger.info(f"Resultados de limpieza: {cleanup_results}")
        except Exception as e:
            logger.warning(f"Error en limpieza de hilos: {e}")

    # Detener timers
    if hasattr(window, "monitor_timer"):
        window.monitor_timer.stop()
    if hasattr(window, "disk_timer"):
        window.disk_timer.stop()
    if hasattr(window, "port_scan_timer"):
        window.port_scan_timer.stop()
    if hasattr(window, "thread_clean_timer"):
        window.thread_clean_timer.stop()

    # Detener hilos de voz
    if hasattr(window, "voice_recognizer") and window.voice_recognizer:
        try:
            window.voice_recognizer.stop_listening()
        except Exception as e:
            logger.warning(f"Error deteniendo reconocimiento de voz: {e}")

    if hasattr(window, "tts_engine") and window.tts_engine:
        try:
            window.tts_engine.stop()
        except Exception as e:
            logger.warning(f"Error deteniendo TTS: {e}")

    # Guardar configuración
    window.save_config()

    # Aceptar el evento de cierre
    event.accept()
    logger.info("Aplicación cerrada correctamente")
