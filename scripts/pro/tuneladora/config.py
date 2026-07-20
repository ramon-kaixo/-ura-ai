"""Configuration — fuente única de configuración para el pipeline."""

from __future__ import annotations

import os
from pathlib import Path


class Configuration:
    """Configuración centralizada del sistema de tuneladoras.

    Todos los pipelines comparten esta misma configuración.
    Las diferencias entre mantenimiento y mejora se expresan
    vía parámetros, no vía configuraciones distintas.
    """

    def __init__(self) -> None:
        self.ura_root: Path = Path(os.environ.get("URA_ROOT", Path.home() / "URA" / "ura_ia_1972"))
        self.log_dir: Path = Path(os.environ.get("TUNEL_LOG_DIR", str(self.ura_root / "logs")))
        self.nervioso: Path = self.ura_root / ".nervioso"
        self.venv_python: str = str(self.ura_root / ".venv" / "bin" / "python3")
        self.ruff: str = str(self.ura_root / ".venv" / "bin" / "ruff")

        # Ollama
        self.ollama_host: str = os.environ.get("URA_OLLAMA_HOST", "localhost")
        self.ollama_port: str = os.environ.get("URA_OLLAMA_PORT", "11434")
        self.ollama_url: str = f"http://{self.ollama_host}:{self.ollama_port}"

        # Qdrant
        self.qdrant_host: str = os.environ.get("URA_QDRANT_HOST", "localhost")
        self.qdrant_port: str = os.environ.get("URA_QDRANT_PORT", "6333")

        # Timeouts por defecto (en segundos)
        self.timeout_ruff: int = int(os.environ.get("TUNEL_TIMEOUT_RUFF", "300"))
        self.timeout_worker: int = int(os.environ.get("TUNEL_TIMEOUT_WORKER", "3600"))
        self.timeout_script: int = int(os.environ.get("TUNEL_TIMEOUT_SCRIPT", "120"))
        self.timeout_snapshot: int = int(os.environ.get("TUNEL_TIMEOUT_SNAPSHOT", "60"))

    @property
    def log_file(self) -> Path:
        return self.log_dir / "tuneladora.log"

    @property
    def sistema_map(self) -> Path:
        return self.nervioso / "sistema_map.json"

    @property
    def delta_snapshot_file(self) -> Path:
        return self.nervioso / "delta_snapshots" / "ultimo_ciclo.json"
