#!/usr/bin/env python3
"""
Módulo: core/backup_system.py
Propósito: Backup automático a disco externo Toshiba con rotación de versiones.
Dependencias principales: pathlib, shutil, psutil, schedule
Reglas especiales: Verificar que disco Toshiba esté montado antes de cualquier operación.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class URABackupSystem:
    """Sistema de backup de URA"""

    def __init__(self, source_dir: Path = None, backup_dir: Path = None):
        self.source_dir = source_dir or Path.home() / ".ura" / "output"
        self.backup_dir = backup_dir or Path.home() / ".ura" / "backups"
        self.keep_days = 7

    def create_backup(self) -> Path:
        """Crear backup del directorio de salida"""
        try:
            # Crear directorio de backup si no existe
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Crear nombre de backup con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            backup_path = self.backup_dir / timestamp

            # Crear backup
            if self.source_dir.exists():
                shutil.copytree(self.source_dir, backup_path)
                logger.info(f"Backup creado: {backup_path}")
            else:
                backup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Directorio de origen no existe, backup vacío creado: {backup_path}")

            # Limpiar backups antiguos
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Error creando backup: {e}")
            raise

    def backup_config_files(self):
        """Backup de archivos de configuración críticos"""
        try:
            config_backup_dir = self.backup_dir / "config"
            config_backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup telegram_config.json
            telegram_config = Path.home() / ".ura" / "telegram_config.json"
            if telegram_config.exists():
                shutil.copy2(telegram_config, config_backup_dir / "telegram_config.json")

            # Backup ecosystem.config.js si existe
            ecosystem_config = Path.home() / ".ura" / "ecosystem.config.js"
            if ecosystem_config.exists():
                shutil.copy2(ecosystem_config, config_backup_dir / "ecosystem.config.js")

            logger.info("Config files backed up")

        except Exception as e:
            logger.error(f"Error backup config files: {e}")

    def cleanup_old_backups(self):
        """Eliminar backups más antiguos que keep_days"""
        try:
            cutoff_date = datetime.now().timestamp() - (self.keep_days * 86400)

            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir() and backup_dir.name != "config":
                    if backup_dir.stat().st_mtime < cutoff_date:
                        shutil.rmtree(backup_dir)
                        logger.info(f"Backup antiguo eliminado: {backup_dir}")

        except Exception as e:
            logger.error(f"Error limpiando backups antiguos: {e}")


def main():
    """Función principal"""
    logging.basicConfig(level=logging.INFO)
    backup_system = URABackupSystem()
    backup_system.create_backup()
    backup_system.backup_config_files()


if __name__ == "__main__":
    main()
