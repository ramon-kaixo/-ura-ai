#!/usr/bin/env python3
"""
URA - Telegram Security Bridge
Sistema de Autorización Humana en Tiempo Real vía Telegram
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class TelegramSecurityBridge:
    """Puente de seguridad con Telegram para autorización remota"""

    def __init__(self, config_path: Path | None = None):
        """
        Inicializar puente de Telegram

        Args:
            config_path: Ruta al archivo de configuración (telegram_config.json)
        """
        self.config_path = config_path or Path(__file__).parent.parent / "telegram_config.json"
        self.api_key = None
        self.chat_id = None
        self.enabled = False
        self.pending_authorizations = {}  # {message_id: callback_function}
        self.authorized_user_ids = []  # Lista de user_ids autorizados

        # Cargar configuración
        self.load_config()

        # Iniciar polling de callbacks en background
        self.polling_thread = None
        self.polling_active = False

        if self.enabled:
            self.start_callback_polling()

    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    config = json.load(f)
                    self.api_key = config.get("api_key")
                    self.chat_id = config.get("chat_id")
                    self.authorized_user_ids = config.get("authorized_user_ids", [])
                    self.enabled = bool(self.api_key and self.chat_id)
                    logger.info(f"Configuración de Telegram cargada: {self.enabled}")
                    logger.info(f"Usuarios autorizados: {len(self.authorized_user_ids)}")
            else:
                logger.warning(f"Configuración de Telegram no encontrada: {self.config_path}")
                self.create_sample_config()
        except Exception as e:
            logger.error(f"Error cargando configuración de Telegram: {e}")

    def create_sample_config(self):
        """Crear archivo de configuración de ejemplo"""
        sample_config = {
            "api_key": "TU_BOT_TOKEN_DE_TELEGRAM",
            "chat_id": "TU_CHAT_ID",
            "authorized_user_ids": [],
            "enabled": False,
        }
        try:
            with open(self.config_path, "w") as f:
                json.dump(sample_config, f, indent=4)
            logger.info(f"Archivo de configuración de ejemplo creado: {self.config_path}")
        except Exception as e:
            logger.error(f"Error creando configuración de ejemplo: {e}")

    def is_user_authorized(self, user_id: int) -> bool:
        """
        Verificar si un user_id está autorizado

        Args:
            user_id: ID de usuario de Telegram

        Returns:
            bool: True si está autorizado, False si no
        """
        # Si no hay lista de autorizados, RECHAZAR (modo seguro por defecto)
        if not self.authorized_user_ids:
            logger.error("No hay lista de usuarios autorizados - rechazando comando por seguridad")
            return False

        # Normalizar ambos lados a int para comparar (acepta str o int en el JSON)
        try:
            user_id_int = int(user_id)
            authorized_ints = {int(x) for x in self.authorized_user_ids}
            is_authorized = user_id_int in authorized_ints
        except (TypeError, ValueError) as exc:
            logger.error(f"User ID inválido ({user_id}): {exc}")
            return False

        if not is_authorized:
            logger.error(f"User ID {user_id} NO autorizado - Comando rechazado")

        return is_authorized

    def send_message(self, message: str, reply_markup: dict | None = None) -> int | None:
        """
        Enviar mensaje a Telegram

        Args:
            message: Texto del mensaje
            reply_markup: Markup para botones inline (opcional)

        Returns:
            message_id si exitoso, None si falla
        """
        if not self.enabled:
            logger.warning("Telegram no está configurado, mensaje no enviado")
            return None

        try:
            url = f"https://api.telegram.org/bot{self.api_key}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}

            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            response = requests.post(url, data=data, timeout=10)
            result = response.json()

            if result.get("ok"):
                message_id = result["result"]["message_id"]
                logger.info(f"Mensaje enviado a Telegram: {message_id}")
                return message_id
            else:
                logger.error(f"Error enviando mensaje: {result}")
                return None
        except Exception as e:
            logger.error(f"Error enviando mensaje a Telegram: {e}")
            return None

    def send_security_alert(
        self, command: str, reason: str, authorization_callback: Callable
    ) -> int | None:
        """
        Enviar alerta de seguridad con botones de autorización

        Args:
            command: Comando bloqueado
            reason: Razón del bloqueo
            authorization_callback: Función a llamar si se autoriza

        Returns:
            message_id si exitoso, None si falla
        """
        message = f"""⚠️ *ALERTA DE SEGURIDAD URA*

