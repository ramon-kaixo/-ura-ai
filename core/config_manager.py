#!/usr/bin/env python3
"""
Config Manager — FASE 1.2
───────────────────────────
Configuración centralizada con validación Pydantic.
Carga desde settings.json, notifica cambios a suscriptores.
"""

import json
import os
import threading
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from core.logging_config import get_logger

logger = get_logger("config_manager", log_dir="./logs")


class OllamaConfig(BaseModel):
    url: str = "http://localhost:11434"
    remote_host: str = "localhost"
    remote_port: int = 11434
    default_model: str = "llama3.2:3b"
    vision_model: str = "llava:latest"
    max_retries: int = 3
    timeout: int = 60
    use_remote: bool = False

    def get_ollama_url(self) -> str:
        """
        Retorna URL de Ollama.
        Prioridad: OLLAMA_HOST env var → use_remote+remote_host → url local
        """
        env_host = os.environ.get("OLLAMA_HOST", "")
        if env_host:
            if "://" not in env_host:
                parts = env_host.split(":")
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else self.remote_port
                return f"http://{host}:{port}"
            return env_host
        if self.use_remote and self.remote_host:
            return f"http://{self.remote_host}:{self.remote_port}"
        return self.url


class DashboardConfig(BaseModel):
    port: int = 5051
    host: str = "0.0.0.0"
    auth_required: bool = True
    max_message_length: int = 4000


class ResearchConfig(BaseModel):
    enabled: bool = True
    models: list[str] = Field(default_factory=lambda: ["llama3.2:3b"])
    interval_seconds: int = 300
    max_idle_models: list[str] = Field(
        default_factory=lambda: ["llama3:latest", "qwen2.5:3b-instruct"]
    )
    idle_interval_seconds: int = 30
    save_path: str = "/Volumes/TOSHIBA_NUEVO/URA/biblioteca_conocimiento"


class SecurityConfig(BaseModel):
    token_file: str = "~/.ura/api_token"
    max_input_length: int = 4000
    jailbreak_detection: bool = True
    command_whitelist: bool = True


class MemoryConfig(BaseModel):
    max_history_entries: int = 200
    pruning_threshold: int = 100
    vector_cache_size: int = 1000


class URAConfig(BaseModel):
    """Configuración completa de URA."""

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    auto_update: bool = True
    debug: bool = False


DEFAULT_CONFIG = URAConfig()


class ConfigManager:
    """
    Gestor centralizado de configuración.

    Uso:
        cm = ConfigManager()
        cm.load()
        print(cm.config.ollama.default_model)
        cm.subscribe("ollama", callback)
    """

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "settings.json"
        self.config: URAConfig = DEFAULT_CONFIG
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable]] = {}

    def load(self) -> URAConfig:
        """Carga configuración desde archivo JSON."""
        if not self.config_path.exists():
            logger.warning(f"Config no encontrada: {self.config_path}. Usando defaults.")
            self._save()
            return self.config

        try:
            with open(self.config_path) as f:
                data = json.load(f)
            with self._lock:
                self.config = URAConfig(**data)
            logger.info(f"Config cargada: {self.config_path}")
        except Exception as e:
            logger.error(f"Error cargando config: {e}. Usando defaults.")
            self.config = DEFAULT_CONFIG
            self._save()

        return self.config

    def save(self):
        """Guarda la configuración actual al archivo."""
        self._save()

    def _save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                f.write(self.config.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Error guardando config: {e}")

    def update(self, section: str, values: dict):
        """Actualiza una sección de la configuración."""
        with self._lock:
            if hasattr(self.config, section):
                current = getattr(self.config, section)
                for key, val in values.items():
                    if hasattr(current, key):
                        setattr(current, key, val)
                self._save()
                self._notify(section)

    def get(self, path: str):
        """Obtiene un valor por ruta (ej: 'ollama.default_model')."""
        parts = path.split(".")
        current = self.config
        for part in parts:
            current = getattr(current, part, None)
            if current is None:
                return None
        return current

    def subscribe(self, section: str, callback: Callable):
        """Suscribe un callback a cambios en una sección."""
        if section not in self._subscribers:
            self._subscribers[section] = []
        self._subscribers[section].append(callback)

    def _notify(self, section: str):
        for cb in self._subscribers.get(section, []):
            try:
                cb(section, getattr(self.config, section, None))
            except Exception as e:
                logger.error(f"Error en subscriber de {section}: {e}")


# ── Singleton ──────────────────────────────────────────────

_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    global _manager
    if _manager is None:
        _manager = ConfigManager()
        _manager.load()
    return _manager
