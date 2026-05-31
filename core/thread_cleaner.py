#!/usr/bin/env python3
"""
URA - Limpiador Automático de Hilos Zombis

Sistema para:
- Detectar hilos/procesos zombies
- Limpiar procesos colgados automáticamente
- Ejecutar limpieza post-acción
- Mantener lista blanca de procesos protegidos
- Limpiar procesos de red no autorizados
- Integrar hilos de mensajería
"""

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración (opcional, si no existe usa defaults)
CONFIG_PATH = Path(__file__).parent.parent / "config" / "thread_cleaner.json"

# Importar sistema de auditoría de red
try:
    from core.network_audit import NetworkAuditSystem

    NETWORK_AUDIT_AVAILABLE = True
except ImportError:
    NETWORK_AUDIT_AVAILABLE = False
    logger.warning("Sistema de auditoría de red no disponible")


@dataclass
class ProcessInfo:
    """Información sobre un proceso"""

    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    create_time: float
    command: str
    is_zombie: bool


@dataclass
class CleanAction:
    """Información sobre una acción de limpieza"""

    pid: int
    name: str
    action: str
    timestamp: str
    reason: str


class ThreadCleaner:
    """Limpiador de hilos zombies completo con arquitectura KILL_ALLOWED vs REPORT_ONLY"""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.clean_log: list[CleanAction] = []
        self.network_audit = (
            NetworkAuditSystem(use_localhost=True) if NETWORK_AUDIT_AVAILABLE else None
        )
        self.messaging_threads: list[dict[str, Any]] = []  # Hilos de mensajería activos
        self.app_threads: list[dict[str, Any]] = []  # Todos los threads de la aplicación

        # Nuevas rutas de configuración
        self.ura_processes_file = Path(__file__).parent.parent / "config" / "ura_processes.json"
        self.stats_file = Path(__file__).parent.parent / "config" / "thread_cleaner_stats.json"

        # Cargar configuración de procesos URA
        self.ura_processes = self._load_ura_processes()

        # Cargar estadísticas diarias
        self.stats = self._load_stats()

    def _load_config(self) -> Any:
        """Cargar configuración desde archivo"""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando configuración: {e}")
            return self._default_config()

    def _load_ura_processes(self) -> Any:
        """Cargar configuración de procesos URA"""
        try:
            with open(self.ura_processes_file) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de procesos URA no encontrado: {self.ura_processes_file}")
            return self._default_ura_processes()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando procesos URA: {e}")
            return self._default_ura_processes()

    def _default_ura_processes(self) -> dict[str, Any]:
        """Configuración por defecto de procesos URA"""
        return {
            "kill_allowed": {
                "process_names": ["python3", "python", "ura_app", "main_final"],
                "description": "Procesos propios de URA que pueden ser terminados si son zombies",
            },
            "report_only": {
                "process_patterns": ["docker", "postgres", "redis", "nginx", "apache", "mysql"],
                "description": "Procesos externos que solo se reportan, nunca se matan",
            },
            "protected_pids": [1],
            "protected_processes": [
                "kernel_task",
                "launchd",
                "WindowServer",
                "loginwindow",
                "Dock",
                "SystemUIServer",
                "ollama",
            ],
            "docker_processes": [
                "com.docker.backend",
                "com.docker.cli",
                "containerd",
                "dockerd",
                "docker-proxy",
            ],
        }

    def _load_stats(self) -> Any:
        """Cargar estadísticas diarias"""
        try:
            with open(self.stats_file) as f:
                stats = json.load(f)
                # Verificar si es el mismo día
                today = datetime.now().strftime("%Y-%m-%d")
                if stats.get("date") != today:
                    # Resetear si es un día nuevo
                    stats = {
                        "date": today,
                        "processes_killed_today": 0,
                        "processes_reported_today": 0,
                        "kill_attempts_failed": 0,
                        "last_reset": datetime.now().isoformat(),
                        "history": [],
                    }
                    # Guardar directamente sin usar self.stats (que aún no está inicializado)
                    try:
                        with open(self.stats_file, "w") as f:
                            json.dump(stats, f, indent=2)
                    except Exception as e:
                        logger.error(f"Error guardando estadísticas reseteadas: {e}")
                return stats
        except FileNotFoundError:
            logger.warning(f"Archivo de estadísticas no encontrado: {self.stats_file}")
            return self._default_stats()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando estadísticas: {e}")
            return self._default_stats()

    def _default_stats(self) -> dict[str, Any]:
        """Estadísticas por defecto"""
        stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "processes_killed_today": 0,
            "processes_reported_today": 0,
            "kill_attempts_failed": 0,
            "last_reset": datetime.now().isoformat(),
            "history": [],
        }
        # Guardar directamente sin usar self.stats (que aún no está inicializado)
        try:
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estadísticas por defecto: {e}")
        return stats

    def _save_stats(self, stats: dict[str, Any] | None = None) -> bool:
        """Guardar estadísticas en archivo"""
        try:
            stats_to_save = stats or self.stats
            with open(self.stats_file, "w") as f:
                json.dump(stats_to_save, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando estadísticas: {e}")
            return False

    def _default_config(self) -> dict[str, Any]:
        """Configuración por defecto"""
        return {
            "version": "1.0",
            "whitelist": {
                "processes": [
                    "python",
                    "python3",
                    "ollama",
                    "redis-server",
                    "code",
                    "Windsurf",
                    "QuickBooks",
                ],
                "pids": [],
            },
            "zombie_detection": {
                "enabled": True,
                "idle_threshold_minutes": 30,
                "cpu_threshold": 0.1,
                "memory_threshold": 0.5,
            },
            "auto_clean": {"enabled": True, "safe_mode": True, "confirm_before_kill": False},
        }

    def _save_config(self) -> bool:
        """Guardar configuración en archivo"""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

    def _is_process_protected(self, pid: int, name: str) -> tuple[bool, str]:
        """Verificar si un proceso está protegido (NUNCA MATAR)"""
        # Verificar PID protegido
        if pid in self.ura_processes["protected_pids"]:
            return True, f"PID {pid} está en lista de PIDs protegidos"

        # Verificar nombre de proceso protegido
        if name in self.ura_processes["protected_processes"]:
            return True, f"Proceso {name} está en lista de procesos protegidos"

        # Verificar procesos Docker
        if any(
            docker_proc in name.lower() for docker_proc in self.ura_processes["docker_processes"]
        ):
            return True, f"Proceso {name} es un proceso Docker protegido"

        return False, ""

    def _is_ura_process(self, pid: int, name: str) -> bool:
        """Verificar si es un proceso propio de URA (KILL_ALLOWED)"""
        try:
            process = psutil.Process(pid)

            # Verificar por nombre
            if name in self.ura_processes["kill_allowed"]["process_names"]:
                return True

            # Verificar parent process usando psutil
            try:
                parent = process.parent()
                if parent:
                    parent_name = parent.name()
                    if parent_name in self.ura_processes["kill_allowed"]["process_names"]:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _is_external_process(self, name: str) -> bool:
        """Verificar si es un proceso externo (REPORT_ONLY)"""
        return any(
            pattern in name.lower()
            for pattern in self.ura_processes["report_only"]["process_patterns"]
        )

    def _log_kill_attempt_failed(self, pid: int, name: str, reason: str):
        """Registrar intento de kill fallido"""
        self.stats["kill_attempts_failed"] += 1
        self.stats["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "pid": pid,
                "name": name,
                "action": "kill_attempt_failed",
                "reason": reason,
            }
        )
        self._save_stats()
        logger.error(f"❌ INTENTO DE KILL FALLIDO: {name} (PID: {pid}) - {reason}")

    def is_process_whitelisted(self, pid: int, name: str) -> bool:
        """Verificar si el proceso está en la lista blanca"""
        # Verificar por nombre
        if name in self.config["whitelist"]["processes"]:
            return True

        # Verificar por PID
        return pid in self.config["whitelist"]["pids"]

    def is_zombie_process(self, process: psutil.Process) -> bool:
        """Determinar si un proceso es zombie"""
        try:
            # Verificar estado
            if process.status() == psutil.STATUS_ZOMBIE:
                return True

            # Verificar si está inactivo por mucho tiempo
            idle_threshold = self.config["zombie_detection"]["idle_threshold_minutes"]
            if idle_threshold > 0:
                create_time = datetime.fromtimestamp(process.create_time())
                if datetime.now() - create_time > timedelta(minutes=idle_threshold):
                    # Verificar uso de CPU y memoria
                    cpu_percent = process.cpu_percent(interval=0.1)
                    memory_percent = process.memory_percent()

                    cpu_threshold = self.config["zombie_detection"]["cpu_threshold"]
                    memory_threshold = self.config["zombie_detection"]["memory_threshold"]

                    if cpu_percent < cpu_threshold and memory_percent < memory_threshold:
                        return True

            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def get_zombie_processes(self) -> list[ProcessInfo]:
        """Obtener lista de procesos zombies"""
        zombies = []

        for proc in psutil.process_iter(
            ["pid", "name", "status", "cpu_percent", "memory_percent", "create_time", "cmdline"]
        ):
            try:
                if not self.is_process_whitelisted(proc.info["pid"], proc.info["name"]):
                    if self.is_zombie_process(proc):
                        zombies.append(
                            ProcessInfo(
                                pid=proc.info["pid"],
                                name=proc.info["name"],
                                status=proc.info["status"],
                                cpu_percent=proc.info["cpu_percent"] or 0.0,
                                memory_percent=proc.info["memory_percent"] or 0.0,
                                create_time=proc.info["create_time"] or 0.0,
                                command=(
                                    " ".join(proc.info["cmdline"]) if proc.info["cmdline"] else ""
                                ),
                                is_zombie=True,
                            )
                        )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return zombies


