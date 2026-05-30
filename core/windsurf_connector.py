#!/usr/bin/env python3
"""
URA Windsurf Connector
Conexión con Windsurf via MCP (Model Context Protocol)
"""

import json
import logging
import subprocess
import time
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


class WindsurfConnector:
    """Conector para Windsurf IDE"""

    def __init__(self):
        self.is_connected = False
        self.active_workspace = None
        self.windsurf_processes = []

    def detect_windsurf(self) -> bool:
        """Detectar si Windsurf está corriendo"""
        try:
            windsurf_processes = []

            # Buscar procesos relacionados con Windsurf/Cascade
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info["cmdline"] or [])
                    if any(
                        keyword in cmdline.lower() for keyword in ["windsurf", "cascade", "vscode"]
                    ):
                        windsurf_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            self.windsurf_processes = windsurf_processes

            if windsurf_processes:
                self.is_connected = True
                logger.info(f"Windsurf detectado: {len(windsurf_processes)} procesos")
                return True
            else:
                self.is_connected = False
                return False

        except Exception as e:
            logger.error(f"Error detectando Windsurf: {e}")
            self.is_connected = False
            return False

    def start_windsurf(self) -> bool:
        """Iniciar Windsurf"""
        try:
            # Intentar diferentes comandos para abrir Windsurf
            commands = [
                ["open", "-a", "Windsurf"],
                ["windsurf"],
                ["code", "--new-window"],  # VSCode como fallback
            ]

            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    time.sleep(3)  # Esperar a que inicie

                    if self.detect_windsurf():
                        logger.info(f"Windsurf iniciado con: {' '.join(cmd)}")
                        return True
                except FileNotFoundError:
                    continue

            logger.error("No se pudo iniciar Windsurf")
            return False

        except Exception as e:
            logger.error(f"Error iniciando Windsurf: {e}")
            return False

    def get_active_workspace(self) -> str | None:
        """Obtener el workspace activo de Windsurf"""
        try:
            # Intentar leer configuración de Windsurf/VSCode
            config_paths = [
                Path.home()
                / "Library"
                / "Application Support"
                / "Windsurf"
                / "User"
                / "workspaceStorage",
                Path.home() / ".vscode" / "workspaces",
            ]

            for config_path in config_paths:
                if config_path.exists():
                    # Buscar archivos de configuración que contengan rutas de workspace
                    for file_path in config_path.rglob("*.json"):
                        try:
                            with open(file_path) as f:
                                config = json.load(f)
                                # Buscar rutas de workspace en la configuración
                                if "workspace" in str(config).lower():
                                    # Extraer ruta del workspace (implementación básica)
                                    for _key, value in config.items():
                                        if isinstance(value, str) and (
                                            "/" in value or "\\" in value
                                        ):
                                            if Path(value).exists():
                                                self.active_workspace = value
                                                return value
                        except (json.JSONDecodeError, PermissionError):
                            continue

            # Si no se encuentra en configuración, intentar detectar por procesos
            for proc in self.windsurf_processes:
                cmdline = proc.get("cmdline", [])
                if cmdline:
                    for arg in cmdline:
                        if ("/" in arg or "\\" in arg) and Path(arg).exists():
                            if Path(arg).is_dir():
                                self.active_workspace = arg
                                return arg

            return None

        except Exception as e:
            logger.error(f"Error obteniendo workspace activo: {e}")
            return None

    def open_workspace(self, workspace_path: str) -> bool:
        """Abrir workspace en Windsurf"""
        try:
            workspace = Path(workspace_path)
            if not workspace.exists():
                logger.error(f"El workspace no existe: {workspace_path}")
                return False

            # Comandos para abrir workspace
            commands = [
                ["open", "-a", "Windsurf", workspace_path],
                ["windsurf", workspace_path],
                ["code", workspace_path],
            ]

            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    time.sleep(2)

                    if self.detect_windsurf():
                        self.active_workspace = workspace_path
                        logger.info(f"Workspace abierto: {workspace_path}")
                        return True
                except FileNotFoundError:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error abriendo workspace: {e}")
            return False

    def create_file(self, file_path: str, content: str = "") -> bool:
        """Crear archivo en el workspace activo"""
        try:
            if not self.active_workspace:
                logger.error("No hay workspace activo")
                return False

            full_path = Path(self.active_workspace) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Archivo creado: {full_path}")
            return True

        except Exception as e:
            logger.error(f"Error creando archivo: {e}")
            return False

    def read_file(self, file_path: str) -> str | None:
        """Leer archivo del workspace activo"""
        try:
            if not self.active_workspace:
                logger.error("No hay workspace activo")
                return None

            full_path = Path(self.active_workspace) / file_path

            if not full_path.exists():
                logger.error(f"Archivo no existe: {full_path}")
                return None

            with open(full_path, encoding="utf-8") as f:
                content = f.read()

            logger.info(f"Archivo leído: {full_path}")
            return content

        except Exception as e:
            logger.error(f"Error leyendo archivo: {e}")
            return None

    def list_files(self, directory: str = "") -> list[dict]:
        """Listar archivos del workspace"""
        try:
            if not self.active_workspace:
                logger.error("No hay workspace activo")
                return []

            base_path = Path(self.active_workspace)
            if directory:
                base_path = base_path / directory

            if not base_path.exists():
                logger.error(f"Directorio no existe: {base_path}")
                return []

            files = []
            for item in base_path.iterdir():
                try:
                    stat = item.stat()
                    files.append(
                        {
                            "name": item.name,
                            "path": str(item.relative_to(Path(self.active_workspace))),
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat.st_size if item.is_file() else 0,
                            "modified": stat.st_mtime,
                        }
                    )
                except (OSError, PermissionError):
                    continue

            files.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            return files

        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            return []

    def create_folder(self, folder_path: str) -> bool:
        """Crear carpeta en el workspace"""
        try:
            if not self.active_workspace:
                logger.error("No hay workspace activo")
                return False

            full_path = Path(self.active_workspace) / folder_path
            full_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Carpeta creada: {full_path}")
            return True

        except Exception as e:
            logger.error(f"Error creando carpeta: {e}")
            return False

    def execute_command(self, command: str, working_dir: str | None = None) -> dict:
        """Ejecutar comando en el contexto del workspace"""
        try:
            cwd = self.active_workspace
            if working_dir:
                cwd = Path(self.active_workspace) / working_dir

            if not cwd or not Path(cwd).exists():
                logger.error("Directorio de trabajo no válido")
                return {"success": False, "error": "Directorio no válido"}

            import shlex

            command_list = shlex.split(command)
            result = subprocess.run(
                command_list, cwd=cwd, capture_output=True, text=True, timeout=30
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.error("Timeout ejecutando comando")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Error ejecutando comando: {e}")
            return {"success": False, "error": str(e)}

    def get_project_structure(self) -> dict:
        """Obtener estructura completa del proyecto"""
        try:
            if not self.active_workspace:
                return {"error": "No hay workspace activo"}

            def build_tree(path: Path, max_depth: int = 3, current_depth: int = 0) -> dict:
                if current_depth >= max_depth:
                    return {"name": path.name, "type": "folder", "children": []}

                node = {
                    "name": path.name,
                    "type": "folder" if path.is_dir() else "file",
                    "path": str(path.relative_to(Path(self.active_workspace))),
                }

                if path.is_dir():
                    children = []
                    try:
                        for item in sorted(path.iterdir()):
                            if not item.name.startswith("."):
                                children.append(build_tree(item, max_depth, current_depth + 1))
                        node["children"] = children
                    except (OSError, PermissionError):
                        pass

                return node

            workspace_path = Path(self.active_workspace)
            return build_tree(workspace_path)

        except Exception as e:
            logger.error(f"Error obteniendo estructura: {e}")
            return {"error": str(e)}

    def search_in_files(self, pattern: str, file_pattern: str = "*") -> list[dict]:
        """Buscar patrón en archivos del workspace"""
        try:
            if not self.active_workspace:
                return []

            workspace_path = Path(self.active_workspace)
            results = []

            for file_path in workspace_path.rglob(file_pattern):
                if file_path.is_file() and not file_path.name.startswith("."):
                    try:
                        with open(file_path, encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern.lower() in line.lower():
                                    results.append(
                                        {
                                            "file": str(file_path.relative_to(workspace_path)),
                                            "line": line_num,
                                            "content": line.strip(),
                                            "match": pattern,
                                        }
                                    )
                    except (OSError, PermissionError, UnicodeDecodeError):
                        continue

            return results

        except Exception as e:
            logger.error(f"Error buscando en archivos: {e}")
            return []

    def health_check(self) -> dict:
        """Verificación completa de salud"""
        return {
            "connected": self.is_connected,
            "active_workspace": self.active_workspace,
            "processes": len(self.windsurf_processes),
            "workspace_exists": (
                Path(self.active_workspace).exists() if self.active_workspace else False
            ),
        }

    def send_message(self, message: str, timeout: int = 60) -> str | None:
        """
        Envía un mensaje a Cascade AI de Windsurf vía AppleScript.
        Si no es posible, devuelve None (no simula — es real o nada).
        """
        if not self.is_connected:
            self.detect_windsurf()
        if not self.is_connected:
            logger.warning("Windsurf no detectado — no se puede enviar mensaje")
            return None

        try:
            import pyautogui
            import os

            # Traer Windsurf al frente
            os.system("osascript -e 'tell application \"Windsurf\" to activate'")
            time.sleep(1)

            # Abrir Cascade (Cmd+L)
            pyautogui.hotkey("command", "l")
            time.sleep(1.5)

            # Escribir el mensaje
            pyautogui.write(message, interval=0.03)
            time.sleep(0.5)

            # Enviar (Enter)
            pyautogui.press("enter")
            time.sleep(min(timeout, 30))

            # Copiar respuesta (Cmd+A, Cmd+C en el panel de Cascade)
            pyautogui.hotkey("command", "a")
            time.sleep(0.3)
            pyautogui.hotkey("command", "c")
            time.sleep(0.3)

            import subprocess

            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            response = result.stdout.strip()

            if response and len(response) > 10:
                logger.info(f"Windsurf Cascade respondió ({len(response)} chars)")
                return response

        except Exception as e:
            logger.error(f"Error enviando a Cascade: {e}")

        return None


# Singleton global
windsurf_connector = WindsurfConnector()
