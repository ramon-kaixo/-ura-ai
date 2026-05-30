#!/usr/bin/env python3
"""
core/action_signer.py - Action Signer (firma de acciones críticas)
Autoriza acciones críticas con diferentes niveles de seguridad
"""

import logging
import sys

from core.logging_config import get_logger

logger = get_logger("action_signer", log_dir="./logs")

# Niveles de autorización
NIVEL_BAJO = "bajo"
NIVEL_MEDIO = "medio"
NIVEL_ALTO = "alto"
NIVEL_CRITICO = "critico"


def autorizar_accion(accion: str, detalle: str, nivel: str) -> bool:
    """
    Autoriza una acción según su nivel de seguridad

    Args:
        accion: Nombre de la acción
        detalle: Detalle de la acción
        nivel: Nivel de seguridad (bajo, medio, alto, critico)

    Returns:
        True si la acción fue autorizada, False en caso contrario
    """
    logger.info(f"Solicitando autorización para acción: {accion} (nivel: {nivel})")

    if nivel == NIVEL_BAJO:
        return _autorizar_bajo(accion, detalle)
    elif nivel == NIVEL_MEDIO:
        return _autorizar_medio(accion, detalle)
    elif nivel == NIVEL_ALTO:
        return _autorizar_alto(accion, detalle)
    elif nivel == NIVEL_CRITICO:
        return _autorizar_critico(accion, detalle)
    else:
        logger.error(f"Nivel de autorización inválido: {nivel}")
        return False


def _autorizar_bajo(accion: str, detalle: str) -> bool:
    """
    Nivel bajo: permitir automáticamente (solo log)
    """
    logger.info(f"[NIVEL BAJO] Acción autorizada automáticamente: {accion}")
    logger.info(f"Detalle: {detalle}")
    return True


