"""Config Manager — compatibility layer over UraConfig Pydantic model.

Deprecation: este módulo será eliminado en URA v4.
Migrar imports a 'from core.config import UraConfig' + usar UraConfig.load().
"""

import json
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
import logging
import os
import platform
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "system_config.json"


def _detect_profile_key() -> str:
    """Detecta qué perfil cargar según SO y hostname.

    linux → linux_asus si hostname contiene 'gx10', si no → linux_terminal
    darwin → darwin_mac
    """
    system = platform.system().lower()
    if system == "darwin":
        return "darwin_mac"
    if system == "linux":
        host = platform.node().lower()
        asus_hosts = ("gx10", "gx10-64c3", "asus")
        return "linux_asus" if any(h in host for h in asus_hosts) else "linux_terminal"
    msg = f"Sistema operativo no soportado: {system}"
    raise RuntimeError(msg)


def _expand_paths(config: dict[str, Any]) -> dict[str, Any]:
    """Expande ~ a home directory en todos los paths del perfil."""
    paths = config.get("paths", {})
    for key in list(paths):
        paths[key] = str(Path(paths[key]).expanduser().resolve())

    if "swarm" in config:
        sp = config["swarm"].get("devices_path", "")
        config["swarm"]["devices_path"] = str(Path(sp).expanduser().resolve())

    maintenance = config.get("maintenance", {})
    if "allowed_log_dirs" in maintenance:
        maintenance["allowed_log_dirs"] = [str(Path(d).expanduser().resolve()) for d in maintenance["allowed_log_dirs"]]
    return config


def _load_raw_config() -> dict[str, Any]:
    """Carga el archivo JSON de configuración."""
    with open(_CONFIG_PATH) as f:  # noqa: PTH123
        return json.load(f)
=======
import warnings
from pathlib import Path
from typing import Any

from core.config import UraConfig

warnings.warn(
    "core.config_manager será eliminado en URA v4. Migrar a: from core.config import UraConfig; cfg = UraConfig.load()",
    DeprecationWarning,
    stacklevel=2,
)

_CONFIG: UraConfig | None = None


=======
import warnings
from pathlib import Path
from typing import Any

from core.config import UraConfig

warnings.warn(
    "core.config_manager será eliminado en URA v4. Migrar a: from core.config import UraConfig; cfg = UraConfig.load()",
    DeprecationWarning,
    stacklevel=2,
)

_CONFIG: UraConfig | None = None


>>>>>>> Stashed changes
=======
import warnings
from pathlib import Path
from typing import Any

from core.config import UraConfig

warnings.warn(
    "core.config_manager será eliminado en URA v4. Migrar a: from core.config import UraConfig; cfg = UraConfig.load()",
    DeprecationWarning,
    stacklevel=2,
)

_CONFIG: UraConfig | None = None


>>>>>>> Stashed changes
=======
import warnings
from pathlib import Path
from typing import Any

from core.config import UraConfig

warnings.warn(
    "core.config_manager será eliminado en URA v4. Migrar a: from core.config import UraConfig; cfg = UraConfig.load()",
    DeprecationWarning,
    stacklevel=2,
)

_CONFIG: UraConfig | None = None


>>>>>>> Stashed changes
=======
import warnings
from pathlib import Path
from typing import Any

from core.config import UraConfig

warnings.warn(
    "core.config_manager será eliminado en URA v4. Migrar a: from core.config import UraConfig; cfg = UraConfig.load()",
    DeprecationWarning,
    stacklevel=2,
)

_CONFIG: UraConfig | None = None


>>>>>>> Stashed changes
def _get_config() -> UraConfig:
    global _CONFIG  # noqa: PLW0603
    if _CONFIG is None:
        _CONFIG = UraConfig.load()
    return _CONFIG
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes


def load_config() -> dict[str, Any]:
    cfg = _get_config()
    profile = cfg.profile_data or {}
    logs_dir = str(Path(profile.get("paths", {}).get("logs", str(Path.home() / "URA" / "logs"))))
    maint_default = str(Path.home() / "URA" / "logs" / "maintenance")
    maint_logs = str(Path(profile.get("paths", {}).get("maintenance_logs", maint_default)))
    return {
        "paths": {
            "data": cfg.data_dir or str(Path.home() / "URA" / "data"),
            "logs": logs_dir,
            "maintenance_logs": maint_logs,
        },
        "ollama": {"host": cfg.ollama_host, "port": cfg.ollama_port},
        "router": {"host": cfg.router_host, "port": cfg.router_port},
        "models": cfg.modelos,
        "fallback_model": cfg.fallback_model,
        "cache_ttl": cfg.cache_ttl,
        "role": cfg.role,
        "hostname": cfg.hostname,
        "maintenance": profile.get("maintenance", {}),
        "swarm": profile.get("swarm", {}),
        "ssh": {"user": cfg.ssh_user, "timeout": cfg.ssh_timeout},
        "rag": {
            "enabled": cfg.rag_enabled,
            "chunk_size": cfg.rag_chunk_size,
            "chunk_overlap": cfg.rag_chunk_overlap,
            "top_k": cfg.rag_top_k,
            "threshold": cfg.rag_threshold,
        },
        "patrones_clasificacion": cfg.patrones_clasificacion,
    }


CONFIG = load_config()


def get_base_dir() -> Path:
    return Path(CONFIG["paths"]["data"]).parent