def clean_process(self, pid: int, force: bool = False) -> bool:
    """Limpiar un proceso específico con arquitectura KILL_ALLOWED vs REPORT_ONLY"""
    try:
        process = psutil.Process(pid)
        name = process.name()

        if is_protected_process(pid, name):
            logger.warning(
                f"🛡️ PROTEGIDO: {name} (PID: {pid}) - {protection_reason} - NO SE ELIMINA"
            )
            self._log_kill_attempt_failed(pid, name, protection_reason)
            return False

        if is_whitelisted_process(pid, name):
            logger.warning(f"⚠️ WHITELIST: {name} (PID: {pid}) está en lista blanca - NO SE ELIMINA")
            self._log_kill_attempt_failed(pid, name, "whitelisted")
            return False

        if is_external_process(name):
            logger.warning(
                f"📋 REPORT_ONLY: {name} (PID: {pid}) es proceso externo - SOLO SE REPORTA, NO SE ELIMINA"
            )
            self.stats["processes_reported_today"] += 1
            self.stats["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "pid": pid,
                    "name": name,
                    "action": "reported",
                    "reason": "external process (report_only)",
                }
            )
            self._save_stats()
            return False

        if not is_ura_process(pid, name):
            logger.warning(f"⚠️ NO URA: {name} (PID: {pid}) no es proceso URA - NO SE ELIMINA")
            self._log_kill_attempt_failed(pid, name, "not a URA process")
            return False

        if self.config["auto_clean"]["safe_mode"]:
            logger.warning(
                f"🔒 SAFE_MODE: {name} (PID: {pid}) - Modo seguro activado, NO SE ELIMINA"
            )
            self._log_kill_attempt_failed(pid, name, "safe_mode")
            return False

        logger.info(f"🔨 KILL_ALLOWED: {name} (PID: {pid}) - Eliminando proceso URA...")

        process.terminate()
        try:
            process.wait(timeout=5)
            logger.info(f"✅ ELIMINADO: {name} (PID: {pid}) - Terminado correctamente")
        except psutil.TimeoutExpired:
            process.kill()
            logger.warning(f"⚡ FORCE_KILL: {name} (PID: {pid}) - Forzado con kill")

        self.stats["processes_killed_today"] += 1
        self.stats["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "pid": pid,
                "name": name,
                "action": "killed",
                "reason": "URA zombie process",
            }
        )
        self._save_stats()

        clean_action = CleanAction(
            pid=pid,
            name=name,
            action="killed",
            timestamp=datetime.now().isoformat(),
            reason="URA zombie process eliminated",
        )
        self.clean_log.append(clean_action)

        return True

    except psutil.NoSuchProcess:
        logger.warning(f"Proceso {pid} no existe")
        return False
    except psutil.AccessDenied:
        logger.error(f"Acceso denegado al proceso {pid}")
        self._log_kill_attempt_failed(pid, "unknown", "access_denied")
        return False
    except Exception as e:
        logger.error(f"Error eliminando proceso {pid}: {e}")
        self._log_kill_attempt_failed(pid, "unknown", str(e))
        return False


