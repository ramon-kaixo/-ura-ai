"""Configuración centralizada del motor URA.

Fuente única de verdad: config_manager.CONFIG (system_config.json).
Legacy config (/etc/ura/config.json, URA_CONFIG) ELIMINADO v6.0.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("ura.config")

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Defaults eliminados - se usan los de system_config.json
DEFAULT_OLLAMA_HOST = "localhost"
DEFAULT_OLLAMA_PORT = 11434
DEFAULT_OLLAMA_MODEL = "llama3:latest"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_TIMEOUT = 120
DEFAULT_OLLAMA_TEMPERATURE = 0.3
DEFAULT_OLLAMA_MAX_TOKENS = 1024
DEFAULT_LLM_PROVIDER = "ollama"


def _apply_config_overrides(c: "UraConfig") -> None:
    """Aplica configuración desde CONFIG (system_config.json). Fuente principal."""
    _cfg = _load_config_dict()
    if not _cfg:
        return
    paths = _cfg.get("paths")
    if isinstance(paths, dict):
        data = paths.get("data")
        if isinstance(data, str):
            c.data_dir = data
    log_level = _cfg.get("log_level")
    if isinstance(log_level, str):
        c.log_level = log_level
    ollama = _cfg.get("ollama")
    if isinstance(ollama, dict):
        host = ollama.get("host")
        if isinstance(host, str) and host:
            c.ollama_host = host
        port = ollama.get("port")
        if port:
            c.ollama_port = int(port)
    llm = _cfg.get("llm")
    if isinstance(llm, dict):
        modelo = llm.get("model")
        if isinstance(modelo, str):
            c.ollama_model = modelo
        emb = llm.get("embedding_model")
        if isinstance(emb, str):
            c.ollama_embedding_model = emb
        timeout = llm.get("timeout")
        if timeout:
            c.ollama_timeout = int(timeout)
        temperatura = llm.get("temperature")
        if temperatura:
            c.ollama_temperature = float(temperatura)
        max_tokens = llm.get("max_tokens")
        if max_tokens:
            c.ollama_max_tokens = int(max_tokens)
        provider = llm.get("provider")
        if isinstance(provider, str):
            c.llm_provider = provider


def _apply_env_overrides(c: "UraConfig") -> None:
    """Sobrescribe campos desde env vars (máxima prioridad)."""
    c.qdrant_host = os.environ.get("URA_QDRANT_HOST", c.qdrant_host)
    c.qdrant_port = int(os.environ.get("URA_QDRANT_PORT", str(c.qdrant_port)))
    c.timer_interval_min = int(os.environ.get("URA_TIMER_INTERVAL_MIN", str(c.timer_interval_min)))
    c.log_level = os.environ.get("URA_LOG_LEVEL", c.log_level)
    if c.log_level.upper() not in VALID_LOG_LEVELS:
        c.log_level = "INFO"
    else:
        c.log_level = c.log_level.upper()
    c.ollama_host = os.environ.get("URA_OLLAMA_HOST", c.ollama_host)
    c.ollama_port = int(os.environ.get("URA_OLLAMA_PORT", str(c.ollama_port)))
    c.ollama_model = os.environ.get("URA_OLLAMA_MODEL", c.ollama_model)
    c.ollama_embedding_model = os.environ.get("URA_OLLAMA_EMBEDDING_MODEL", c.ollama_embedding_model)
    c.ollama_timeout = int(os.environ.get("URA_OLLAMA_TIMEOUT", str(c.ollama_timeout)))
    c.ollama_temperature = float(os.environ.get("URA_OLLAMA_TEMPERATURE", str(c.ollama_temperature)))
    c.ollama_max_tokens = int(os.environ.get("URA_OLLAMA_MAX_TOKENS", str(c.ollama_max_tokens)))
    c.llm_provider = os.environ.get("URA_LLM_PROVIDER", c.llm_provider)


def _load_config_dict() -> dict[str, object] | None:
    """Carga CONFIG desde config_manager."""
    try:
        from motor.core.config_manager import CONFIG
        return CONFIG
    except Exception:
        return None


RUTAS_CONFIG_OPENCODE = [
    "/etc/opencode/opencode.json",
    "/etc/opencode/opencode.jsonc",
    "/home/ramon/URA/ura_ia_1972/opencode.json",
    "/home/ramon/URA/ura_ia_1972/opencode.jsonc",
]


@dataclass
class UraConfig:
    """Configuración centralizada del motor URA.

    Fuente única de verdad: motor.core.config_manager.CONFIG (system_config.json).
    Env vars (URA_*) tienen máxima prioridad.
    Legacy config (/etc/ura/config.json, URA_CONFIG) ELIMINADO v6.0.
    """

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    deploy_dir: str = "/opt/motor/deploy"
    data_dir: str = ""
    log_level: str = "INFO"
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    ollama_model: str = "llama3:latest"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout: int = 120
    ollama_temperature: float = 0.3
    ollama_max_tokens: int = 1024
    llm_provider: str = "ollama"
    is_vm: bool = True
    asus_host: str = "100.72.103.12"
    asus_port: int = 4198
    tailscale_iface: str = "tailscale0"
    timer_interval_min: int = 5
    failure_knowledge_path: str = ""
    baseline_path: str = ""
    auto_verify: bool = False
    schema_version: int = 301  # v3.1

    def __post_init__(self) -> None:
        """Completa rutas relativas al directorio base del proyecto."""
        base = Path(__file__).parent.parent
        if not self.data_dir:
            self.data_dir = str(base / "data")
        if not self.failure_knowledge_path:
            self.failure_knowledge_path = str(base / "data" / "failure_knowledge_inicial.json")
        if not self.baseline_path:
            self.baseline_path = str(base / "data" / "baseline_inicial.json")
        if self.log_level.upper() not in VALID_LOG_LEVELS:
            log.warning("log_level inválido '%s', usando INFO", self.log_level)
            self.log_level = "INFO"
        else:
            self.log_level = self.log_level.upper()

    @classmethod
    def load(cls) -> "UraConfig":
        """Carga configuración desde CONFIG (system_config.json) + env vars.

        Legacy config (/etc/ura/config.json, URA_CONFIG) ELIMINADO v6.0.
        """
        c = cls()
        _apply_config_overrides(c)
        _apply_env_overrides(c)
        return c
