#!/usr/bin/env python3
"""
URA Log Rotator - Rotación de logs
Rota LOG_ACTIVIDAD_URA.md cuando supera 5 MB
"""

import gzip
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class URALogRotator:
    """Rotador de logs de URA"""

    def __init__(self, log_path: Path = None, max_size_mb: int = 5):
        self.log_path = log_path or Path.home() / ".ura" / "LOG_ACTIVIDAD_URA.md"
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.keep_days = 30

    def should_rotate(self) -> bool:
        """Determinar si el log necesita rotación"""
        if not self.log_path.exists():
            return False
        return self.log_path.stat().st_size > self.max_size_bytes

    def rotate(self):
        """Rotar el log actual"""
        if not self.should_rotate():
            logger.info("Log no necesita rotación")
            return

        try:
            # Crear nombre de archivo archivado
            timestamp = datetime.now().strftime("%Y%m%d")
            archive_path = self.log_path.parent / f"LOG_ACTIVIDAD_URA.{timestamp}.md.gz"

            # Comprimir el log actual
            with open(self.log_path, "rb") as f_in:
                with gzip.open(archive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Limpiar el log actual
            self.log_path.write_text(f"# LOG ROTADO - {datetime.now().isoformat()}\n\n")

            logger.info(f"Log rotado: {self.log_path} -> {archive_path}")

            # Limpiar archivos antiguos
            self.cleanup_old_logs()

        except Exception as e:
            logger.error(f"Error rotando log: {e}")

    def cleanup_old_logs(self):
        """Eliminar logs archivados más antiguos que keep_days"""
        try:
            cutoff_date = datetime.now().timestamp() - (self.keep_days * 86400)

            for log_file in self.log_path.parent.glob("LOG_ACTIVIDAD_URA.*.md.gz"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    logger.info(f"Log antiguo eliminado: {log_file}")

        except Exception as e:
            logger.error(f"Error limpiando logs antiguos: {e}")


def main():
    """Función principal"""
    logging.basicConfig(level=logging.INFO)
    rotator = URALogRotator()
    rotator.rotate()


if __name__ == "__main__":
    main()