def is_protected_process(pid: int, name: str) -> bool:
    """Verificar si el proceso está protegido"""
    is_protected, protection_reason = _is_process_protected(pid, name)
    return is_protected


def is_whitelisted_process(pid: int, name: str) -> bool:
    """Verificar si el proceso está en la lista blanca"""
    return not force and is_process_whitelisted(pid, name)


def is_external_process(name: str) -> bool:
    """Verificar si el proceso es externo (REPORT_ONLY)"""
    return _is_external_process(name)


def is_ura_process(pid: int, name: str) -> bool:
    """Verificar si el proceso es URA (KILL_ALLOWED)"""
    return not force and _is_ura_process(pid, name)


def _is_ura_process(pid: int, name: str) -> bool:
    # Implementación detallada de la lógica para verificar si el proceso es URA
    pass


def clean_all_zombies(self, force: bool = False) -> int:
    """Limpiar todos los procesos zombies"""
    zombies = self.get_zombie_processes()
    cleaned_count = 0

    for zombie in zombies:
        if self.clean_process(zombie.pid, force=force):
            cleaned_count += 1

    logger.info(f"Limpiados {cleaned_count} de {len(zombies)} procesos zombies")
    return cleaned_count


def post_action_clean(self, action_name: str) -> int:
    """Limpieza automática post-acción"""
    logger.info(f"Ejecutando limpieza post-acción: {action_name}")

    # Limpiar zombies
    cleaned_count = self.clean_all_zombies(force=False)

    # Limpieza de procesos específicos según la acción
    if action_name.lower() == "quickbooks":
        _clean_quickbooks_processes(self)
    elif action_name.lower() == "email":
        _clean_email_processes(self)
    elif action_name.lower() == "banco":
        _clean_bank_processes(self)

    logger.info(f"Limpieza post-acción completada: {action_name}")
    return cleaned_count