def get_ollama_url() -> str:
    return _get_config().get_ollama_url()


def get_ollama_urls() -> list[str]:
    cfg = _get_config()
    return [cfg.get_ollama_url()]
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream


def get_ollama_urls() -> dict[str, str]:
    """Devuelve URLs primaria y de fallback de Ollama.

    La primaria usa host/port local del perfil activo.
    El fallback usa remote_host si existe, o la misma URL.
    """
    ollama = CONFIG.get("ollama", {})
    host = ollama.get("host", "localhost")
    port = ollama.get("port", 11434)
    remote = ollama.get("remote_host", host)
    primary = f"http://{host}:{port}"
    fallback = f"http://{remote}:{port}"
    return {"primary": primary, "fallback": fallback}
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes


def get_role() -> str:
    return _get_config().role


def get_hostname() -> str:
    return _get_config().hostname


def validate_config() -> list:
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    """Valida que los directorios declarados en config existan y tengan permisos.
    Retorna lista de warnings.
    """
    warnings = []
    for key in ("data", "logs", "maintenance_logs"):
        path = CONFIG["paths"].get(key)
        if path:
            p = Path(path)
            if not p.exists():
                warnings.append(f"Directorio no existe: {p}")
            elif not os.access(p, os.W_OK):
                warnings.append(f"Sin permisos de escritura: {p}")

    for dir_path in CONFIG.get("maintenance", {}).get("allowed_temp_dirs", []):
        if not Path(dir_path).exists():
            warnings.append(f"Directorio temp no existe: {dir_path}")  # noqa: PERF401

    for dir_path in CONFIG.get("maintenance", {}).get("allowed_log_dirs", []):
        if not Path(dir_path).exists():
            warnings.append(f"Directorio log no existe: {dir_path}")  # noqa: PERF401

    return warnings
=======
    return _get_config().validate_dirs()
>>>>>>> Stashed changes
=======
    return _get_config().validate_dirs()
>>>>>>> Stashed changes
=======
    return _get_config().validate_dirs()
>>>>>>> Stashed changes
=======
    return _get_config().validate_dirs()
>>>>>>> Stashed changes
=======
    return _get_config().validate_dirs()
>>>>>>> Stashed changes


_REQUIRED_KEYS = {
    "ollama": ["host", "port"],
    "router": ["host", "port"],
    "paths": ["data", "logs", "maintenance_logs"],
    "maintenance": ["thresholds", "exclude_patterns", "allowed_temp_dirs", "allowed_log_dirs"],
    "models": ["razonamiento", "codigo_complejo", "codigo_rapido", "respuesta_rapida"],
    "fallback_model": str,
    "cache_ttl": int,
    "llm": ["provider"],
}


def _check_required_keys(errors: list[str]) -> None:
    for section, keys in _REQUIRED_KEYS.items():
        if section not in CONFIG:
            errors.append(f"Falta seccion requerida: '{section}'")
        elif isinstance(keys, list):
            missing = [key for key in keys if key not in CONFIG[section]]
            errors.extend(f"Falta key '{key}' en seccion '{section}'" for key in missing)

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
        if isinstance(keys, list):
            for key in keys:
                if key not in CONFIG[section]:
                    errors.append(f"Falta key '{key}' en seccion '{section}'")  # noqa: PERF401

    for profile_name in ("linux_asus", "darwin_mac", "linux_terminal"):
        if profile_name not in CONFIG.get("_raw_profiles", {}):
            errors.append(f"Perfil '{profile_name}' no encontrado en system_config.json")  # noqa: PERF401
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

def validate_schema() -> list:
    errors: list[str] = []
    _check_required_keys(errors)
    if "patrones_clasificacion" not in CONFIG:
        errors.append("Falta 'patrones_clasificacion' en global_defaults")
    return errors


def validate_schema_json() -> list:
    try:
        import jsonschema
    except ImportError:
        return []
    schema_path = Path(__file__).resolve().parent.parent / "config" / "schema.json"
    config_path = Path(__file__).resolve().parent.parent / "config" / "system_config.json"
    if not schema_path.exists():
        return ["Schema file not found: config/schema.json"]
    errors: list[str] = []
    try:
        schema = json.loads(schema_path.read_text())
        raw_config = json.loads(config_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(raw_config), key=lambda e: e.path):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
            errors.append(f"{'.'.join(str(p) for p in err.path)}: {err.message}")  # noqa: PERF401
=======
            path_str = ".".join(str(p) for p in err.path)
            errors.append(f"{path_str}: {err.message}")
>>>>>>> Stashed changes
=======
            path_str = ".".join(str(p) for p in err.path)
            errors.append(f"{path_str}: {err.message}")
>>>>>>> Stashed changes
=======
            path_str = ".".join(str(p) for p in err.path)
            errors.append(f"{path_str}: {err.message}")
>>>>>>> Stashed changes
=======
            path_str = ".".join(str(p) for p in err.path)
            errors.append(f"{path_str}: {err.message}")
>>>>>>> Stashed changes
=======
            path_str = ".".join(str(p) for p in err.path)
            errors.append(f"{path_str}: {err.message}")
>>>>>>> Stashed changes
    except json.JSONDecodeError as e:
        errors.append(f"JSON invalido: {e}")
    except Exception as e:
        errors.append(str(e))
    return errors
