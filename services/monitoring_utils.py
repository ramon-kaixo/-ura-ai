#!/usr/bin/env python3
"""
Monitoring Utils - Paso 3A
───────────────────────────
Utilidades para monitoreo y actualización de estado.
"""

import logging
import time

logger = logging.getLogger(__name__)


def update_cursor_speed(window, value):
    """Actualizar velocidad del cursor."""
    window.config["cursor_speed"] = value
    logger.info(f"Velocidad del cursor actualizada: {value}")


def update_ollama_status(window, connected):
    """Actualizar estado de conexión Ollama."""
    if connected:
        window.ollama_status_label.setText("🟢 Ollama: Conectado")
        window.ollama_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
    else:
        window.ollama_status_label.setText("🔴 Ollama: Desconectado")
        window.ollama_status_label.setStyleSheet("color: #dc3545; font-weight: bold;")


def update_context_with_maintenance(window, message):
    """Actualizar panel Contexto (10%) con mensajes de mantenimiento."""
    timestamp = time.strftime("%H:%M:%S")
    window.ura_context_text.append(f"[{timestamp}] {message}")

    # Auto-scroll

    cursor = window.ura_context_text.textCursor()
    cursor.movePosition(cursor.End)
    window.ura_context_text.setTextCursor(cursor)


def update_context_with_terminal(window, message):
    """Actualizar panel Contexto con mensajes de terminal."""
    timestamp = time.strftime("%H:%M:%S")
    window.ura_context_text.append(f"[{timestamp}] 🖥️ {message}")

    # Auto-scroll

    cursor = window.ura_context_text.textCursor()
    cursor.movePosition(cursor.End)
    window.ura_context_text.setTextCursor(cursor)


def start_ollama_checker(window):
    """Iniciar checker de Ollama."""
    from PyQt5.QtCore import QTimer

    def check_ollama():
        connected = window.ollama_connector.test_connection(test_model=False)
        window.update_ollama_status(connected)

        if not connected and not window.is_reconnecting:
            window.handle_ollama_dropped()
        elif connected and window.is_reconnecting:
            window.handle_ollama_recovered()

    window.ollama_checker = QTimer()
    window.ollama_checker.timeout.connect(check_ollama)
    window.ollama_checker.start(5000)  # Cada 5 segundos
    logger.info("Ollama checker iniciado")


def start_monitoring(window):
    """Iniciar monitoreo de componentes."""
    from PyQt5.QtCore import QTimer
    import config
    import threading

    def run_technical_checks():
        if window.technical_alert_monitor:
            try:
                window.technical_alert_monitor.run_checks()
            except Exception as e:
                logger.error(f"Error en technical checks: {e}")

    # Configurar timer para checks técnicos (24 horas)
    window.technical_check_timer = QTimer()
    window.technical_check_timer.timeout.connect(run_technical_checks)
    window.technical_check_timer.start(24 * 60 * 60 * 1000)  # 24 horas

    # Ejecutar checks iniciales después de 5 minutos
    QTimer.singleShot(5 * 60 * 1000, run_technical_checks)
    logger.info("Technical alert monitoring started")

    # Monitor de disco: avisa en rojo si bajamos de 20 GB (cada 5 min)
    if config.disk_monitor_available:
        window._disk_warning_shown = False
        window.disk_timer = QTimer()
        window.disk_timer.timeout.connect(window._check_disk_space)
        window.disk_timer.start(5 * 60 * 1000)
        QTimer.singleShot(4000, window._check_disk_space)  # primera comprobación al arrancar

    logger.info("Mantenimiento autónomo desactivado (pendiente de reactivar)")

    # ── Escaneo periódico de puertos (cada 10 min) ────────────────────────
    if window.network_audit:
        window.port_scan_timer = QTimer(window)
        window.port_scan_timer.timeout.connect(window._run_port_scan)
        window.port_scan_timer.start(10 * 60 * 1000)
        logger.info("QTimer port_scan activo (10 min)")

    # ── Limpieza periódica de hilos zombie (cada 5 min) ──────────────────
    if window.thread_cleaner:
        window.thread_clean_timer = QTimer(window)
        window.thread_clean_timer.timeout.connect(window._run_thread_clean)
        window.thread_clean_timer.start(5 * 60 * 1000)
        logger.info("QTimer thread_clean activo (5 min)")

    # ── Informe diario STATUS.md (5 s tras arrancar) ─────────────────────
    QTimer.singleShot(5000, window._generate_daily_status)

    # ── Revisión semanal de herramientas + investigación IA (cada 7 días) ─
    window.weekly_review_timer = QTimer(window)
    window.weekly_review_timer.timeout.connect(window._run_weekly_review)
    window.weekly_review_timer.start(7 * 24 * 60 * 60 * 1000)
    logger.info("QTimer weekly_review activo (7 días)")

    # Auditoría de tokens del system prompt al arrancar (log informativo)
    if config.ura_identity_available and get_identity is not None:
        try:
            ident = get_identity()
            ident.audit_tokens(ident.get_system_prompt())
        except Exception as exc:
            logger.debug("audit_tokens falló: %s", exc)

    # Pre-calentamiento asíncrono del modelo: carga en RAM sin bloquear la GUI
    if config.ram_manager_available:
        # Reactivado para despertar Ollama al inicio
        threading.Thread(target=window._warmup_model_async, daemon=True).start()
        logger.info("[warmup] Activado para despertar Ollama al inicio")
