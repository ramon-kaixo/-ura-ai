#!/usr/bin/env python3
"""
Messaging Utils - Paso 3A
─────────────────────────
Utilidades para mensajería y Windsurf.
"""

import logging
import time

logger = logging.getLogger(__name__)


def send_message(window, mensaje=None):
    """Enviar mensaje a URA."""
    if mensaje is None:
        mensaje = window.user_input.text().strip()

    if not mensaje:
        return

    window.current_user_message = mensaje
    window.chat_user(mensaje)
    window.user_input.clear()

    # Procesar mensaje con URA
    window._process_user_message(mensaje)


def send_message(window, mensaje=None):
    """Enviar mensaje del usuario a Ura (delegado a MessageDispatcher)."""
    if not hasattr(window, "_dispatcher"):
        from core.message_dispatcher import MessageDispatcher

        window._dispatcher = MessageDispatcher(window)

    # Integrar CentralRouter - Fase Final (versión síncrona simplificada)
    try:
        from core.central_router import CentralRouter
        import asyncio

        # Crear router y procesar
        router = CentralRouter()

        # Ejecutar async de forma síncrona
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(router.process_request(mensaje))
        finally:
            loop.close()

        # Mostrar intención detectada en UI
        window.chat_info(
            f"[Router] Intención: {result['intent']} | Agente: {result['agent']} | Confianza: {result['confidence']:.2f}"
        )

        # Si el router ya dio respuesta, usarla
        if result["response"] and result["intent"] not in ["chat", "sistema"]:
            window.chat_ura(result["response"])
            return

        # Si no, delegar al dispatcher original
        window._dispatcher.dispatch(mensaje)

    except Exception as e:
        logger.warning(f"Router no disponible, usando dispatcher: {e}")
        window._dispatcher.dispatch(mensaje)


def send_to_windsurf(window, message):
    """Enviar mensaje directo a Windsurf."""
    timestamp = time.strftime("%H:%M:%S")

    # Añadir al panel de Windsurf
    window.windsurf_response_text.append(f"[{timestamp}] Enviado desde URA:\n{message}")

    # Simular procesamiento en Windsurf
    from services.threads import WindsurfThread

    window.windsurf_simulator = WindsurfThread(message)
    window.windsurf_simulator.response_ready.connect(window.handle_windsurf_response)
    window.windsurf_simulator.finished.connect(window.handle_windsurf_response)
    window.active_windsurf_threads.append(window.windsurf_simulator)
    window.windsurf_simulator.start()

    # Limpiar campo pendiente
    clear_pending_response(window)

    logger.info(f"Enviado a Windsurf: {message[:50]}...")


def clear_pending_response(window):
    """Limpiar respuesta pendiente."""
    window.pending_ura_response = ""
    window.ura_pending_text.clear()


def send_pending_to_windsurf(window):
    """Enviar respuesta pendiente a Windsurf - FLUJO CORRECTO."""
    if not window.pending_ura_response:
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.warning(
            window, "Advertencia", "No hay respuesta pendiente para enviar a Windsurf"
        )
        return

    window._send_to_windsurf(window.pending_ura_response)


def notify_ura_context_update(window, context):
    """Notificar a Windsurf que el contexto de URA ha cambiado."""
    if hasattr(window, "ura_context_text"):
        window.ura_context_text.setPlainText(context)
    logger.info(f"Contexto URA actualizado: {len(context)} caracteres")
