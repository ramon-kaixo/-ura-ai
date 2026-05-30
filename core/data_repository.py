#!/usr/bin/env python3
"""
Data Repository - FASE 1.2
─────────────────────────
Acceso a datos con bloqueo de archivos para evitar condiciones de carrera.
"""

import json
from pathlib import Path
from typing import Any
from filelock import FileLock

from core.logging_config import get_logger

logger = get_logger("data_repository", log_dir="./logs")


class DataRepository:
    """
    Repositorio de datos con bloqueo de archivos.

    Uso:
        repo = DataRepository(base_path="/path/to/data")
        repo.save_json("config", {"key": "value"})
        data = repo.load_json("config")
    """

    def __init__(self, base_path: Path | None = None):
        """
        Inicializar repositorio.

        Args:
            base_path: Ruta base para datos (default: ~/.ura/data)
        """
        if base_path is None:
            base_path = Path.home() / ".ura" / "data"

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"DataRepository inicializado en {self.base_path}")

    def _get_file_path(self, key: str) -> Path:
        """Obtiene ruta del archivo para una clave."""
        return self.base_path / f"{key}.json"

    def _get_lock_path(self, key: str) -> Path:
        """Obtiene ruta del archivo de bloqueo."""
        return self.base_path / f"{key}.lock"

    def save_json(self, key: str, data: Any) -> bool:
        """
        Guarda datos en formato JSON con bloqueo.

        Args:
            key: Clave para identificar los datos
            data: Datos a guardar (deben ser serializables a JSON)

        Returns:
            True si exitoso, False si error
        """
        file_path = self._get_file_path(key)
        lock_path = self._get_lock_path(key)

        try:
            with FileLock(lock_path, timeout=10):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.debug(f"Datos guardados: {key}")
                return True
        except Exception as e:
            logger.error(f"Error guardando datos '{key}': {e}")
            return False

    def load_json(self, key: str, default: Any = None) -> Any:
        """
        Carga datos en formato JSON con bloqueo.

        Args:
            key: Clave para identificar los datos
            default: Valor por defecto si no existe

        Returns:
            Datos cargados o default
        """
        file_path = self._get_file_path(key)
        lock_path = self._get_lock_path(key)

        if not file_path.exists():
            return default

        try:
            with FileLock(lock_path, timeout=10):
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Datos cargados: {key}")
                return data
        except Exception as e:
            logger.error(f"Error cargando datos '{key}': {e}")
            return default

    def delete(self, key: str) -> bool:
        """
        Elimina datos.

        Args:
            key: Clave para identificar los datos

        Returns:
            True si exitoso, False si error
        """
        file_path = self._get_file_path(key)
        lock_path = self._get_lock_path(key)

        try:
            with FileLock(lock_path, timeout=10):
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Datos eliminados: {key}")
                return True
        except Exception as e:
            logger.error(f"Error eliminando datos '{key}': {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Verifica si existen datos para una clave.

        Args:
            key: Clave para verificar

        Returns:
            True si existe, False si no
        """
        file_path = self._get_file_path(key)
        return file_path.exists()

    def list_keys(self) -> list[str]:
        """
        Lista todas las claves disponibles.

        Returns:
            Lista de claves
        """
        return [f.stem for f in self.base_path.glob("*.json") if not f.name.endswith(".lock")]


# ── Singleton ──────────────────────────────────────────────

_repository: DataRepository | None = None


def get_data_repository() -> DataRepository:
    """Retorna instancia global de DataRepository."""
    global _repository
    if _repository is None:
        _repository = DataRepository()
    return _repository


def reset_data_repository() -> None:
    """Resetea instancia global."""
    global _repository
    _repository = None


if __name__ == "__main__":
    # Test
    repo = DataRepository()

    # Test save/load
    repo.save_json("test", {"key": "value"})
    data = repo.load_json("test")
    print(f"Datos: {data}")

    # Test exists
    print(f"Existe 'test': {repo.exists('test')}")
    print(f"Existe 'no_existe': {repo.exists('no_existe')}")

    # Test list
    print(f"Claves: {repo.list_keys()}")

    # Test delete
    repo.delete("test")
    print(f"Después de eliminar: {repo.exists('test')}")