def _autorizar_medio(accion: str, detalle: str) -> bool:
    """
    Nivel medio: notificación PyQt5 + confirmación
    """
    logger.info(f"[NIVEL MEDIO] Solicitando confirmación para: {accion}")
    logger.info(f"Detalle: {detalle}")

    try:
        # Intentar usar PyQt5 para diálogo de confirmación
        from PyQt5.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        msg = QMessageBox()
        msg.setWindowTitle("Confirmación de Acción")
        msg.setText(f"¿Autorizar la siguiente acción?\n\nAcción: {accion}\n\nDetalle: {detalle}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        result = msg.exec_()

        if result == QMessageBox.Yes:
            logger.info(f"[NIVEL MEDIO] Acción autorizada por usuario: {accion}")
            return True
        else:
            logger.warning(f"[NIVEL MEDIO] Acción rechazada por usuario: {accion}")
            return False

    except ImportError:
        logger.warning("PyQt5 no disponible, usando modo consola")
        return _autorizar_medio_consola(accion, detalle)
    except Exception as e:
        logger.error(f"Error en diálogo PyQt5: {e}")
        return _autorizar_medio_consola(accion, detalle)


def _autorizar_medio_consola(accion: str, detalle: str) -> bool:
    """
    Fallback de consola para nivel medio
    """
    print("\n=== CONFIRMACIÓN DE ACCIÓN ===")
    print(f"Acción: {accion}")
    print(f"Detalle: {detalle}")
    print("============================")

    respuesta = input("¿Autorizar esta acción? (s/n): ").strip().lower()

    if respuesta == "s" or respuesta == "si" or respuesta == "y" or respuesta == "yes":
        logger.info(f"[NIVEL MEDIO] Acción autorizada por usuario (consola): {accion}")
        return True
    else:
        logger.warning(f"[NIVEL MEDIO] Acción rechazada por usuario (consola): {accion}")
        return False


def _autorizar_alto(accion: str, detalle: str) -> bool:
    """
    Nivel alto: diálogo con justificación obligatoria (mínimo 10 caracteres)
    """
    logger.info(f"[NIVEL ALTO] Solicitando justificación para: {accion}")
    logger.info(f"Detalle: {detalle}")

    try:
        from PyQt5.QtWidgets import (
            QApplication,
            QDialog,
            QVBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
        )

        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        dialog = QDialog()
        dialog.setWindowTitle("Autorización de Acción Crítica")
        dialog.setModal(True)

        layout = QVBoxLayout()

        label = QLabel(
            f"Acción: {accion}\n\nDetalle: {detalle}\n\nJustificación obligatoria (mínimo 10 caracteres):"
        )
        layout.addWidget(label)

        input_field = QLineEdit()
        layout.addWidget(input_field)

        button_layout = QHBoxLayout()

        def on_aceptar():
            justificacion = input_field.text().strip()
            if len(justificacion) >= 10:
                logger.info(f"[NIVEL ALTO] Acción autorizada: {accion}")
                logger.info(f"Justificación: {justificacion}")
                dialog.accept()
            else:
                input_field.setStyleSheet("background-color: #ffcccc")

        def on_rechazar():
            logger.warning(f"[NIVEL ALTO] Acción rechazada: {accion}")
            dialog.reject()

        btn_aceptar = QPushButton("Autorizar")
        btn_aceptar.clicked.connect(on_aceptar)
        button_layout.addWidget(btn_aceptar)

        btn_rechazar = QPushButton("Rechazar")
        btn_rechazar.clicked.connect(on_rechazar)
        button_layout.addWidget(btn_rechazar)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        result = dialog.exec_()

        return result == QDialog.Accepted

    except ImportError:
        logger.warning("PyQt5 no disponible, usando modo consola")
        return _autorizar_alto_consola(accion, detalle)
    except Exception as e:
        logger.error(f"Error en diálogo PyQt5: {e}")
        return _autorizar_alto_consola(accion, detalle)


def _autorizar_alto_consola(accion: str, detalle: str) -> bool:
    """
    Fallback de consola para nivel alto
    """
    print("\n=== AUTORIZACIÓN DE ACCIÓN CRÍTICA ===")
    print(f"Acción: {accion}")
    print(f"Detalle: {detalle}")
    print("====================================")

    justificacion = input("Justificación obligatoria (mínimo 10 caracteres): ").strip()

    if len(justificacion) < 10:
        print("❌ Justificación demasiado corta")
        logger.warning(f"[NIVEL ALTO] Justificación demasiado corta: {accion}")
        return False

    confirmacion = input("¿Autorizar esta acción? (s/n): ").strip().lower()

    if confirmacion == "s" or confirmacion == "si" or confirmacion == "y" or confirmacion == "yes":
        logger.info(f"[NIVEL ALTO] Acción autorizada (consola): {accion}")
        logger.info(f"Justificación: {justificacion}")
        return True
    else:
        logger.warning(f"[NIVEL ALTO] Acción rechazada (consola): {accion}")
        return False


def _autorizar_critico(accion: str, detalle: str) -> bool:
    """
    Nivel crítico: bloquear + alerta Telegram + esperar autorización manual
    """
    logger.warning(f"[NIVEL CRÍTICO] Acción bloqueada pendiente de autorización manual: {accion}")
    logger.warning(f"Detalle: {detalle}")

    # Enviar alerta Telegram
    _enviar_alerta_telegram(accion, detalle)

    # Esperar autorización manual
    print("\n=== ACCIÓN CRÍTICA BLOQUEADA ===")
    print(f"Acción: {accion}")
    print(f"Detalle: {detalle}")
    print("Se ha enviado una alerta a Telegram")
    print("=================================")

    respuesta = input("Para autorizar manualmente, introduce 'AUTORIZAR': ").strip()

    if respuesta == "AUTORIZAR":
        logger.info(f"[NIVEL CRÍTICO] Acción autorizada manualmente: {accion}")
        return True
    else:
        logger.error(f"[NIVEL CRÍTICO] Acción NO autorizada: {accion}")
        return False


def _enviar_alerta_telegram(accion: str, detalle: str) -> None:
    """Envía alerta a Telegram"""
    logger.info("Enviando alerta Telegram para acción crítica")

    try:
        from core.messaging_tools import send_telegram_message

        message = f"""
🚨 ACCIÓN CRÍTICA REQUIERE AUTORIZACIÓN 🚨

Acción: {accion}
Detalle: {detalle}
Nivel: CRÍTICO

Esta acción ha sido bloqueada y requiere autorización manual.
Para autorizar, accede al sistema e introduce el código 'AUTORIZAR'.
        """

        send_telegram_message(message)
        logger.info("Alerta Telegram enviada")

    except Exception as e:
        logger.error(f"Error enviando alerta Telegram: {e}")


# Acciones que requieren autorización obligatoria
ACCIONES_CRITICAS = {
    "borrar_fichero": NIVEL_ALTO,
    "eliminar_directorio": NIVEL_ALTO,
    "modificar_configuracion_sistema": NIVEL_ALTO,
    "cambiar_credenciales_boveda": NIVEL_CRITICO,
    "activar_workflow_n8n": NIVEL_MEDIO,
    "modificar_variables_entorno": NIVEL_ALTO,
}


def obtener_nivel_requerido(accion: str) -> str:
    """
    Obtiene el nivel de autorización requerido para una acción

    Args:
        accion: Nombre de la acción

    Returns:
        Nivel de autorización requerido
    """
    return ACCIONES_CRITICAS.get(accion, NIVEL_BAJO)


def accion_requiere_autorizacion(accion: str) -> bool:
    """
    Verifica si una acción requiere autorización

    Args:
        accion: Nombre de la acción

    Returns:
        True si requiere autorización
    """
    nivel = obtener_nivel_requerido(accion)
    return nivel != NIVEL_BAJO


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Prueba nivel bajo
    resultado = autorizar_accion("test_bajo", "Acción de prueba", NIVEL_BAJO)
    print(f"Nivel bajo: {resultado}")

    # Prueba nivel alto
    # resultado = autorizar_accion("borrar_archivo", "Borrar archivo importante", NIVEL_ALTO)
    # print(f"Nivel alto: {resultado}")
