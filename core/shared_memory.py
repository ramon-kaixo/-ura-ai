#!/usr/bin/env python3
"""
Memoria compartida entre agentes de URA
Permite que los agentes compartan contexto y pasen información entre sí
"""

from typing import Any
from datetime import datetime


class SharedMemory:
    """Memoria compartida entre agentes."""

    def __init__(self, max_keys: int = 1000):
        self._memory: dict[str, dict[str, Any]] = {}
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._max_keys: int = max_keys
        self._access_log: list[dict[str, Any]] = []

    def set(self, key: str, value: Any, agent: str = "system") -> bool:
        """
        Guardar valor en memoria compartida.

        Args:
            key: Clave para el valor
            value: Valor a guardar
            agent: Agente que guarda el valor

        Returns:
            True si se guardó correctamente, False si no
        """
        if not key or not isinstance(key, str):
            return False

        # Limitar número de claves
        if len(self._memory) >= self._max_keys and key not in self._memory:
            self._remove_oldest_key()

        self._memory[key] = {
            "value": value,
            "agent": agent,
            "timestamp": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
        }

        # Registrar acceso
        self._log_access(key, "set", agent)

        return True

    def get(self, key: str) -> Any | None:
        """
        Obtener valor de memoria compartida.

        Args:
            key: Clave del valor

        Returns:
            Valor o None si no existe
        """
        if key not in self._memory:
            return None

        # Actualizar timestamp de acceso
        self._memory[key]["updated"] = datetime.now().isoformat()

        # Registrar acceso
        self._log_access(key, "get", "system")

        return self._memory[key]["value"]

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        """
        Obtener metadata de una clave.

        Args:
            key: Clave del valor

        Returns:
            Dict con metadata o None si no existe
        """
        if key not in self._memory:
            return None

        return {
            "agent": self._memory[key]["agent"],
            "timestamp": self._memory[key]["timestamp"],
            "updated": self._memory[key]["updated"],
        }

    def delete(self, key: str) -> bool:
        """
        Eliminar clave de memoria compartida.

        Args:
            key: Clave a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        if key not in self._memory:
            return False

        del self._memory[key]
        self._log_access(key, "delete", "system")

        return True

    def list_keys(self) -> list[str]:
        """
        Listar todas las claves en memoria compartida.

        Returns:
            Lista de claves ordenadas por timestamp de actualización
        """
        keys = list(self._memory.keys())
        keys.sort(key=lambda k: self._memory[k].get("updated", ""), reverse=True)
        return keys

    def clear(self) -> None:
        """Limpiar toda la memoria compartida."""
        self._memory.clear()
        self._access_log.clear()

    def get_session_id(self) -> str:
        """Obtener ID de sesión actual."""
        return self._session_id

    def get_stats(self) -> dict[str, Any]:
        """
        Obtener estadísticas de uso.

        Returns:
            Dict con estadísticas
        """
        return {
            "total_keys": len(self._memory),
            "session_id": self._session_id,
            "max_keys": self._max_keys,
            "access_count": len(self._access_log),
            "agents": self._get_agent_stats(),
        }

    def _remove_oldest_key(self) -> None:
        """Eliminar la clave menos recientemente actualizada."""
        if not self._memory:
            return

        oldest_key = min(self._memory.keys(), key=lambda k: self._memory[k].get("updated", ""))
        del self._memory[oldest_key]

    def _log_access(self, key: str, action: str, agent: str) -> None:
        """Registrar acceso a memoria."""
        self._access_log.append(
            {"key": key, "action": action, "agent": agent, "timestamp": datetime.now().isoformat()}
        )

        # Limitar tamaño del log
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-500:]

    def _get_agent_stats(self) -> dict[str, int]:
        """Obtener estadísticas por agente."""
        stats = {}
        for entry in self._access_log:
            agent = entry.get("agent", "unknown")
            stats[agent] = stats.get(agent, 0) + 1
        return stats

    def to_dict(self) -> dict[str, Any]:
        """
        Convertir memoria a diccionario para serialización.

        Returns:
            Dict con datos serializables
        """
        return {
            "session_id": self._session_id,
            "memory": dict(self._memory.items()),
            "stats": self.get_stats(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Cargar memoria desde diccionario.

        Args:
            data: Diccionario con datos
        """
        self._session_id = data.get("session_id", self._session_id)
        self._memory = data.get("memory", {})
        self._max_keys = data.get("stats", {}).get("max_keys", self._max_keys)


# Singleton global
_shared_memory: SharedMemory | None = None


def get_shared_memory() -> SharedMemory:
    """Obtener instancia singleton de memoria compartida."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SharedMemory()
    return _shared_memory


def reset_shared_memory() -> None:
    """Resetear memoria compartida (crear nueva instancia)."""
    global _shared_memory
    _shared_memory = SharedMemory()
