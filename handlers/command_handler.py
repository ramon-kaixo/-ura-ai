#!/usr/bin/env python3
"""
Command Handler - Paso 2A
──────────────────────────
Handler central de comandos para URA.
"""

import logging
import time
import threading
import contextlib
from typing import TYPE_CHECKING, Callable, Any

from PyQt5.QtWidgets import QMessageBox

from core.ura_config import config
from handlers.handler_utils import get_health_report_from_file, format_timestamp

if TYPE_CHECKING:
    # from main_final import URAMainWindowFinal  # archived
    pass

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handler central de comandos para URA."""

    def __init__(self, parent: Any):
        """
        Inicializar CommandHandler.

        Args:
            parent: Instancia de URAMainWindowFinal
        """
        self.parent = parent
        self.commands: dict[str, Callable] = {}
        self._register_commands()

    def _register_commands(self):
        """Registrar comandos disponibles."""
        self.commands = {
            "smart_recovery": self.handle_smart_recovery,
            "clean_safe": self.handle_clean_safe,
            "health_report": self.handle_health_report_command,
        }

    def process_command(self, command_text: str) -> bool:
        """
        Procesar un comando de texto.

        Args:
            command_text: Texto del comando

        Returns:
            True si se procesó el comando, False si no
        """
        # Detectar comandos por texto
        if (
            "recuperación inteligente" in command_text.lower()
            or "smart recovery" in command_text.lower()
        ):
            self.handle_smart_recovery()
            return True
        elif "limpieza segura" in command_text.lower() or "clean safe" in command_text.lower():
            self.handle_clean_safe()
            return True
        elif "informe de salud" in command_text.lower() or "health report" in command_text.lower():
            self.handle_health_report_command()
            return True
        return False

    def handle_smart_recovery(self):
        """Disparar Recuperación Inteligente con protocolo de validación dual."""
        if not config.smart_recovery_available:
            QMessageBox.warning(
                self.parent, "Recuperación Inteligente", "Módulo smart_recovery no disponible."
            )
            return
        reply = QMessageBox.question(
            self.parent,
            "Recuperación Inteligente",
            "Esto va a:\n"
            "  1. Guardar los archivos nuevos de hoy (facturas, logs, outputs).\n"
            "  2. Restaurar el núcleo desde el backup nocturno más cercano a las 03:00 AM.\n"
            "  3. Re-integrar los archivos preservados.\n"
            "  4. Reinstalar automáticamente cualquier librería Python faltante.\n\n"
            "Antes de ejecutar se pedirá validación por Telegram + Face ID/Touch ID.\n\n"
            "¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # --- Protocolo de validación dual (Telegram + Apple) ---
        if config.security_policy_available and hasattr(self.parent, "require_authorization"):
            self.parent.smart_recovery_button.setEnabled(False)
            self.parent.smart_recovery_button.setText("🔐 Validando…")
            from PyQt5.QtWidgets import QApplication

            QApplication.processEvents()
            authorized = self.parent.require_authorization(
                action_name="Recuperación Inteligente",
                details="Restaurar núcleo desde backup 03:00 AM",
                reason="URA: confirma la Recuperación Inteligente",
                telegram_bridge=(
                    self.parent.telegram_bridge if hasattr(self.parent, "telegram_bridge") else None
                ),
            )
            if not authorized:
                self.parent.smart_recovery_button.setEnabled(True)
                self.parent.smart_recovery_button.setText("🛟 Recuperación Inteligente")
                QMessageBox.warning(
                    self.parent,
                    "Recuperación Inteligente",
                    "Acción abortada: validación de seguridad denegada.",
                )
                return
        else:
            logger.warning("security_policy no disponible; se ejecuta sin validación")

        self.parent.smart_recovery_button.setEnabled(False)
        self.parent.smart_recovery_button.setText("🛟 Recuperando…")
        self.parent.show_progress()

        # Iniciar hilo de recuperación
        from services.threads import _SmartRecoveryThread

        self.parent._recovery_thread = _SmartRecoveryThread(self.parent)
        self.parent._recovery_thread.finished.connect(self.parent._on_recovery_finished)
        self.parent._recovery_thread.start()

    def handle_clean_safe(self):
        """Limpieza Segura: lanza la generación de lista en un QThread."""
        if (
            getattr(self.parent, "_clean_thread", None) is not None
            and self.parent._clean_thread.isRunning()
        ):
            self.parent.chat_alert("Ya hay una limpieza en curso. Espera a que termine.")
            return

        self.parent.clean_safe_button.setEnabled(False)
        self.parent.clean_safe_button.setText("🧹 Generando lista…")

        from services.threads import _CleanSafeListThread

        self.parent._clean_thread = _CleanSafeListThread(self.parent)
        self.parent._clean_thread.list_ready.connect(self.parent._on_clean_list_ready)
        self.parent._clean_thread.failed.connect(self.parent._on_clean_list_failed)
        self.parent._clean_thread.start()

    def handle_health_report_command(self):
        """Manejar comando de voz 'informe de salud'"""
        health_report = get_health_report_from_file()

        # Mostrar en UI
        timestamp = format_timestamp()
        self.parent.ura_history_text.append(f"[{timestamp}] URA: {health_report}")

        # Establecer como respuesta pendiente
        self.parent.pending_ura_response = health_report
        self.parent.ura_pending_text.setPlainText(health_report)

        # Auto-scroll
        cursor = self.parent.ura_history_text.textCursor()
        cursor.movePosition(cursor.End)
        self.parent.ura_history_text.setTextCursor(cursor)

        # Sintetizar por voz si está disponible
        if hasattr(self.parent, "speak_response"):
            self.parent.speak_response()

        logger.info(f"Informe de salud generado: {health_report}")

    def handle_streaming_chunk(self, chunk):
        """Manejar cada chunk/token del streaming - actualiza UI en tiempo real"""
        self.parent.streaming_response += chunk

        # Actualizar panel pendiente con respuesta parcial
        self.parent.ura_pending_text.setPlainText(self.parent.streaming_response)

        # Auto-scroll
        cursor = self.parent.ura_pending_text.textCursor()
        cursor.movePosition(cursor.End)
        self.parent.ura_pending_text.setTextCursor(cursor)

        logger.debug(f"Chunk recibido: {chunk[:20]}...")

    def handle_ollama_disconnection(self):
        """Manejar desconexión de Ollama con mensaje elegante"""
        if self.parent.is_reconnecting:
            return  # Ya estamos reconectando

        self.parent.is_reconnecting = True

        # Mostrar mensaje elegante en UI
        timestamp = format_timestamp()
        self.parent.ura_history_text.append(
            f"[{timestamp}] ⚠️ URA ha perdido conexión, reconectando..."
        )
        self.parent.ura_pending_text.setPlainText("URA ha perdido conexión, reconectando...")

        # Intentar reconectar en background
        def reconnect():
            for _attempt in range(5):
                time.sleep(2)
                if self.parent.ollama_connector.test_connection(test_model=False):
                    timestamp = format_timestamp()
                    self.parent.ura_history_text.append(
                        f"[{timestamp}] ✅ URA reconectado exitosamente"
                    )
                    self.parent.is_reconnecting = False
                    return
            # Si no se reconecta después de 5 intentos
            timestamp = format_timestamp()
            self.parent.ura_history_text.append(f"[{timestamp}] ❌ No se pudo reconectar a Ollama")
            self.parent.is_reconnecting = False

        reconnect_thread = threading.Thread(target=reconnect, daemon=True)
        reconnect_thread.start()

    def handle_streaming_complete(self, response):
        """Manejar respuesta completa de streaming"""
        format_timestamp()

        # Guardrail anti-duda: si el modelo ha dudado, sustituimos la respuesta
        if config.ura_guardrail_available:
            from core.ura_guardrail import guardrail_review

            intervenido, response = guardrail_review(
                response, user_message=getattr(self.parent, "_last_user_message", "")
            )
            if intervenido:
                logger.info("[guardrail] Respuesta con duda interceptada y corregida.")

        # Guardrails de Salida para integridad de datos
        if (
            config.output_guardrails_available
            and hasattr(self.parent, "output_guardrails_manager")
            and self.parent.output_guardrails_manager
        ):
            try:
                guardrail = self.parent.output_guardrails_manager.get_guardrail()
                if guardrail:
                    result = guardrail.validate(response, {"context": "ura_response"})
                    if not result.passed:
                        logger.warning(f"Output guardrail violations: {len(result.violations)}")
                        if result.sanitized:
                            response = result.final_output
                            logger.info("Response sanitized by guardrails")
            except Exception as e:
                logger.error(f"Error applying output guardrails: {e}")

        # Cache - Guardar respuesta en cache
        cache_key = f"ura_response:{getattr(self.parent, '_last_user_message', '')}"
        if (
            config.cache_available
            and hasattr(self.parent, "cache")
            and self.parent.cache
            and cache_key not in ["ura_response:", "ura_response:None"]
        ):
            self.parent.cache.set(cache_key, response, ttl_seconds=300)  # 5 minutos

        # Añadir al historial (burbuja azul pálido con texto negro)
        self.parent.chat_ura(response)

        # Memoria conversacional: guardar turno de URA
        if (
            config.ura_memory_available
            and hasattr(self.parent, "get_memory")
            and self.parent.get_memory
        ):
            with contextlib.suppress(Exception):
                self.parent.get_memory().add_ura(response)

        # Añadir respuesta al Contexto Dinámico
        if (
            config.dynamic_context_available
            and hasattr(self.parent, "dynamic_context")
            and self.parent.dynamic_context
        ):
            try:
                self.parent.dynamic_context.add_message(response, role="assistant", priority=0.8)
            except Exception as e:
                logger.error(f"Error adding response to dynamic context: {e}")

    def handle_ura_response(self, response):
        """Manejar respuesta de URA - va a Respuesta Pendiente"""
        format_timestamp()

        # Añadir al historial (burbuja azul pálido con texto negro)
        self.parent.chat_ura(response)

        # Establecer como respuesta pendiente (FLUJO CORRECTO)
        self.parent.pending_ura_response = response
        self.parent.ura_pending_text.setPlainText(response)

        # Auto-scroll
        cursor = self.parent.ura_history_text.textCursor()
        cursor.movePosition(cursor.End)
        self.parent.ura_history_text.setTextCursor(cursor)

        logger.info(f"URA respondió y está pendiente de decisión: {response[:50]}...")

    def handle_processing_error(self, error):
        """Manejar error de procesamiento"""
        format_timestamp()
        self.parent.chat_alert(f"ERROR: {error}")

        # Mostrar error detallado
        QMessageBox.critical(
            self.parent, "Error de Procesamiento", f"No se pudo procesar el mensaje:\n\n{error}"
        )

    def handle_windsurf_response(self, response):
        """Manejar respuesta de Windsurf"""
        timestamp = format_timestamp()
        self.parent.windsurf_response_text.append(f"[{timestamp}] Windsurf: {response}")
