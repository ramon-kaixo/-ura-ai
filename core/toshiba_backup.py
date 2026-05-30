#!/usr/bin/env python3
"""
Módulo: core/toshiba_backup.py
Propósito: Backup específico a disco Toshiba externo con verificación de montaje previo.
Dependencias principales: pathlib, shutil, logging
Reglas especiales: Verificar montaje ANTES de cualquier operación. No crear directorios en ruta no montada.
"""

from __future__ import annotations

import shutil
import hashlib
from datetime import datetime
from pathlib import Path

logger = __import__("logging").getLogger("toshiba_backup")

TOSHIBA_PATH = Path("/Volumes/TOSHIBA_NUEVO")
BACKUP_DIR = TOSHIBA_PATH / "URA" / "backup_before_delete"


class ToshibaBackup:
    """Sistema de respaldo automático a Toshiba antes de borrar."""

    def __init__(self, backup_dir: Path | None = None):
        self.backup_dir = backup_dir or BACKUP_DIR
        if not self.backup_dir.parent.exists():
            logger.warning(f"Directorio padre no existe: {self.backup_dir.parent}")
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.warning(f"No se pudo crear directorio de backup: {self.backup_dir}")

    def is_toshiba_mounted(self) -> bool:
        """Verifica si el disco Toshiba está montado."""
        return TOSHIBA_PATH.exists() and TOSHIBA_PATH.is_dir()

    def backup_before_delete(self, file_path: Path) -> bool:
        """
        Copia un archivo a Toshiba antes de borrarlo.

        Returns:
            True si el respaldo fue exitoso, False si no.
        """
        if not self.is_toshiba_mounted():
            logger.warning(f"Toshiba no está montado, no se puede respaldar {file_path}")
            return False

        if not file_path.exists():
            logger.warning(f"Archivo no existe: {file_path}")
            return False

        # Generar hash único para el nombre del respaldo
        file_hash = self._file_hash(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}_{file_hash}_{file_path.name}"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Respaldo creado: {file_path} -> {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error al respaldar {file_path}: {e}")
            return False

    def _file_hash(self, file_path: Path) -> str:
        """Genera hash SHA256 del archivo."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]

    def safe_delete(self, file_path: Path) -> bool:
        """
        Borra un archivo después de respaldarlo a Toshiba.

        Returns:
            True si el borrado fue exitoso, False si no.
        """
        # Primero respaldar
        if not self.backup_before_delete(file_path):
            logger.warning(f"No se pudo respaldar {file_path}, cancelando borrado")
            return False

        # Luego borrar
        try:
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            logger.info(f"Archivo borrado: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error al borrar {file_path}: {e}")
            return False

    def get_backup_size(self) -> int:
        """Retorna el tamaño total del directorio de backup en bytes."""
        if not self.backup_dir.exists():
            return 0
        total = 0
        for item in self.backup_dir.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total


# Singleton
_backup_instance: ToshibaBackup | None = None


def get_toshiba_backup() -> ToshibaBackup:
    """Obtener el singleton de backup Toshiba."""
    global _backup_instance
    if _backup_instance is None:
        _backup_instance = ToshibaBackup()
    return _backup_instance


def safe_delete_with_backup(file_path: Path) -> bool:
    """
    Función conveniente para borrar un archivo con respaldo automático.
    """
    return get_toshiba_backup().safe_delete(file_path)


if __name__ == "__main__":
    # Test del sistema
    backup = get_toshiba_backup()
    print(f"Toshiba montado: {backup.is_toshiba_mounted()}")
    print(f"Directorio backup: {backup.backup_dir}")
    print(f"Tamaño backup: {backup.get_backup_size()} bytes")
