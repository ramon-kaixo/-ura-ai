#!/usr/bin/env python3
"""
Módulo: core/security/hermetic_states.py
Propósito: Estados herméticos de seguridad: bloquea pagos, credenciales e internet según modo activo.
Dependencias principales: enum, functools, threading, json
Reglas especiales: Decoradores SIEMPRE verificados antes de ejecutar funciones sensibles. Reset total al desactivar.
"""

import functools
import logging
from enum import StrEnum
from threading import Lock

logger = logging.getLogger(__name__)


class HermeticState(StrEnum):
    """Estados del sistema hermético"""

    NORMAL = "normal"  # Sistema operativo normal
    BLOCK_PAYMENTS = "block_payments"  # Bloquea pagos
    BLOCK_CREDENTIALS = "block_credentials"  # Bloquea credenciales
    BLOCK_INTERNET = "block_internet"  # Bloquea internet
    HERMETIC = "hermetic"  # Bloquea todo


# Singleton con thread-safety
class HermeticSecurityManager:
    """
    Gestor de seguridad hermética.
    Controla los tres estados globales de bloqueo independientes.
    """

    def __init__(self):
        """Inicializa el gestor con todos los estados desactivados"""
        self._lock = Lock()
        self._block_payments = False
        self._block_credentials = False
        self._block_internet = False
        self._hermetic_mode = False
        logger.info("HermeticSecurityManager inicializado")

    def set_block_payments(self, blocked: bool) -> None:
        """
        Activa/desactiva el bloqueo de pagos

        Args:
            blocked: True para bloquear pagos, False para permitir
        """
        with self._lock:
            self._block_payments = blocked
            status = "ACTIVADO" if blocked else "DESACTIVADO"
            logger.warning(f"BLOCK_PAYMENTS {status}")

    def set_block_credentials(self, blocked: bool) -> None:
        """
        Activa/desactiva el bloqueo de credenciales

        Args:
            blocked: True para bloquear credenciales, False para permitir
        """
        with self._lock:
            self._block_credentials = blocked
            status = "ACTIVADO" if blocked else "DESACTIVADO"
            logger.warning(f"BLOCK_CREDENTIALS {status}")

    def set_block_internet(self, blocked: bool) -> None:
        """
        Activa/desactiva el bloqueo de internet

        Args:
            blocked: True para bloquear internet, False para permitir
        """
        with self._lock:
            self._block_internet = blocked
            status = "ACTIVADO" if blocked else "DESACTIVADO"
            logger.warning(f"BLOCK_INTERNET {status}")

    def set_hermetic_mode(self, enabled: bool) -> None:
        """
        Activa/desactiva el modo hermético total (bloquea todo)

        Args:
            enabled: True para modo hermético, False para normal
        """
        with self._lock:
            self._hermetic_mode = enabled
            if enabled:
                # Activar todos los bloqueos
                self._block_payments = True
                self._block_credentials = True
                self._block_internet = True
                logger.critical("MODO HERMÉTICO ACTIVADO - TODAS LAS OPERACIONES BLOQUEADAS")
            else:
                self._block_payments = False
                self._block_credentials = False
                self._block_internet = False
                logger.info("MODO HERMÉTICO DESACTIVADO")

    def is_block_payments(self) -> bool:
        """Verifica si los pagos están bloqueados"""
        with self._lock:
            return self._block_payments or self._hermetic_mode

    def is_block_credentials(self) -> bool:
        """Verifica si las credenciales están bloqueadas"""
        with self._lock:
            return self._block_credentials or self._hermetic_mode

    def is_block_internet(self) -> bool:
        """Verifica si internet está bloqueado"""
        with self._lock:
            return self._block_internet or self._hermetic_mode

    def is_hermetic_mode(self) -> bool:
        """Verifica si el sistema está en modo hermético total"""
        with self._lock:
            return self._hermetic_mode

    def get_status(self) -> dict:
        """
        Obtiene el estado actual de todos los bloqueos

        Returns:
            Diccionario con el estado de cada bloqueo
        """
        with self._lock:
            return {
                "block_payments": self._block_payments,
                "block_credentials": self._block_credentials,
                "block_internet": self._block_internet,
                "hermetic_mode": self._hermetic_mode,
                "system_state": "HERMETIC" if self._hermetic_mode else "NORMAL",
            }

    def reset_all(self) -> None:
        """Desactiva todos los bloqueos (reset a estado normal)"""
        with self._lock:
            self._block_payments = False
            self._block_credentials = False
            self._block_internet = False
            self._hermetic_mode = False
            logger.warning("TODOS LOS BLOQUEOS DESACTIVADOS - SISTEMA EN MODO NORMAL")