def _clean_quickbooks_processes(self):
    """Limpiar procesos específicos de QuickBooks"""
    try:
        # Buscar procesos relacionados con QuickBooks que no sean el principal
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = proc.info["name"].lower()
                if "quickbooks" in name and not self.is_process_whitelisted(
                    proc.info["pid"], proc.info["name"]
                ):
                    # Solo eliminar si es un proceso auxiliar
                    cmdline = " ".join(proc.info["cmdline"]) if proc.info["cmdline"] else ""
                    if "helper" in cmdline.lower() or "background" in cmdline.lower():
                        self.clean_process(proc.info["pid"], force=False)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error limpiando procesos QuickBooks: {e}")


def _clean_email_processes(self):
    """Limpiar procesos específicos de email"""
    try:
        email_clients = ["mail", "thunderbird", "outlook", "apple mail"]
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info["name"].lower()
                if any(client in name for client in email_clients):
                    if not self.is_process_whitelisted(proc.info["pid"], proc.info["name"]):
                        self.clean_process(proc.info["pid"], force=False)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error limpiando procesos email: {e}")


def _clean_bank_processes(self):
    """Limpiar procesos específicos de banco"""
    try:
        # Limpiar procesos de navegadores que puedan estar relacionados con banca
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info["name"].lower()
                if "chrome" in name or "firefox" in name or "safari" in name:
                    if not self.is_process_whitelisted(proc.info["pid"], proc.info["name"]):
                        # Solo eliminar si hay múltiples instancias
                        count = sum(
                            1
                            for p in psutil.process_iter(["name"])
                            if p.info["name"].lower() == name
                        )
                        if count > 1:
                            self.clean_process(proc.info["pid"], force=False)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error limpiando procesos banco: {e}")


def main():
    """Punto de entrada CLI"""
    parser = argparse.ArgumentParser(description="URA - Limpiador de Hilos Zombis")
    parser.add_argument("--list", action="store_true", help="Listar hilos zombies")
    parser.add_argument("--clean", action="store_true", help="Limpiar hilos zombies")
    parser.add_argument(
        "--force", action="store_true", help="Forzar limpieza (ignorar lista blanca)"
    )
    parser.add_argument("--post-action", type=str, metavar="ACTION", help="Limpieza post-acción")
    parser.add_argument("--whitelist-add", type=str, metavar="NAME", help="Añadir a lista blanca")
    parser.add_argument("--verbose", action="store_true", help="Modo verbose")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    cleaner = ThreadCleaner()

    if args.list:
        zombies = cleaner.list_zombies()
        print(f"\n=== HILOS ZOMBIES ({len(zombies)}) ===")
        for zombie in zombies:
            print(f"PID: {zombie.pid} - {zombie.name}")
            print(f"  CPU: {zombie.cpu_percent}% | Mem: {zombie.memory_percent}%")
            print(f"  Status: {zombie.status}")
            print(f"  Command: {zombie.command[:100]}")
            print()

    elif args.clean:
        cleaned = cleaner.clean_all_zombies(force=args.force)
        print(f"✅ Limpiados {cleaned} procesos zombies")

    elif args.post_action:
        cleaned = cleaner.post_action_clean(args.post_action)
        print(f"✅ Limpieza post-acción completada: {args.post_action} ({cleaned} procesos)")

    elif args.whitelist_add:
        success = cleaner.add_to_whitelist(name=args.whitelist_add)
        if success:
            print(f"✅ {args.whitelist_add} añadido a lista blanca")
        else:
            print("❌ Error añadiendo a lista blanca")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
