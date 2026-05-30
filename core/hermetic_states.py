#!/usr/bin/env python3
"""
Módulo: core/hermetic_states.py
Propósito: Gestiona el modo hermético que bloquea pagos, credenciales e internet.
Dependencias: logging, threading
Reglas especiales: Al desactivar modo hermético, se deben desbloquear todos los flags individuales.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class HermeticSecurityManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._block_payments = False
        self._block_credentials = False
        self._block_internet = False
        self._hermetic_mode = False
        logger.info("HermeticSecurityManager inicializado")

    def is_block_payments(self) -> bool:
        return self._block_payments or self._hermetic_mode

    def is_block_credentials(self) -> bool:
        return self._block_credentials or self._hermetic_mode

    def is_block_internet(self) -> bool:
        return self._block_internet or self._hermetic_mode

    def set_hermetic_mode(self, enabled: bool):
        with self._lock:
            if enabled:
                self._block_payments = True
                self._block_credentials = True
                self._block_internet = True
                self._hermetic_mode = True
                logger.critical(
                    "MODO HERMÉTICO ACTIVADO - Pagos, credenciales e Internet bloqueados"
                )
            else:
                self._block_payments = False
                self._block_credentials = False
                self._block_internet = False
                self._hermetic_mode = False
                logger.info("MODO HERMÉTICO DESACTIVADO")

    def block_payments(self):
        with self._lock:
            self._block_payments = True
            logger.warning("Bloqueo de pagos activado manualmente")

    def block_credentials(self):
        with self._lock:
            self._block_credentials = True
            logger.warning("Bloqueo de credenciales activado manualmente")

    def block_internet(self):
        with self._lock:
            self._block_internet = True
            logger.warning("Bloqueo de internet activado manualmente")


# Singleton global
hermetic_manager = HermeticSecurityManager()
