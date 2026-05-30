#!/usr/bin/env python3
"""
URA Auto Sync System
Sistema automático de sincronización y backup para URA
"""

import argparse
import json
import logging
import py_compile
import shutil
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("WARNING: watchdog no instalado, modo auto no disponible")


class URASyncConfig:
    """Gestor de configuración del sistema de sincronización"""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Carga configuración desde archivo JSON"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene valor de configuración"""
        return self.config.get(key, default)

    def get_source_dir(self) -> Path:
        return Path(self.config["source_dir"])

    def get_backup_dir(self) -> Path:
        backup_dir = Path(self.config["backup_dir"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def get_current_link(self) -> Path:
        return Path(self.config["current_link"])


class PythonSyntaxValidator:
    """Validador de sintaxis Python"""

    @staticmethod
    def validate_file(file_path: Path) -> bool:
        """Valida sintaxis de un archivo Python"""
        if file_path.suffix != ".py":
            return True

        try:
            py_compile.compile(str(file_path), doraise=True)
            return True
        except py_compile.PyCompileError as e:
            logging.error(f"Syntax error in {file_path}: {e}")
            return False

    @staticmethod
    def validate_directory(directory: Path, exclude_patterns: list[str]) -> bool:
        """Valida sintaxis de todos los archivos Python en un directorio"""
        for py_file in directory.rglob("*.py"):
            # Skip excluded patterns
            if any(pattern in str(py_file) for pattern in exclude_patterns):
                continue

            if not PythonSyntaxValidator.validate_file(py_file):
                return False
        return True


class BackupManager:
    """Gestor de backups automáticos"""

    def __init__(self, config: URASyncConfig):
        self.config = config
        self.backup_dir = config.get_backup_dir()
        self.max_backups = config.get("max_backups", 10)
        self.retention_days = config.get("backup_retention_days", 30)
        self.current_link = config.get_current_link()

    def create_backup(self, source_dir: Path) -> Path | None:
        """Crea backup del directorio fuente"""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name

        try:
            # Create backup using rsync for efficiency
            exclude_args = []
            for pattern in self.config.get("exclude_patterns", []):
                exclude_args.extend(["--exclude", pattern])

            cmd = (
                ["rsync", "-av", "--delete"]
                + exclude_args
                + [str(source_dir) + "/", str(backup_path)]
            )
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logging.info(f"Backup creado: {backup_path}")
                self._update_current_link(backup_path)
                self._cleanup_old_backups()
                return backup_path
            else:
                logging.error(f"Error creando backup: {result.stderr}")
                return None
        except Exception as e:
            logging.error(f"Error creando backup: {e}")
            return None

    def _update_current_link(self, latest_backup: Path):
        """Actualiza enlace simbólico current"""
        try:
            if self.current_link.exists():
                self.current_link.unlink()
            self.current_link.symlink_to(latest_backup)
            logging.info(f"Enlace current actualizado: {latest_backup}")
        except Exception as e:
            logging.error(f"Error actualizando enlace current: {e}")

    def _cleanup_old_backups(self):
        """Limpia backups antiguos"""
        now = datetime.now()
        backups = sorted(
            self.backup_dir.glob("backup_*"), key=lambda x: x.stat().st_mtime, reverse=True
        )

        # Remove backups older than retention_days
        for backup in backups:
            backup_time = datetime.fromtimestamp(backup.stat().st_mtime)
            if (now - backup_time).days > self.retention_days:
                try:
                    shutil.rmtree(backup)
                    logging.info(f"Backup antiguo eliminado: {backup}")
                except Exception as e:
                    logging.error(f"Error eliminando backup antiguo {backup}: {e}")

        # Keep only max_backups most recent
        backups = sorted(
            self.backup_dir.glob("backup_*"), key=lambda x: x.stat().st_mtime, reverse=True
        )
        for backup in backups[self.max_backups :]:
            try:
                shutil.rmtree(backup)
                logging.info(f"Backup excedente eliminado: {backup}")
            except Exception as e:
                logging.error(f"Error eliminando backup excedente {backup}: {e}")


class GitManager:
    """Gestor de operaciones Git"""

    def __init__(self, config: URASyncConfig):
        self.config = config
        self.source_dir = config.get_source_dir()
        self.sync_method = config.get("sync_method", "git")
        self.git_remote = config.get("git_remote", "origin")
        self.git_branch = config.get("git_branch", "main")

    def is_git_repo(self) -> bool:
        """Verifica si el directorio es un repo Git"""
        return (self.source_dir / ".git").exists()

    def init_git(self) -> bool:
        """Inicializa repo Git si no existe"""
        if not self.is_git_repo():
            try:
                subprocess.run(["git", "init"], cwd=self.source_dir, check=True)
                logging.info("Repositorio Git inicializado")
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Error inicializando Git: {e}")
                return False
        return True

    def commit_changes(self, message: str) -> bool:
        """Realiza commit de cambios"""
        try:
            # Add all files
            subprocess.run(["git", "add", "."], cwd=self.source_dir, check=True)

            # Commit
            subprocess.run(["git", "commit", "-m", message], cwd=self.source_dir, check=True)
            logging.info(f"Commit realizado: {message}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error en commit: {e}")
            return False

    def push_to_remote(self) -> bool:
        """Push a remote"""
        try:
            subprocess.run(
                ["git", "push", self.git_remote, self.git_branch], cwd=self.source_dir, check=True
            )
            logging.info(f"Push realizado a {self.git_remote}/{self.git_branch}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error en push: {e}")
            return False


class MobileSyncManager:
    """Gestor de sincronización con móvil"""

    def __init__(self, config: URASyncConfig):
        self.config = config
        self.enabled = config.get("mobile_sync_enabled", False)
        self.mobile_host = config.get("mobile_host", "")
        self.mobile_path = config.get("mobile_path", "")

    def sync_to_mobile(self, source_dir: Path) -> bool:
        """Sincroniza con móvil usando rsync"""
        if not self.enabled or not self.mobile_host:
            logging.info("Sincronización móvil deshabilitada")
            return True

        try:
            cmd = [
                "rsync",
                "-av",
                "--delete",
                str(source_dir) + "/",
                f"{self.mobile_host}:{self.mobile_path}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logging.info("Sincronización con móvil completada")
                return True
            else:
                logging.error(f"Error sincronizando con móvil: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Error en sincronización móvil: {e}")
            return False

    def check_mobile_connection(self) -> bool:
        """Verifica si el móvil está conectado"""
        if not self.enabled or not self.mobile_host:
            return False

        try:
            result = subprocess.run(
                [
                    "ping",
                    "-c",
                    "1",
                    self.mobile_host.split("@")[1] if "@" in self.mobile_host else self.mobile_host,
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False


class OllamaValidator:
    """Validador de conexión Ollama"""

    @staticmethod
    def validate() -> bool:
        """Verifica que Ollama esté corriendo"""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Error verificando Ollama: {e}")
            return False


class NotificationManager:
    """Gestor de notificaciones visuales"""

    def __init__(self, config: URASyncConfig):
        self.config = config
        self.enabled = config.get("notifications", {}).get("enabled", True)
        self.show_dashboard = config.get("notifications", {}).get("show_dashboard", True)

    def notify(self, message: str, status: str = "info"):
        """Envía notificación visual"""
        if not self.enabled:
            return

        icon_map = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️", "sync": "🔄"}

        icon = icon_map.get(status, "ℹ️")
        full_message = f"{icon} {message}"

        logging.info(full_message)

        # Aquí se podría integrar con el dashboard de URA
        if self.show_dashboard:
            # TODO: Implementar integración con dashboard
            pass


class FileChangeHandler(FileSystemEventHandler):
    """Manejador de cambios de archivos para watchdog"""

    def __init__(self, sync_system: "URASyncSystem"):
        self.sync_system = sync_system
        self.last_change_time = 0
        self.debounce_seconds = sync_system.config.get("debounce_seconds", 120)

    def on_any_event(self, event):
        """Maneja cualquier evento de archivo"""
        if event.is_directory:
            return

        # Skip excluded patterns
        for pattern in self.sync_system.config.get("exclude_patterns", []):
            if pattern in event.src_path:
                return

        current_time = time.time()
        self.last_change_time = current_time
        logging.info(f"Cambio detectado: {event.src_path}")

        # Schedule sync after debounce
        self.sync_system.schedule_sync()


class URASyncSystem:
    """Sistema principal de sincronización automática"""

    def __init__(self, config_path: str):
        self.config = URASyncConfig(config_path)
        self.setup_logging()

        self.validator = PythonSyntaxValidator()
        self.backup_manager = BackupManager(self.config)
        self.git_manager = GitManager(self.config)
        self.mobile_sync = MobileSyncManager(self.config)
        self.ollama_validator = OllamaValidator()
        self.notifications = NotificationManager(self.config)

        self.observer = None
        self.sync_scheduled = False
        self.sync_timer = None

    def setup_logging(self):
        """Configura sistema de logging"""
        log_file = Path(self.config.get("log_file", "logs/auto_sync.log"))
        log_file.parent.mkdir(parents=True, exist_ok=True)

        max_size = self.config.get("max_log_size_mb", 10) * 1024 * 1024

        handler = RotatingFileHandler(log_file, maxBytes=max_size, backupCount=5)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[handler, logging.StreamHandler()],
        )

    def schedule_sync(self):
        """Programa sincronización después de debounce"""
        if self.sync_scheduled:
            return

        self.sync_scheduled = True
        debounce_seconds = self.config.get("debounce_seconds", 120)

        logging.info(f"Sincronización programada en {debounce_seconds} segundos...")
        self.notifications.notify("Sincronización programada...", "sync")

        # Schedule sync
        time.sleep(debounce_seconds)
        self.perform_sync()
        self.sync_scheduled = False

    def perform_sync(self, force: bool = False) -> bool:
        """Realiza sincronización completa"""
        source_dir = self.config.get_source_dir()

        self.notifications.notify("Iniciando sincronización...", "sync")

        # 1. Validate syntax if enabled
        if self.config.get("validate_syntax", True):
            self.notifications.notify("Validando sintaxis Python...", "info")
            if not self.validator.validate_directory(
                source_dir, self.config.get("exclude_patterns", [])
            ):
                self.notifications.notify(
                    "Error de sintaxis - backup creado pero no sincronizado", "error"
                )
                # Still create backup even if syntax error
                self.backup_manager.create_backup(source_dir)
                return False

        # 2. Validate Ollama if enabled
        if self.config.get("validate_ollama", True):
            if not self.ollama_validator.validate():
                self.notifications.notify(
                    "Ollama no disponible - sincronización pausada", "warning"
                )
                return False

        # 3. Create backup
        self.notifications.notify("Creando backup...", "info")
        backup_path = self.backup_manager.create_backup(source_dir)
        if not backup_path:
            self.notifications.notify("Error creando backup", "error")
            return False

        # 4. Git operations
        if self.config.get("sync_method") == "git":
            self.notifications.notify("Sincronizando con Git...", "info")

            if not self.git_manager.is_git_repo() and not self.git_manager.init_git():
                return False

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = self.config.get(
                "auto_commit_message", "Auto-sync: {timestamp} - Versión Estable"
            )
            commit_msg = commit_msg.format(timestamp=timestamp)

            if not self.git_manager.commit_changes(commit_msg):
                self.notifications.notify("Error en commit Git", "error")
                return False

            # Push if configured
            if self.config.get("git_remote") and not self.git_manager.push_to_remote():
                self.notifications.notify("Error en push Git", "warning")

        # 5. Mobile sync
        if self.mobile_sync.enabled:
            self.notifications.notify("Sincronizando con móvil...", "info")
            if not self.mobile_sync.check_mobile_connection():
                self.notifications.notify("Móvil no conectado", "warning")
            elif not self.mobile_sync.sync_to_mobile(source_dir):
                self.notifications.notify("Error sincronizando con móvil", "error")

        self.notifications.notify("Sincronización completada", "success")
        return True

    def start_auto_sync(self):
        """Inicia modo automático con watchdog"""
        if not WATCHDOG_AVAILABLE:
            logging.error("watchdog no disponible, modo auto no funciona")
            return False

        source_dir = self.config.get_source_dir()
        event_handler = FileChangeHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(source_dir), recursive=True)

        self.observer.start()
        logging.info(f"Modo auto iniciado monitoreando: {source_dir}")
        self.notifications.notify("Sistema de sincronización automática iniciado", "success")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()

        self.observer.join()
        return True


def main():
    parser = argparse.ArgumentParser(description="URA Auto Sync System")
    parser.add_argument(
        "--config", default="config/auto_sync_config.json", help="Ruta al archivo de configuración"
    )
    parser.add_argument("--force", action="store_true", help="Forzar sincronización inmediata")
    parser.add_argument("--auto", action="store_true", help="Iniciar modo automático")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin hacer cambios reales")

    args = parser.parse_args()

    # Resolve config path relative to script location
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / args.config

    try:
        sync_system = URASyncSystem(str(config_path))

        if args.auto:
            if not WATCHDOG_AVAILABLE:
                print("ERROR: watchdog no instalado. Instala con: pip install watchdog")
                sys.exit(1)
            sync_system.start_auto_sync()
        elif args.force:
            sync_system.perform_sync(force=True)
        else:
            print("URA Auto Sync System")
            print("Usa --auto para modo automático o --force para sincronización manual")
            print(f"Config: {config_path}")

    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
