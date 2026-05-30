#!/usr/bin/env python3
"""
Windsurf Utils - Paso 3A
──────────────────────────
Utilidades para Windsurf.
"""

import logging
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


def check_windsurf_status(window):
    """Verificar estado de Windsurf."""
    try:
        import requests

        response = requests.get("http://localhost:18789/health", timeout=2)
        if response.status_code == 200:
            window.windsurf_status_label.setText("🟢 Windsurf: Conectado")
            window.windsurf_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            return True
        else:
            window.windsurf_status_label.setText("🔴 Windsurf: Error")
            window.windsurf_status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            return False
    except Exception as e:
        window.windsurf_status_label.setText("🔴 Windsurf: Desconectado")
        window.windsurf_status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        logger.warning(f"Windsurf no disponible: {e}")
        return False


def check_connections(window):
    """Verificar todas las conexiones."""
    windsurf_ok = window.check_windsurf_status()

    # Probar conexión real con Ollama
    ollama_ok = window.ollama_connector.test_connection(test_model=True)
    window.update_ollama_status(ollama_ok)

    if ollama_ok and windsurf_ok:
        QMessageBox.information(
            window, "Conexiones", "Todos los servicios están conectados y funcionando"
        )
        return True
    else:
        status_msg = f"Estado - Ollama: {'OK' if ollama_ok else 'ERROR'}, Windsurf: {'OK' if windsurf_ok else 'ERROR'}"
        QMessageBox.warning(window, "Conexiones", status_msg)
        return False


def handle_windsurf_response(window, response):
    """Manejar respuesta de Windsurf - va a Contexto."""
    window.command_handler.handle_windsurf_response(response)

    # Añadir al contexto (FLUJO CORRECTO)
    window.windsurf_context = response
    timestamp = time.strftime("%H:%M:%S")
    context_entry = f"\n[{timestamp}] Contexto de Windsurf:\n{response}"
    window.ura_context_text.setPlainText(context_entry)

    # Notificar a URA que tiene nuevo contexto
    window.notify_ura_context_update(response)

    logger.info(f"Windsurf respondió y actualizó contexto: {response[:50]}...")


def start_windsurf(window):
    """Iniciar Windsurf."""
    logger.info("Iniciando Windsurf...")
    # Aquí se implementaría la lógica para iniciar Windsurf
    window.chat_alert("Windsurf iniciado")
