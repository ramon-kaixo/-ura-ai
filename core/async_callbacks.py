#!/usr/bin/env python3
"""
Sistema de callbacks asíncronos para agentes de URA
"""

import asyncio
import uuid
from typing import Callable, Any
from datetime import datetime


class AsyncCallbackManager:
    """Gestor de callbacks asíncronos."""

    def __init__(self):
        self._callbacks: dict[str, Callable] = {}
        self._results: dict[str, Any] = {}
        self._pending: dict[str, bool] = {}

    def register_callback(self, callback_id: str | None = None) -> str:
        """
        Registrar un nuevo callback.

        Args:
            callback_id: ID opcional del callback (se genera uno si no se proporciona)

        Returns:
            ID del callback
        """
        if callback_id is None:
            callback_id = str(uuid.uuid4())

        self._pending[callback_id] = True
        return callback_id

    async def execute_callback(
        self, callback_id: str, callback_func: Callable, *args, **kwargs
    ) -> Any:
        """
        Ejecutar callback de forma asíncrona.

        Args:
            callback_id: ID del callback
            callback_func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre

        Returns:
            Resultado del callback
        """
        try:
            result = await callback_func(*args, **kwargs)
            self._results[callback_id] = {
                "success": True,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
            return result
        except Exception as e:
            self._results[callback_id] = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            raise
        finally:
            self._pending[callback_id] = False

    def get_callback_result(self, callback_id: str) -> dict[str, Any] | None:
        """
        Obtener resultado de un callback.

        Args:
            callback_id: ID del callback

        Returns:
            Dict con el resultado o None si no existe
        """
        return self._results.get(callback_id)

    def is_callback_pending(self, callback_id: str) -> bool:
        """
        Verificar si un callback está pendiente.

        Args:
            callback_id: ID del callback

        Returns:
            True si está pendiente, False en caso contrario
        """
        return self._pending.get(callback_id, False)

    def clear_callback(self, callback_id: str) -> None:
        """
        Limpiar un callback.

        Args:
            callback_id: ID del callback
        """
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]
        if callback_id in self._results:
            del self._results[callback_id]
        if callback_id in self._pending:
            del self._pending[callback_id]

    def clear_all(self) -> None:
        """Limpiar todos los callbacks."""
        self._callbacks.clear()
        self._results.clear()
        self._pending.clear()


# Singleton global
_callback_manager: AsyncCallbackManager | None = None


def get_callback_manager() -> AsyncCallbackManager:
    """Obtener instancia singleton del gestor de callbacks."""
    global _callback_manager
    if _callback_manager is None:
        _callback_manager = AsyncCallbackManager()
    return _callback_manager


def reset_callback_manager() -> None:
    """Resetear gestor de callbacks (crear nueva instancia)."""
    global _callback_manager
    _callback_manager = AsyncCallbackManager()


async def run_async_operation(
    operation: Callable, *args, timeout: float = 30.0, **kwargs
) -> dict[str, Any]:
    """
    Ejecutar operación asíncrona con timeout.

    Args:
        operation: Función a ejecutar
        *args: Argumentos posicionales
        timeout: Timeout en segundos
        **kwargs: Argumentos con nombre

    Returns:
        Dict con el resultado
    """
    callback_manager = get_callback_manager()
    callback_id = callback_manager.register_callback()

    try:
        result = await asyncio.wait_for(
            callback_manager.execute_callback(callback_id, operation, *args, **kwargs),
            timeout=timeout,
        )

        return {"success": True, "callback_id": callback_id, "result": result}
    except TimeoutError:
        return {"success": False, "callback_id": callback_id, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "callback_id": callback_id, "error": str(e)}
