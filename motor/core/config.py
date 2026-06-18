import os, json, logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("ura.config")

RUTA_CONFIG_DEFECTO = "/etc/ura/config.json"
RUTA_DEPLOY_DEFECTO = "/home/ramon/URA/ura_ia_1972/deploy"
HOST_ASUS_DEFECTO = "100.72.103.12"
PUERTO_ASUS_DEFECTO = 4198
INTERFAZ_TAILSCALE_DEFECTO = "tailscale0"
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
    schema_version: int = 3

    def __post_init__(self):
        """Completa rutas relativas al directorio base del proyecto."""
        base = Path(__file__).parent.parent
        if not self.data_dir:
            self.data_dir = str(base / "data")
        if not self.failure_knowledge_path:
            self.failure_knowledge_path = str(base / "data" / "failure_knowledge_inicial.json")
        if not self.baseline_path:
            self.baseline_path = str(base / "data" / "baseline_inicial.json")

    @classmethod
    def load(cls, path: str = "") -> "UraConfig":
        """Carga configuración desde JSON, vars de entorno o valores por defecto."""
        candidates = [p for p in [path, os.environ.get("URA_CONFIG", ""), RUTA_CONFIG_DEFECTO] if p]
        c = cls()
        for p in candidates:
            if p and Path(p).exists():
                try:
                    d = json.loads(Path(p).read_text())
                    for k, v in d.items():
                        if hasattr(c, k):
                            setattr(c, k, v)
                    log.info("config cargada desde %s", p)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("error al cargar config %s: %s", p, e)
                break
        c.qdrant_host = os.environ.get("URA_QDRANT_HOST", c.qdrant_host)
        c.log_level = os.environ.get("URA_LOG_LEVEL", c.log_level)
        return c
