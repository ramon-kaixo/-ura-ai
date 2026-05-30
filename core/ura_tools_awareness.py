#!/usr/bin/env python3
"""
Conciencia de Herramientas Disponibles de URA - Nivel 22

URA tiene conocimiento de todas las herramientas disponibles:
- Herramientas de línea de comandos
- Librerías Python instaladas
- APIs y servicios disponibles
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from core.ura_config import config
from core.ura_monitoring import get_ura_monitoring

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

TOOLS_AWARENESS_PATH = Path.home() / ".ura" / "tools_awareness.json"
TOOLS_AWARENESS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ToolsInfo:
    """Información de herramientas disponibles."""

    scan_time: str
    command_line_tools: list[str]
    python_libraries: list[str]
    python_version: str
    available_apis: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ToolsInfo":
        return cls(**data)


class URAToolsAwareness:
    """Gestor de conciencia de herramientas de URA."""

    def __init__(self):
        self.tools_info = self._load_tools_info()

    def _load_tools_info(self) -> ToolsInfo:
        """Cargar información de herramientas desde disco."""
        if TOOLS_AWARENESS_PATH.exists():
            try:
                with open(TOOLS_AWARENESS_PATH) as f:
                    data = json.load(f)
                    return ToolsInfo.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando información de herramientas: {e}")

        return self._scan_tools()

    def _scan_tools(self) -> ToolsInfo:
        """Escanear herramientas disponibles con límites de performance."""
        import time

        start = time.time()

        try:
            tools_config = config.get_tools_config()
            timeout = tools_config["timeout"]

            # Escanear herramientas de línea de comandos
            command_line_tools = []
            for tool in ["git", "docker", "npm", "pip", "python3", "node"]:
                try:
                    result = subprocess.run(
                        ["which", tool], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        command_line_tools.append(tool)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                except Exception as e:
                    logger.warning(f"Error verificando {tool}: {e}")

            # Escanear librerías Python
            python_libraries = []
            try:
                result = subprocess.run(
                    ["pip3", "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if result.returncode == 0:
                    import json as json_lib

                    packages = json_lib.loads(result.stdout)
                    python_libraries = [
                        p["name"] for p in packages[: tools_config["max_libraries"]]
                    ]
            except Exception as e:
                logger.warning(f"Error escaneando librerías Python: {e}")
                monitor.log_error("tools_awareness", "PipScanError", str(e))

            # Versión de Python
            python_version = (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )

            # APIs disponibles (simulado)
            available_apis = ["filesystem", "network", "process", "system"]

            duration = time.time() - start
            monitor.log_performance("tools_awareness", "scan_tools", duration)

            return ToolsInfo(
                scan_time=datetime.now().isoformat(),
                command_line_tools=command_line_tools,
                python_libraries=python_libraries,
                python_version=python_version,
                available_apis=available_apis,
            )
        except Exception as e:
            monitor.log_error("tools_awareness", "ScanError", str(e))
            raise

    def _save_tools_info(self):
        """Guardar información de herramientas a disco."""
        with open(TOOLS_AWARENESS_PATH, "w") as f:
            json.dump(self.tools_info.to_dict(), f, indent=2)

    def refresh_tools_info(self):
        """Actualizar información de herramientas."""
        self.tools_info = self._scan_tools()
        self._save_tools_info()

    def get_tools_context(self) -> str:
        """Genera contexto de herramientas para el system prompt."""
        context_parts = ["CONCIENCIA DE HERRAMIENTAS DISPONIBLES:"]
        context_parts.append(
            f"- Herramientas de línea de comandos: {', '.join(self.tools_info.command_line_tools[:5])}"
        )
        context_parts.append(
            f"- Librerías Python: {len(self.tools_info.python_libraries)} instaladas"
        )
        context_parts.append(f"- Versión de Python: {self.tools_info.python_version}")
        context_parts.append(f"- APIs disponibles: {', '.join(self.tools_info.available_apis)}")

        return "\n".join(context_parts) + "\n"

    def get_available_libraries(self) -> list[str]:
        """Obtener librerías Python disponibles."""
        return self.tools_info.python_libraries

    def check_library_available(self, library_name: str) -> bool:
        """Verificar si una librería está disponible."""
        try:
            __import__(library_name)
            return True
        except ImportError:
            return False


# Singleton
_ura_tools_awareness: URAToolsAwareness | None = None


def get_ura_tools_awareness() -> URAToolsAwareness:
    """Obtener el singleton de conciencia de herramientas de URA."""
    global _ura_tools_awareness
    if _ura_tools_awareness is None:
        _ura_tools_awareness = URAToolsAwareness()
    return _ura_tools_awareness


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tools = get_ura_tools_awareness()

    print("Conciencia de herramientas disponibles creada")
    print(tools.get_tools_context())
