"""
core/storage_manager.py - Gestor de Almacenamiento Multi-Nube
Integra MEGAcmd, Google Drive y Dropbox con verificación de salud de conexión
"""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConnectionHealth:
    """Estado de salud de conexión"""

    service: str
    is_connected: bool
    status_message: str
    last_checked: str
    can_upload: bool
    can_download: bool


class StorageManager:
    """Gestor de almacenamiento multi-nube"""

    def __init__(self):
        # Rutas de comandos
        self.mega_cmd = "/Applications/MEGAcmd.app/Contents/MacOS/mega-exec"
        self.mega_available = self._check_mega_available()

        # Configuración de servicios
        self.services = {
            "mega": {
                "name": "MEGA",
                "enabled": self.mega_available,
                "backup_path": "URA_DNA_BACKUP",
            },
            "google_drive": {
                "name": "Google Drive",
                "enabled": False,  # Requiere API key
                "backup_path": "URA_DNA_BACKUP",
            },
            "dropbox": {
                "name": "Dropbox",
                "enabled": False,  # Requiere API key
                "backup_path": "URA_DNA_BACKUP",
            },
        }

    def _check_mega_available(self) -> bool:
        """Verificar si MEGAcmd está disponible"""
        try:
            result = subprocess.run(
                [self.mega_cmd, "version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"MEGAcmd not available: {e}")
            return False

    def check_mega_connection_health(self) -> ConnectionHealth:
        """
        Verificar salud de conexión MEGA

        Returns:
            ConnectionHealth con estado de la conexión
        """
        if not self.mega_available:
            return ConnectionHealth(
                service="MEGA",
                is_connected=False,
                status_message="MEGAcmd no está disponible",
                last_checked=datetime.now().isoformat(),
                can_upload=False,
                can_download=False,
            )

        try:
            # Verificar si hay sesión activa
            result = subprocess.run(
                [self.mega_cmd, "whoami"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                username = result.stdout.strip()

                # Verificar si puede listar archivos (prueba de conexión)
                list_result = subprocess.run(
                    [self.mega_cmd, "ls", "/"], capture_output=True, text=True, timeout=10
                )

                can_upload = list_result.returncode == 0
                can_download = can_upload  # Si puede listar, puede descargar

                return ConnectionHealth(
                    service="MEGA",
                    is_connected=True,
                    status_message=f"Conectado como {username}",
                    last_checked=datetime.now().isoformat(),
                    can_upload=can_upload,
                    can_download=can_download,
                )
            else:
                return ConnectionHealth(
                    service="MEGA",
                    is_connected=False,
                    status_message="No hay sesión activa de MEGA. Ejecuta: mega-login",
                    last_checked=datetime.now().isoformat(),
                    can_upload=False,
                    can_download=False,
                )

        except subprocess.TimeoutExpired:
            return ConnectionHealth(
                service="MEGA",
                is_connected=False,
                status_message="Timeout verificando conexión",
                last_checked=datetime.now().isoformat(),
                can_upload=False,
                can_download=False,
            )
        except Exception as e:
            return ConnectionHealth(
                service="MEGA",
                is_connected=False,
                status_message=f"Error verificando conexión: {str(e)}",
                last_checked=datetime.now().isoformat(),
                can_upload=False,
                can_download=False,
            )

    def mega_backup(self, source_path: Path, backup_name: str) -> dict:
        """
        Realizar backup a MEGA

        Args:
            source_path: Ruta de origen
            backup_name: Nombre del backup

        Returns:
            Dict con resultados del backup
        """
        # Primero verificar salud de conexión
        health = self.check_mega_connection_health()

        if not health.is_connected:
            return {
                "success": False,
                "error": f"MEGA no está conectado: {health.status_message}",
                "health": health.__dict__,
            }

        if not health.can_upload:
            return {
                "success": False,
                "error": "MEGA no puede subir archivos",
                "health": health.__dict__,
            }

        try:
            # Ruta en MEGA
            mega_path = f"/{self.services['mega']['backup_path']}/{backup_name}"

            logger.info(f"Iniciando backup a MEGA: {source_path} -> {mega_path}")

            # Crear directorio en MEGA
            mkdir_result = subprocess.run(
                [self.mega_cmd, "mkdir", "-p", mega_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if mkdir_result.returncode != 0:
                logger.warning(f"Error creando directorio en MEGA: {mkdir_result.stderr}")

            # Subir archivos
            result = subprocess.run(
                [self.mega_cmd, "put", "-r", str(source_path), mega_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos timeout
            )

            if result.returncode == 0:
                logger.info(f"Backup a MEGA completado: {mega_path}")

                # Verificar que se subió correctamente
                verify_result = subprocess.run(
                    [self.mega_cmd, "ls", mega_path], capture_output=True, text=True, timeout=10
                )

                if verify_result.returncode == 0:
                    files_count = (
                        len(verify_result.stdout.strip().split("\n"))
                        if verify_result.stdout.strip()
                        else 0
                    )

                    return {
                        "success": True,
                        "backup_path": mega_path,
                        "files_count": files_count,
                        "health": health.__dict__,
                        "message": f"Backup completado exitosamente. {files_count} archivos subidos",
                    }
                else:
                    return {
                        "success": True,
                        "backup_path": mega_path,
                        "files_count": 0,
                        "health": health.__dict__,
                        "message": "Backup completado pero no se pudo verificar",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Error subiendo a MEGA: {result.stderr}",
                    "health": health.__dict__,
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout subiendo a MEGA", "health": health.__dict__}
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en backup MEGA: {str(e)}",
                "health": health.__dict__,
            }

    def mega_login(self, email: str, password: str) -> bool:
        """
        Iniciar sesión en MEGA

        Args:
            email: Email de MEGA
            password: Contraseña de MEGA

        Returns:
            True si login exitoso
        """
        try:
            result = subprocess.run(
                [self.mega_cmd, "login", email, password],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"Login MEGA exitoso para {email}")
                return True
            else:
                logger.error(f"Error login MEGA: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error login MEGA: {e}")
            return False

    def mega_logout(self) -> bool:
        """Cerrar sesión en MEGA"""
        try:
            result = subprocess.run(
                [self.mega_cmd, "logout"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                logger.info("Logout MEGA exitoso")
                return True
            else:
                logger.error(f"Error logout MEGA: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error logout MEGA: {e}")
            return False

    def google_drive_backup(self, source_path: Path, backup_name: str) -> dict:
        """
        Realizar backup a Google Drive (placeholder - requiere API key)

        Args:
            source_path: Ruta de origen
            backup_name: Nombre del backup

        Returns:
            Dict con resultados del backup
        """
        return {
            "success": False,
            "error": "Google Drive no configurado. Requiere API key de Google Cloud Console",
            "service": "Google Drive",
            "enabled": False,
        }

    def dropbox_backup(self, source_path: Path, backup_name: str) -> dict:
        """
        Realizar backup a Dropbox (placeholder - requiere API key)

        Args:
            source_path: Ruta de origen
            backup_name: Nombre del backup

        Returns:
            Dict con resultados del backup
        """
        return {
            "success": False,
            "error": "Dropbox no configurado. Requiere API key de Dropbox App Console",
            "service": "Dropbox",
            "enabled": False,
        }

    def perform_multi_cloud_backup(self, source_path: Path, backup_name: str) -> dict:
        """
        Realizar backup a múltiples nubes disponibles

        Args:
            source_path: Ruta de origen
            backup_name: Nombre del backup

        Returns:
            Dict con resultados de todos los backups
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "backup_name": backup_name,
            "services": {},
        }

        # Backup a MEGA
        if self.mega_available:
            mega_result = self.mega_backup(source_path, backup_name)
            results["services"]["mega"] = mega_result
        else:
            results["services"]["mega"] = {
                "success": False,
                "error": "MEGAcmd no disponible",
                "enabled": False,
            }

        # Backup a Google Drive (placeholder)
        google_result = self.google_drive_backup(source_path, backup_name)
        results["services"]["google_drive"] = google_result

        # Backup a Dropbox (placeholder)
        dropbox_result = self.dropbox_backup(source_path, backup_name)
        results["services"]["dropbox"] = dropbox_result

        # Contar servicios exitosos
        successful = sum(1 for s in results["services"].values() if s.get("success"))
        total = len(results["services"])

        results["summary"] = {
            "total_services": total,
            "successful": successful,
            "failed": total - successful,
        }

        return results

    def get_all_connection_health(self) -> dict[str, ConnectionHealth]:
        """
        Obtener estado de salud de todas las conexiones

        Returns:
            Dict con estado de salud de cada servicio
        """
        health_status = {}

        # MEGA
        health_status["mega"] = self.check_mega_connection_health()

        # Google Drive (placeholder)
        health_status["google_drive"] = ConnectionHealth(
            service="Google Drive",
            is_connected=False,
            status_message="No configurado - Requiere API key",
            last_checked=datetime.now().isoformat(),
            can_upload=False,
            can_download=False,
        )

        # Dropbox (placeholder)
        health_status["dropbox"] = ConnectionHealth(
            service="Dropbox",
            is_connected=False,
            status_message="No configurado - Requiere API key",
            last_checked=datetime.now().isoformat(),
            can_upload=False,
            can_download=False,
        )

        return health_status


def get_storage_manager() -> StorageManager:
    """Factory function para obtener instancia de StorageManager"""
    return StorageManager()


if __name__ == "__main__":
    # Prueba del gestor de almacenamiento
    manager = get_storage_manager()

    print("Verificando disponibilidad de servicios:")
    print(f"MEGA disponible: {manager.mega_available}")

    print("\nVerificando salud de conexiones:")
    health = manager.get_all_connection_health()
    for service, status in health.items():
        print(f"  {service}: {'✅' if status.is_connected else '❌'} {status.status_message}")