El sistema ha bloqueado un comando potencialmente peligroso.

*Comando:* `{command}`
*Razón:* {reason}

¿Deseas autorizarlo manualmente?"""

        # Botones inline
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Autorizar", "callback_data": f"AUTHORIZE:{command}"},
                    {"text": "❌ Denegar", "callback_data": f"DENY:{command}"},
                ]
            ]
        }

        message_id = self.send_message(message, reply_markup)

        if message_id:
            # Guardar callback para cuando el usuario responda
            self.pending_authorizations[message_id] = authorization_callback
            logger.info(f"Alerta de seguridad enviada, esperando autorización: {message_id}")

        return message_id

    def send_health_report(self, report_content: str) -> int | None:
        """
        Enviar informe semanal de salud

        Args:
            report_content: Contenido del informe

        Returns:
            message_id si exitoso, None si falla
        """
        message = f"""📊 *INFORME SEMANAL DE SALUD URA*
📅 {datetime.now().strftime("%Y-%m-%d")}

{report_content}

---
*Generado automáticamente por URA*"""

        return self.send_message(message)

    def start_callback_polling(self):
        """Iniciar polling de callbacks en background"""
        if self.polling_active:
            return

        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._poll_callbacks, daemon=True)
        self.polling_thread.start()
        logger.info("Polling de callbacks iniciado")

    def stop_callback_polling(self):
        """Detener polling de callbacks"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        logger.info("Polling de callbacks detenido")

    def _poll_callbacks(self):
        """Polling de callbacks de Telegram en background"""
        offset = 0

        while self.polling_active:
            try:
                if not self.enabled:
                    time.sleep(5)
                    continue

                url = f"https://api.telegram.org/bot{self.api_key}/getUpdates"
                params = {"offset": offset, "timeout": 10}

                response = requests.get(url, params=params, timeout=15)
                result = response.json()

                if result.get("ok") and result.get("result"):
                    for update in result["result"]:
                        self._handle_update(update)
                        offset = update["update_id"] + 1

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error en polling de callbacks: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        """Manejar update de Telegram"""
        try:
            # Verificar autorización de usuario
            user_id = None
            if "callback_query" in update:
                user_id = update["callback_query"].get("from", {}).get("id")
            elif "message" in update:
                user_id = update["message"].get("from", {}).get("id")

            # Si hay user_id, verificar autorización
            if user_id and not self.is_user_authorized(user_id):
                logger.error(f"Update rechazado: User ID {user_id} no autorizado")
                return

            # Callback query (botón presionado)
            if "callback_query" in update:
                callback_query = update["callback_query"]
                callback_data = callback_query.get("data", "")
                query_id = callback_query["id"]

                # Responder al callback query
                self._answer_callback_query(query_id)

                # Procesar acción
                if callback_data.startswith("AUTHORIZE:"):
                    command = callback_data.split(":", 1)[1]
                    self._handle_authorization(command, callback_query["message"]["message_id"])
                elif callback_data.startswith("DENY:"):
                    command = callback_data.split(":", 1)[1]
                    self._handle_denial(command, callback_query["message"]["message_id"])

            # Mensaje de texto (para comandos manuales)
            elif "message" in update and "text" in update["message"]:
                self._handle_text_message(update["message"])

        except Exception as e:
            logger.error(f"Error manejando update: {e}")

    def _answer_callback_query(self, query_id: str, text: str = "Procesando..."):
        """Responder a callback query"""
        try:
            url = f"https://api.telegram.org/bot{self.api_key}/answerCallbackQuery"
            data = {"callback_query_id": query_id, "text": text}
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            logger.error(f"Error respondiendo callback query: {e}")

    def _handle_authorization(self, command: str, message_id: int):
        """Manejar autorización de comando"""
        logger.info(f"Comando autorizado por usuario: {command}")

        # Ejecutar callback pendiente si existe
        if message_id in self.pending_authorizations:
            callback = self.pending_authorizations[message_id]
            try:
                callback(authorized=True)
            except Exception as e:
                logger.error(f"Error ejecutando callback de autorización: {e}")
            del self.pending_authorizations[message_id]

        # Enviar confirmación
        self.send_message(
            f"✅ *Comando Autorizado*\n\nEl comando `{command}` ha sido autorizado y ejecutado."
        )

    def _handle_denial(self, command: str, message_id: int):
        """Manejar denegación de comando"""
        logger.warning(f"Comando denegado por usuario: {command}")

        # Ejecutar callback pendiente si existe
        if message_id in self.pending_authorizations:
            callback = self.pending_authorizations[message_id]
            try:
                callback(authorized=False)
            except Exception as e:
                logger.error(f"Error ejecutando callback de denegación: {e}")
            del self.pending_authorizations[message_id]

        # Enviar confirmación
        self.send_message(
            f"❌ *Comando Denegado*\n\nEl comando `{command}` ha sido denegado y bloqueado."
        )

    def _handle_text_message(self, message: dict):
        """Manejar mensaje de texto (para comandos manuales)"""
        text = message.get("text", "").strip()

        # Comandos manuales
        if text.startswith("/"):
            logger.info(f"Comando manual recibido: {text}")
            # Aquí se pueden implementar comandos como /health, /status, etc.

    def send_technical_response(
        self, instruction_sheet: dict | None = None, execution_result: dict | None = None
    ) -> int | None:
        """
        Enviar respuesta técnica con formato directo

        Args:
            instruction_sheet: Ficha de instrucción técnica del Director
            execution_result: Resultado de la ejecución

        Returns:
            message_id si exitoso, None si falla
        """
        if not self.enabled:
            logger.warning("Telegram no está configurado, respuesta técnica no enviada")
            return None

        try:
            # Formato de salida técnica
            if instruction_sheet and execution_result:
                operation_type = instruction_sheet.get("operation_type", "UNKNOWN")
                success = execution_result.get("success", False)
                data = execution_result.get("data", "")

                message = f"""[OP: {operation_type}]
[RESULT: {"SUCCESS" if success else "FAILURE"}]
[DATA: {data[:200]}]
[TIMESTAMP: {datetime.now().strftime("%H:%M:%S")}]"""
            elif instruction_sheet:
                # Solo ficha (operación aprobada pero no ejecutada)
                operation_type = instruction_sheet.get("operation_type", "UNKNOWN")
                message = f"""[STATUS: APPROVED]
[OP: {operation_type}]
[CAPABILITY: {instruction_sheet.get("capability_required", "UNKNOWN")}]
[TIMESTAMP: {datetime.now().strftime("%H:%M:%S")}]"""
            else:
                # Estado del sistema
                message = f"""[STATUS: READY]
[CAPABILITIES: LOADED]
[MODE: TECHNICAL]
[TIMESTAMP: {datetime.now().strftime("%H:%M:%S")}]"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error enviando respuesta técnica: {e}")
            return None

    def test_connection(self) -> bool:
        """Probar conexión con Telegram"""
        if not self.enabled:
            logger.warning("Telegram no está configurado")
            return False

        try:
            message = f"🧪 *Test de Conexión URA*\n\nConexión exitosa - {datetime.now().strftime('%H:%M:%S')}"
            message_id = self.send_message(message)
            return message_id is not None
        except Exception as e:
            logger.error(f"Error en test de conexión: {e}")
            return False


# Singleton global
_telegram_bridge = None


def get_telegram_bridge(config_path: Path | None = None) -> TelegramSecurityBridge:
    """Obtener instancia singleton del puente de Telegram"""
    global _telegram_bridge
    if _telegram_bridge is None:
        _telegram_bridge = TelegramSecurityBridge(config_path)
    return _telegram_bridge
