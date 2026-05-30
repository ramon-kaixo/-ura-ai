#!/usr/bin/env python3
"""
Verificación Dual de URA - Nivel 24

Sistema de verificación de seguridad con dos factores:
- Verificación biométrica de macOS (Touch ID / contraseña)
- Notificaciones push vía Pushover
- Registro en ~/.ura/security.log
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SECURITY_LOG_PATH = Path.home() / ".ura" / "security.log"
SECURITY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class DualVerification:
    """Sistema de verificación dual de seguridad."""

    def __init__(self, pushover_user_key: str = None, pushover_api_token: str = None):
        self.pushover_user_key = pushover_user_key
        self.pushover_api_token = pushover_api_token
        self._load_config()

    def _load_config(self):
        """Cargar configuración de Pushover desde archivo."""
        config_path = Path.home() / ".ura" / "pushover_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    self.pushover_user_key = config.get("user_key")
                    self.pushover_api_token = config.get("api_token")
            except Exception as e:
                logger.error(f"Error cargando configuración Pushover: {e}")

    def _log_security_event(self, event_type: str, reason: str, success: bool):
        """Registrar evento de seguridad en log."""
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"

        log_entry = f"[{timestamp}] [{status}] {event_type}: {reason}\n"

        try:
            with open(SECURITY_LOG_PATH, "a") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Error escribiendo en security log: {e}")

        logger.info(f"Security event logged: {event_type} - {status}")

    def verify_mac_biometry(self, reason: str) -> bool:
        """
        Ejecuta verificación biométrica de macOS.

        Args:
            reason: Razón de la verificación (se mostrará en el prompt)

        Returns:
            True si autorizado, False si rechazado
        """
        try:
            script = f'do shell script "echo autorizado" with prompt "URA: {reason}" with administrator privileges'

            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=60
            )

            authorized = result.returncode == 0 and "autorizado" in result.stdout

            self._log_security_event("BIOMETRY_VERIFICATION", reason, authorized)

            if authorized:
                logger.info(f"Verificación biométrica exitosa: {reason}")
            else:
                logger.warning(f"Verificación biométrica fallida: {reason}")

            return authorized

        except subprocess.TimeoutExpired:
            logger.error("Timeout en verificación biométrica")
            self._log_security_event("BIOMETRY_VERIFICATION", reason, False)
            return False
        except Exception as e:
            logger.error(f"Error en verificación biométrica: {e}")
            self._log_security_event("BIOMETRY_VERIFICATION", reason, False)
            return False

    def send_push_notification(self, title: str, message: str) -> bool:
        """
        Envía notificación push vía Pushover.

        Args:
            title: Título de la notificación
            message: Mensaje de la notificación

        Returns:
            True si enviado exitosamente, False si falló
        """
        if not self.pushover_user_key or not self.pushover_api_token:
            logger.warning("Pushover no configurado, saltando notificación")
            self._log_security_event("PUSH_NOTIFICATION", f"{title}: {message}", False)
            return False

        try:
            from pushover_complete import PushoverAPI

            push = PushoverAPI(self.pushover_api_token)
            push.user_token = self.pushover_user_key
            push.title = title
            push.message = message
            push.send()

            self._log_security_event("PUSH_NOTIFICATION", f"{title}: {message}", True)
            logger.info(f"Notificación push enviada: {title}")
            return True

        except ImportError:
            logger.warning("pushover-complete no instalado, ejecuta: pip install pushover-complete")
            self._log_security_event("PUSH_NOTIFICATION", f"{title}: {message}", False)
            return False
        except Exception as e:
            logger.error(f"Error enviando notificación push: {e}")
            self._log_security_event("PUSH_NOTIFICATION", f"{title}: {message}", False)
            return False

    def request_authorization(self, action: str) -> bool:
        """
        Solicita autorización usando verificación biométrica y notificación push.

        Args:
            action: Descripción de la acción que requiere autorización

        Returns:
            True si autorizado, False si rechazado
        """
        # 1. Enviar notificación push
        self.send_push_notification(
            title="URA: Autorización Requerida", message=f"Se requiere autorización para: {action}"
        )

        # 2. Solicitar verificación biométrica
        authorized = self.verify_mac_biometry(action)

        return authorized

    def configure_pushover(self, user_key: str, api_token: str):
        """
        Configura las credenciales de Pushover.

        Args:
            user_key: User key de Pushover
            api_token: API token de Pushover
        """
        self.pushover_user_key = user_key
        self.pushover_api_token = api_token

        # Guardar configuración
        config_path = Path.home() / ".ura" / "pushover_config.json"
        try:
            with open(config_path, "w") as f:
                json.dump({"user_key": user_key, "api_token": api_token}, f, indent=2)
            logger.info("Configuración de Pushover guardada")
        except Exception as e:
            logger.error(f"Error guardando configuración Pushover: {e}")

    def get_security_log(self, limit: int = 50) -> list[str]:
        """
        Obtiene los últimos eventos del log de seguridad.

        Args:
            limit: Número máximo de eventos a retornar

        Returns:
            Lista de entradas del log
        """
        if not SECURITY_LOG_PATH.exists():
            return []

        try:
            with open(SECURITY_LOG_PATH) as f:
                lines = f.readlines()

            return lines[-limit:]
        except Exception as e:
            logger.error(f"Error leyendo security log: {e}")
            return []


# Singleton
_dual_verification: DualVerification | None = None


def get_dual_verification(
    pushover_user_key: str = None, pushover_api_token: str = None
) -> DualVerification:
    """Obtener el singleton de verificación dual."""
    global _dual_verification
    if _dual_verification is None:
        _dual_verification = DualVerification(pushover_user_key, pushover_api_token)
    return _dual_verification


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dv = get_dual_verification()

    print("Sistema de verificación dual creado")

    # Prueba de verificación biométrica
    print("\nProbando verificación biométrica...")
    if dv.verify_mac_biometry("Prueba de verificación"):
        print("✓ Verificación biométrica exitosa")
    else:
        print("✗ Verificación biométrica fallida")

    # Prueba de notificación push (requiere configuración)
    print("\nProbando notificación push...")
    if dv.send_push_notification("URA Test", "Prueba de notificación"):
        print("✓ Notificación push enviada")
    else:
        print("✗ Notificación push fallida (requiere configuración)")
