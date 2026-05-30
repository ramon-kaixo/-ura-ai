#!/usr/bin/env python3
"""
iCloud Sync - Fase 7
Sincronización con iCloud Drive para multi-dispositivo.
Sincroniza ~/.ura/ con iCloud Drive cada hora.
"""

import json
import logging
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

URA_PATH = Path.home() / ".ura"
SYNC_LOG_PATH = URA_PATH / "sync_log.json"


class ICloudSync:
    """Sincronización con iCloud Drive."""

    def __init__(self, sync_interval: int = 3600):  # 1 hora por defecto
        self.icloud_path = self._detect_icloud_path()
        self.sync_interval = sync_interval
        self._running = False
        self._thread = None
        self.sync_log = self._load_sync_log()

    def _load_sync_log(self) -> dict[str, str]:
        """Cargar log de sincronización."""
        if SYNC_LOG_PATH.exists():
            try:
                with open(SYNC_LOG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando sync log: {e}")
        return {}

    def _detect_icloud_path(self) -> Path | None:
        """
        Detectar ruta de iCloud automáticamente.

        Returns:
            Ruta de iCloud o None si no se encuentra
        """
        # Rutas comunes de iCloud en macOS
        possible_paths = [
            Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
            Path.home() / "iCloud",
            Path.home() / "Library" / "CloudStorage" / "com~apple~CloudDocs",
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"iCloud detectado en: {path}")
                return path

        logger.warning("No se detectó iCloud Drive")
        return None

    def get_icloud_path(self) -> str | None:
        """
        Obtener ruta de iCloud.

        Returns:
            Ruta de iCloud o None
        """
        return str(self.icloud_path) if self.icloud_path else None

    def sync_to_icloud(self, local_path: str, icloud_folder: str = "URA") -> bool:
        """
        Sincronizar archivo local a iCloud.

        Args:
            local_path: Ruta del archivo local
            icloud_folder: Carpeta destino en iCloud

        Returns:
            True si exitoso, False si no
        """
        if not self.icloud_path:
            logger.error("iCloud no disponible")
            return False

        try:
            local = Path(local_path)
            if not local.exists():
                logger.error(f"Archivo local no encontrado: {local_path}")
                return False

            # Crear carpeta destino
            dest_folder = self.icloud_path / icloud_folder
            dest_folder.mkdir(parents=True, exist_ok=True)

            # Copiar archivo
            dest_file = dest_folder / local.name
            shutil.copy2(local, dest_file)

            logger.info(f"Archivo sincronizado a iCloud: {dest_file}")
            return True
        except Exception as e:
            logger.error(f"Error sincronizando a iCloud: {e}")
            return False

    def sync_from_icloud(self, icloud_folder: str = "URA", local_dest: str = None) -> bool:
        """
        Sincronizar archivo desde iCloud.

        Args:
            icloud_folder: Carpeta origen en iCloud
            local_dest: Ruta destino local (si None, usa home/URA)

        Returns:
            True si exitoso, False si no
        """
        if not self.icloud_path:
            logger.error("iCloud no disponible")
            return False

        try:
            source_folder = self.icloud_path / icloud_folder
            if not source_folder.exists():
                logger.error(f"Carpeta iCloud no encontrada: {source_folder}")
                return False

            # Determinar destino local
            if local_dest:
                dest = Path(local_dest)
            else:
                dest = Path.home() / "URA" / icloud_folder

            dest.mkdir(parents=True, exist_ok=True)

            # Copiar archivos
            for file in source_folder.iterdir():
                if file.is_file():
                    # Manejar conflictos por timestamp
                    local_file = dest / file.name
                    if local_file.exists():
                        # Comparar timestamps
                        local_mtime = local_file.stat().st_mtime
                        remote_mtime = file.stat().st_mtime
                        if remote_mtime > local_mtime:
                            shutil.copy2(file, local_file)
                            logger.info(f"Archivo actualizado desde iCloud: {file.name}")
                    else:
                        shutil.copy2(file, dest / file.name)
                        logger.info(f"Archivo sincronizado desde iCloud: {file.name}")

            return True
        except Exception as e:
            logger.error(f"Error sincronizando desde iCloud: {e}")
            return False

    def sync_ura_folder(self) -> bool:
        """Sincroniza toda la carpeta ~/.ura/ con iCloud."""
        if not self.icloud_path:
            logger.warning("iCloud no disponible, saltando sincronización")
            return False

        try:
            # Crear carpeta URA en iCloud
            icloud_ura = self.icloud_path / "URA"
            icloud_ura.mkdir(parents=True, exist_ok=True)

            # Usar rsync para sincronización eficiente
            cmd = ["rsync", "-avz", "--delete", str(URA_PATH) + "/", str(icloud_ura) + "/"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                # Registrar timestamp de sincronización
                self.sync_log["last_sync"] = datetime.now().isoformat()
                self.sync_log["status"] = "success"
                self._save_sync_log()
                logger.info(f"Sincronización completada: {self.sync_log['last_sync']}")
                return True
            else:
                logger.error(f"Error en rsync: {result.stderr}")
                self.sync_log["status"] = "failed"
                self.sync_log["error"] = result.stderr
                self._save_sync_log()
                return False

        except subprocess.TimeoutExpired:
            logger.error("Timeout en sincronización rsync")
            return False
        except Exception as e:
            logger.error(f"Error sincronizando ~/.ura/: {e}")
            return False

    def _save_sync_log(self):
        """Guardar log de sincronización."""
        try:
            with open(SYNC_LOG_PATH, "w") as f:
                json.dump(self.sync_log, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando sync log: {e}")

    def start_auto_sync(self):
        """Inicia sincronización automática en segundo plano."""
        if self._running:
            logger.warning("Auto-sync ya está corriendo")
            return

        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info(f"Auto-sync iniciado (intervalo: {self.sync_interval}s)")

    def _sync_loop(self):
        """Bucle de sincronización automática."""
        while self._running:
            try:
                self.sync_ura_folder()
            except Exception as e:
                logger.error(f"Error en auto-sync: {e}")

            time.sleep(self.sync_interval)

    def stop_auto_sync(self):
        """Detiene sincronización automática."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Auto-sync detenido")

    def get_sync_status(self) -> dict:
        """Obtener estado de sincronización."""
        return {
            "icloud_available": self.icloud_path is not None,
            "icloud_path": str(self.icloud_path) if self.icloud_path else None,
            "last_sync": self.sync_log.get("last_sync"),
            "status": self.sync_log.get("status"),
            "auto_sync_running": self._running,
        }


# Singleton
_icloud_sync: ICloudSync | None = None


def get_icloud_sync(sync_interval: int = 3600) -> ICloudSync:
    """Obtener el singleton de sincronización iCloud."""
    global _icloud_sync
    if _icloud_sync is None:
        _icloud_sync = ICloudSync(sync_interval=sync_interval)
    return _icloud_sync


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync = get_icloud_sync()

    print(f"iCloud: {sync.get_icloud_path()}")
    print(f"Estado: {sync.get_sync_status()}")

    # Sincronización manual
    print("Sincronizando ~/.ura/ con iCloud...")
    if sync.sync_ura_folder():
        print("Sincronización completada")
    else:
        print("Error en sincronización")
