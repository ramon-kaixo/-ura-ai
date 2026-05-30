#!/usr/bin/env python3
"""
URA Display Manager - Ventanas Emergentes Nativas de macOS
============================================================
Muestra diálogos nativos usando osascript (AppleScript) para solicitar
confirmación del usuario antes de acciones sensibles.

Flujo:
1. Muestra ventana emergente con coste y nombre del servicio
2. Si el usuario pulsa 'Aceptar', llama a autenticación de Apple
3. Si el usuario pulsa 'Cancelar', aborta la acción
"""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


class DisplayManager:
    """
    Gestor de ventanas emergentes nativas de macOS
    """

    def __init__(self):
        """Inicializa el gestor de ventanas"""
        if sys.platform != "darwin":
            logger.warning("DisplayManager solo disponible en macOS")
            self.available = False
        else:
            self.available = True
            logger.info("DisplayManager inicializado para macOS")

    def show_confirmation_dialog(
        self, service_name: str, cost_eur: float, additional_info: str = ""
    ) -> tuple[bool, str | None]:
        """
        Muestra un diálogo de confirmación nativo en macOS

        Args:
            service_name: Nombre del servicio/app
            cost_eur: Coste en euros
            additional_info: Información adicional opcional

        Returns:
            (user_accepted, error_message) - True si el usuario aceptó
        """
        if not self.available:
            logger.error("DisplayManager no disponible en este sistema")
            return False, "DisplayManager no disponible"

        # Construir mensaje del diálogo
        title = "URA - Confirmación de Compra"
        message = "¿Deseas autorizar la siguiente compra?\n\n"
        message += f"📦 Servicio: {service_name}\n"
        message += f"💰 Coste: €{cost_eur:.2f}\n"

        if additional_info:
            message += f"\nℹ️ {additional_info}"

        # Script AppleScript para mostrar diálogo
        applescript = f"""
        tell application "System Events"
            set dialogResult to display dialog "{message}" ¬
                buttons {{"Cancelar", "Aceptar"}} ¬
                default button "Aceptar" ¬
                cancel button "Cancelar" ¬
                with title "{title}" ¬
                with icon caution
            set buttonClicked to button returned of dialogResult
            return buttonClicked
        end tell
        """

        try:
            # Ejecutar AppleScript
            result = subprocess.run(
                ["osascript", "-e", applescript], capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                button_clicked = result.stdout.strip()
                if button_clicked == "Aceptar":
                    logger.info(f"Usuario aceptó compra: {service_name} por €{cost_eur:.2f}")
                    return True, None
                else:
                    logger.info(f"Usuario canceló compra: {service_name}")
                    return False, "Usuario canceló"
            else:
                error_msg = result.stderr.strip() or "Error desconocido en osascript"
                logger.error(f"Error en diálogo: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            logger.error("Timeout en diálogo de confirmación")
            return False, "Timeout en diálogo"
        except Exception as e:
            logger.error(f"Error mostrando diálogo: {str(e)}")
            return False, str(e)

    def show_approval_dialog_with_auth(
        self, service_name: str, cost_eur: float, additional_info: str = "", auth_callback=None
    ) -> tuple[bool, str | None]:
        """
        Muestra diálogo y solicita autenticación de Apple si el usuario acepta

        Args:
            service_name: Nombre del servicio/app
            cost_eur: Coste en euros
            additional_info: Información adicional opcional
            auth_callback: Función de callback para autenticación (apple_biometric_auth)

        Returns:
            (approved, error_message) - True si autorizado
        """
        # Paso 1: Mostrar diálogo de confirmación
        user_accepted, error = self.show_confirmation_dialog(
            service_name, cost_eur, additional_info
        )

        if not user_accepted:
            return False, error or "Usuario canceló"

        # Paso 2: Si el usuario aceptó, solicitar autenticación de Apple
        if auth_callback:
            try:
                auth_result = auth_callback(
                    reason=f"Autorizar compra: {service_name} por €{cost_eur:.2f}"
                )
                if auth_result:
                    logger.info("Autenticación de Apple exitosa")
                    return True, None
                else:
                    logger.warning("Autenticación de Apple falló")
                    return False, "Autenticación falló"
            except Exception as e:
                logger.error(f"Error en autenticación: {str(e)}")
                return False, str(e)

        # Si no hay callback de autenticación, aprobar directamente
        logger.warning("Sin callback de autenticación, aprobando sin verificación")
        return True, None


# Singleton
_display_manager = None


def get_display_manager() -> DisplayManager:
    """
    Obtiene la instancia singleton del DisplayManager

    Returns:
        Instancia de DisplayManager
    """
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager


# Función de conveniencia para uso directo
def request_approval_with_dialog(
    service_name: str, cost_eur: float, additional_info: str = "", auth_callback=None
) -> bool:
    """
    Solicita aprobación del usuario mediante diálogo nativo y autenticación

    Args:
        service_name: Nombre del servicio/app
        cost_eur: Coste en euros
        additional_info: Información adicional opcional
        auth_callback: Función de callback para autenticación

    Returns:
        True si el usuario autorizó y se autenticó correctamente
    """
    manager = get_display_manager()
    approved, error = manager.show_approval_dialog_with_auth(
        service_name, cost_eur, additional_info, auth_callback
    )

    if error:
        logger.error(f"Error en solicitud de aprobación: {error}")

    return approved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Prueba del diálogo
    manager = DisplayManager()
    if manager.available:
        # Simular autenticación
        def mock_auth(reason):
            print(f"Mock auth: {reason}")
            return True

        result = manager.show_approval_dialog_with_auth(
            service_name="App de Prueba",
            cost_eur=2.99,
            additional_info="Esta es una prueba del sistema",
            auth_callback=mock_auth,
        )

        print(f"Resultado: {'APROBADO' if result[0] else 'DENEGADO'}")
        if result[1]:
            print(f"Error: {result[1]}")