# Singleton global
_hermetic_manager = None
_manager_lock = Lock()


def get_hermetic_manager() -> HermeticSecurityManager:
    """
    Obtiene la instancia singleton del HermeticSecurityManager

    Returns:
        Instancia de HermeticSecurityManager
    """
    global _hermetic_manager
    if _hermetic_manager is None:
        with _manager_lock:
            if _hermetic_manager is None:
                _hermetic_manager = HermeticSecurityManager()
    return _hermetic_manager


# Decoradores para verificar bloqueos
def check_payments_allowed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        manager = get_hermetic_manager()
        if manager.is_block_payments():
            error_msg = "❌ SISTEMA HERMÉTICO: Pagos bloqueados. Operación cancelada."
            logger.error(error_msg)
            raise HermeticSecurityError(error_msg)
        return func(*args, **kwargs)

    return wrapper


def check_credentials_allowed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        manager = get_hermetic_manager()
        if manager.is_block_credentials():
            error_msg = "❌ SISTEMA HERMÉTICO: Credenciales bloqueadas. Operación cancelada."
            logger.error(error_msg)
            raise HermeticSecurityError(error_msg)
        return func(*args, **kwargs)

    return wrapper


def check_internet_allowed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        manager = get_hermetic_manager()
        if manager.is_block_internet():
            error_msg = "❌ SISTEMA HERMÉTICO: Internet bloqueado. Operación cancelada."
            logger.error(error_msg)
            raise HermeticSecurityError(error_msg)
        return func(*args, **kwargs)

    return wrapper


# Excepción personalizada
class HermeticSecurityError(Exception):
    """Excepción lanzada cuando el sistema hermético bloquea una operación"""


# Funciones de conveniencia para control directo
def block_payments() -> None:
    """Activa el bloqueo de pagos"""
    get_hermetic_manager().set_block_payments(True)


def unblock_payments() -> None:
    """Desactiva el bloqueo de pagos"""
    get_hermetic_manager().set_block_payments(False)


def block_credentials() -> None:
    """Activa el bloqueo de credenciales"""
    get_hermetic_manager().set_block_credentials(True)


def unblock_credentials() -> None:
    """Desactiva el bloqueo de credenciales"""
    get_hermetic_manager().set_block_credentials(False)


def block_internet() -> None:
    """Activa el bloqueo de internet"""
    get_hermetic_manager().set_block_internet(True)


def unblock_internet() -> None:
    """Desactiva el bloqueo de internet"""
    get_hermetic_manager().set_block_internet(False)


def enable_hermetic_mode() -> None:
    """Activa el modo hermético total (bloquea todo)"""
    get_hermetic_manager().set_hermetic_mode(True)


def disable_hermetic_mode() -> None:
    """Desactiva el modo hermético total"""
    get_hermetic_manager().set_hermetic_mode(False)


def reset_hermetic_states() -> None:
    """Desactiva todos los bloqueos"""
    get_hermetic_manager().reset_all()


def get_hermetic_status() -> dict:
    """Obtiene el estado actual de los bloqueos"""
    return get_hermetic_manager().get_status()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Prueba del sistema
    print("=== PRUEBA DEL SISTEMA HERMÉTICO ===")

    # Estado inicial
    print("\nEstado inicial:")
    print(get_hermetic_status())

    # Bloquear pagos
    print("\nBloqueando pagos...")
    block_payments()
    print(get_hermetic_status())

    # Probar función con decorador
    @check_payments_allowed
    def test_payment():
        return "Pago ejecutado"

    try:
        test_payment()
    except HermeticSecurityError as e:
        print(f"✅ Bloqueo funciona: {e}")

    # Desbloquear
    print("\nDesbloqueando pagos...")
    unblock_payments()
    print(get_hermetic_status())

    # Probar de nuevo
    try:
        result = test_payment()
        print(f"✅ Desbloqueo funciona: {result}")
    except HermeticSecurityError:
        print("❌ Error: debería funcionar")

    # Modo hermético total
    print("\nActivando modo hermético total...")
    enable_hermetic_mode()
    print(get_hermetic_status())

    # Reset
    print("\nReseteando todos los bloqueos...")
    reset_hermetic_states()
    print(get_hermetic_status())
