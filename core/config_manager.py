#!/usr/bin/env python3
"""Config Manager - Carga unificada de configuración con perfiles por sistema operativo.
Detecta automáticamente Linux (Asus GX10) vs Darwin (Mac) y carga el perfil correcto.
"""

import json
import logging
import os
import platform
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "system_config.json"
_LOCAL_CONFIG_PATH = Path(__file__).parent.parent / "config.local.json"


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
    with open(_CONFIG_PATH) as f:
        return json.load(f)


def load_config() -> dict[str, Any]:
    """Carga y fusiona la configuración para el sistema operativo actual."""
    raw = _load_raw_config()

    profile_key = _detect_profile_key()

    profile = raw.get("profiles", {}).get(profile_key, {})
    if not profile:
        msg = f"Perfil '{profile_key}' no encontrado en system_config.json"
        raise RuntimeError(msg)

    config: dict[str, Any] = {}
    config.update(raw.get("global_defaults", {}))
    config.update(profile)

    # Sobrescribir con configuración local (no requiere sudo en GX10)
    if _LOCAL_CONFIG_PATH.exists():
        log.warning(
            "config.local.json encontrado — DEPRECATED. Será eliminado en F23. "
            "Migre las claves a system_config.json.",
        )
        try:
            local = json.loads(_LOCAL_CONFIG_PATH.read_text())
            config.update(local)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("error al cargar config local %s: %s", _LOCAL_CONFIG_PATH, e)

    # Guardar referencia a perfiles raw para validate_schema()
    config["_raw_profiles"] = raw.get("profiles", {})

    return _expand_paths(config)


CONFIG = load_config()


def get_base_dir() -> Path:
    """Devuelve el directorio base URA según el SO: ~/URA en Mac, /home/ramon/URA en Linux."""
    return Path(CONFIG["paths"]["data"]).parent


def get_ollama_url() -> str:
    """Devuelve la URL completa de Ollama para este nodo."""
    return f"http://{CONFIG['ollama']['host']}:{CONFIG['ollama']['port']}"


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


def get_role() -> str:
    """Devuelve el rol de este nodo: 'client' o 'server'."""
    return CONFIG.get("role", "unknown")


def get_hostname() -> str:
    """Devuelve el hostname lógico de este nodo según el perfil."""
    return CONFIG.get("hostname", "unknown")


def validate_config() -> list:
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
            warnings.append(f"Directorio temp no existe: {dir_path}")

    for dir_path in CONFIG.get("maintenance", {}).get("allowed_log_dirs", []):
        if not Path(dir_path).exists():
            warnings.append(f"Directorio log no existe: {dir_path}")

    return warnings


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


def validate_schema() -> list:
    """Valida la estructura de CONFIG contra el esquema esperado.
    Retorna lista de errores (vacia = OK).
    """
    errors = []

    for section, keys in _REQUIRED_KEYS.items():
        if section not in CONFIG:
            errors.append(f"Falta seccion requerida: '{section}'")
            continue

        if isinstance(keys, list):
            for key in keys:
                if key not in CONFIG[section]:
                    errors.append(f"Falta key '{key}' en seccion '{section}'")

    for profile_name in ("linux_asus", "darwin_mac", "linux_terminal"):
        if profile_name not in CONFIG.get("_raw_profiles", {}):
            errors.append(f"Perfil '{profile_name}' no encontrado en system_config.json")

    if "patrones_clasificacion" not in CONFIG:
        errors.append("Falta 'patrones_clasificacion' en global_defaults")

    return errors


def validate_schema_json() -> list:
    """Valida system_config.json contra el JSON Schema declarativo (config/schema.json).
    Requiere jsonschema instalado. Si no está, retorna lista vacía (no bloquea).
    """
    try:
        import jsonschema
    except ImportError:
        return []

    schema_path = Path(__file__).parent.parent / "config" / "schema.json"
    config_path = Path(__file__).parent.parent / "config" / "system_config.json"

    if not schema_path.exists():
        return ["Schema file not found: config/schema.json"]

    errors = []
    try:
        schema = json.loads(schema_path.read_text())
        raw_config = json.loads(config_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(raw_config), key=lambda e: e.path):
            errors.append(f"{'.'.join(str(p) for p in err.path)}: {err.message}")
    except json.JSONDecodeError as e:
        errors.append(f"JSON invalido: {e}")
    except Exception as e:
        errors.append(str(e))

    return errors
