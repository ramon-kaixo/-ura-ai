"""URA unified configuration — Pydantic-based, profile-aware."""

import json
import logging
import os
import platform
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger("ura.config")

RUTA_CONFIG_DEFECTO = "/etc/ura/config.json"
RUTA_DEPLOY_DEFECTO = "/home/ramon/URA/ura_ia_1972/deploy"
HOST_ASUS_DEFECTO = "10.164.1.99"
PUERTO_ASUS_DEFECTO = 4198
INTERFAZ_TAILSCALE_DEFECTO = "tailscale0"
RUTAS_CONFIG_OPENCODE = [
    "/etc/opencode/opencode.json",
    "/etc/opencode/opencode.jsonc",
    "/home/ramon/URA/ura_ia_1972/opencode.json",
    "/home/ramon/URA/ura_ia_1972/opencode.jsonc",
]

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class UraConfig(BaseModel):
    qdrant_host: str = "localhost"
    qdrant_port: int = Field(default=6333, ge=1, le=65535)
    deploy_dir: str = RUTA_DEPLOY_DEFECTO
    data_dir: str = ""
    log_level: str = "INFO"
    is_vm: bool = True
    asus_host: str = HOST_ASUS_DEFECTO
    asus_port: int = Field(default=PUERTO_ASUS_DEFECTO, ge=1, le=65535)
    tailscale_iface: str = INTERFAZ_TAILSCALE_DEFECTO
    timer_interval_min: int = Field(default=5, ge=1, le=1440)
    failure_knowledge_path: str = ""
    baseline_path: str = ""
    auto_verify: bool = False
    schema_version: int = Field(default=7, ge=1, le=999)

    role: str = "server"
    hostname: str = ""
    ollama_host: str = "localhost"
    ollama_port: int = Field(default=11434, ge=1, le=65535)
    router_host: str = Field(default="0.0.0.0")  # noqa: S104
    router_port: int = Field(default=11435, ge=1, le=65535)
    modelos: dict[str, list[str]] = Field(default_factory=lambda: {})
    fallback_model: str = "qwen2.5:7b"
    cache_ttl: int = Field(default=3600, ge=60, le=86400)
    retention_days: dict[str, int] = Field(default_factory=lambda: {"logs": 7, "cache": 30, "docker_build": 7})
    patrones_clasificacion: dict[str, list[str]] = Field(default_factory=lambda: {})
    ssh_user: str = "ramon"
    ssh_timeout: int = Field(default=300, ge=1, le=3600)
    rag_enabled: bool = False
    rag_chunk_size: int = Field(default=500, ge=50, le=10000)
    rag_chunk_overlap: int = Field(default=50, ge=0, le=1000)
    rag_top_k: int = Field(default=5, ge=1, le=100)
    rag_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    _profile_cache: dict[str, Any] | None = None

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in VALID_LOG_LEVELS:
            msg = f"log_level inválido: '{v}'. Válidos: {sorted(VALID_LOG_LEVELS)}"
            raise ValueError(msg)
        return upper

    @property
    def profile_data(self) -> dict[str, Any]:
        return self._profile_cache or {}

    def model_post_init(self, _ctx):
        base = Path(__file__).parent.parent
        if not self.data_dir:
            self.data_dir = str(base / "data")
        if not self.failure_knowledge_path:
            self.failure_knowledge_path = str(base / "data" / "failure_knowledge_inicial.json")
        if not self.baseline_path:
            self.baseline_path = str(base / "data" / "baseline_inicial.json")
        if not self.hostname:
            self.hostname = platform.node().lower()

    @classmethod
    def _detect_profile_key(cls) -> str:
        system = platform.system().lower()
        if system == "darwin":
            return "darwin_mac"
        if system == "linux":
            host = platform.node().lower()
            return "linux_asus" if any(h in host for h in ("gx10", "asus")) else "linux_terminal"
        return "linux_terminal"

    @classmethod
    def _load_profile(cls, profile_key: str | None = None) -> dict[str, Any]:
        system_cfg = Path(__file__).resolve().parent.parent / "config" / "system_config.json"
        if not system_cfg.exists():
            return {}
        try:
            raw = json.loads(system_cfg.read_text())
            key = profile_key or cls._detect_profile_key()
            profile = raw.get("profiles", {}).get(key, {})
            defaults = raw.get("global_defaults", {})
            merged = dict(defaults)
            merged.update(profile)
            return merged
        except (json.JSONDecodeError, OSError) as e:
            log.warning("error cargando system_config.json: %s", e)
            return {}

    @classmethod
    def _load_legacy_json(cls, path: str = "") -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        candidates = [p for p in [path, os.environ.get("URA_CONFIG", ""), RUTA_CONFIG_DEFECTO] if p]
        for p in candidates:
            if p and Path(p).exists():
                try:
                    d = json.loads(Path(p).read_text())
                    kwargs = {k: v for k, v in d.items() if k in cls.model_fields}
                    log.info("config cargada desde %s", p)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("error al cargar config %s: %s", p, e)
                break
        return kwargs

    @classmethod
    def _coerce_env_int(cls, key: str, default: int) -> int:
        val = os.environ.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            log.warning("URA_ENV: %s='%s' no es entero, usando default=%s", key, val, default)
            return default

    _ENV_MAP: ClassVar[list[tuple[str, str, type]]] = [
        ("URA_QDRANT_HOST", "qdrant_host", str),
        ("URA_QDRANT_PORT", "qdrant_port", int),
        ("URA_LOG_LEVEL", "log_level", str),
        ("URA_OLLAMA_HOST", "ollama_host", str),
        ("URA_OLLAMA_PORT", "ollama_port", int),
        ("URA_ROUTER_PORT", "router_port", int),
        ("URA_SSH_TIMEOUT", "ssh_timeout", int),
        ("URA_TIMER_INTERVAL_MIN", "timer_interval_min", int),
        ("URA_CACHE_TTL", "cache_ttl", int),
        ("URA_RAG_CHUNK_SIZE", "rag_chunk_size", int),
        ("URA_RAG_CHUNK_OVERLAP", "rag_chunk_overlap", int),
        ("URA_RAG_TOP_K", "rag_top_k", int),
        ("URA_RAG_THRESHOLD", "rag_threshold", float),
    ]

    @classmethod
    def _env_to_kwargs(cls) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for env_key, field_name, cast in cls._ENV_MAP:
            if env_key not in os.environ:
                continue
            raw = os.environ[env_key]
            try:
                kwargs[field_name] = cast(raw)  # type: ignore[call-arg]
            except (ValueError, TypeError):
                log.warning("URA_ENV: %s='%s' no es %s, ignorado", env_key, raw, cast.__name__)
        return kwargs

    @classmethod
    def load(cls, path: str = "", profile: str | None = None) -> "UraConfig":
        kwargs = cls._load_legacy_json(path)

        profile_data = cls._load_profile(profile)
        profile_map = {
            "log_level": profile_data.get("log_level"),
            "role": profile_data.get("role"),
            "hostname": profile_data.get("hostname"),
            "ollama_host": profile_data.get("ollama", {}).get("host"),
            "ollama_port": profile_data.get("ollama", {}).get("port"),
            "router_host": profile_data.get("router", {}).get("host"),
            "router_port": profile_data.get("router", {}).get("port"),
            "modelos": profile_data.get("models"),
            "fallback_model": profile_data.get("fallback_model"),
            "cache_ttl": profile_data.get("cache_ttl"),
            "retention_days": profile_data.get("retention_days"),
            "patrones_clasificacion": profile_data.get("patrones_clasificacion"),
            "ssh_user": profile_data.get("ssh", {}).get("user"),
            "ssh_timeout": profile_data.get("ssh", {}).get("timeout"),
            "rag_enabled": profile_data.get("rag", {}).get("enabled"),
            "rag_chunk_size": profile_data.get("rag", {}).get("chunk_size"),
            "rag_chunk_overlap": profile_data.get("rag", {}).get("chunk_overlap"),
            "rag_top_k": profile_data.get("rag", {}).get("top_k"),
            "rag_threshold": profile_data.get("rag", {}).get("threshold"),
        }
        kwargs.update({k: v for k, v in profile_map.items() if v is not None})
        paths = profile_data.get("paths", {})
        if paths.get("data"):
            kwargs["data_dir"] = str(Path(paths["data"]).expanduser().resolve())

        kwargs.update(cls._env_to_kwargs())

        try:
            c = cls(**kwargs)
            c._profile_cache = profile_data
            return c
        except ValidationError as e:
            errores = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errores.append(f"  {loc}: {err['msg']}")
            msg = "Configuración inválida:\n" + "\n".join(errores)
            log.error(msg)
            raise ValueError(msg) from e

    def get_ollama_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"

    def get_router_url(self) -> str:
        return f"http://{self.router_host}:{self.router_port}"

    def validate_dirs(self) -> list[str]:
        warnings = []
        if self.data_dir and not Path(self.data_dir).exists():
            warnings.append(f"Directorio data no existe: {self.data_dir}")
        return warnings
