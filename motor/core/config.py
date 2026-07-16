import json
import logging
import os
import warnings
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("ura.config")

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

RUTA_CONFIG_DEFECTO = "/etc/ura/config.json"
RUTA_DEPLOY_DEFECTO = "/home/ramon/URA/ura_ia_1972/deploy"
HOST_ASUS_DEFECTO = "100.72.103.12"
PUERTO_ASUS_DEFECTO = 4198
INTERFAZ_TAILSCALE_DEFECTO = "tailscale0"
def _apply_legacy_config(c: "UraConfig", path: str = "") -> None:
    """Aplica configuración desde JSON legacy (path arg, URA_CONFIG, /etc/ura/config.json).
    Es la fuente de menor prioridad — CONFIG y env vars sobrescriben después.
    """
    sources = [p for p in [path, os.environ.get("URA_CONFIG", ""), RUTA_CONFIG_DEFECTO] if p]
    if path or os.environ.get("URA_CONFIG"):
        warnings.warn(
            "UraConfig.load(path=...) y URA_CONFIG están DEPRECATED. "
            "Use system_config.json vía config_manager.",
            FutureWarning,
            stacklevel=3,
        )
    for p in sources:
        if p and Path(p).exists():
            try:
                d = json.loads(Path(p).read_text())
                for k, v in d.items():
                    if hasattr(c, k):
                        setattr(c, k, v)
                log.info("config legacy cargada desde %s", p)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("error al cargar config %s: %s", p, e)
            break


def _apply_config_overrides(c: "UraConfig") -> None:
    """Sobrescribe campos compartidos desde CONFIG (system_config.json)."""
    _cfg = _load_config_dict()
    if not _cfg:
        return
    if "paths" in _cfg and "data" in _cfg["paths"]:
        c.data_dir = _cfg["paths"]["data"]
    if "log_level" in _cfg:
        c.log_level = _cfg["log_level"]


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


def _load_config_dict() -> dict | None:
    """Intenta cargar CONFIG desde config_manager. Retorna None si no está disponible."""
    try:
        from core.config_manager import CONFIG

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
    """Configuración centralizada del motor URA."""

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    deploy_dir: str = RUTA_DEPLOY_DEFECTO
    data_dir: str = ""
    log_level: str = "INFO"
    is_vm: bool = True
    asus_host: str = HOST_ASUS_DEFECTO
    asus_port: int = PUERTO_ASUS_DEFECTO
    tailscale_iface: str = INTERFAZ_TAILSCALE_DEFECTO
    timer_interval_min: int = 5
    failure_knowledge_path: str = ""
    baseline_path: str = ""
    auto_verify: bool = False
    schema_version: int = 301  # v3.1

    def __post_init__(self):
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
    def load(cls, path: str = "") -> "UraConfig":
        """Carga configuración desde CONFIG, env vars o valores por defecto.

        Los campos compartidos con CONFIG (data_dir, log_level) se obtienen
        de system_config.json vía config_manager. El resto mantiene su lógica
        actual (env vars + defaults de la dataclass).

        El parámetro 'path' y la env var URA_CONFIG se mantienen por
        compatibilidad pero emiten deprecation warning.
        """
        c = cls()
        _apply_legacy_config(c, path)
        _apply_config_overrides(c)
        _apply_env_overrides(c)
        return c
