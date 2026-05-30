#!/usr/bin/env python3
"""
URA Configuration
Centralized configuration flags and settings for URA modules
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class URAFeatureFlags:
    """Flags booleanos de disponibilidad de módulos URA."""

    # Modules with try/except imports (set dynamically)
    network_audit_available: bool = False
    thread_cleaner_available: bool = False

    # Default availability flags (all False by default)
    auto_maintenance_available: bool = False
    cache_available: bool = False
    distributed_lock_available: bool = False
    dynamic_context_available: bool = False
    feature_flags_available: bool = False
    function_calling_available: bool = False
    knowledge_tables_available: bool = False
    mac_apps_available: bool = False
    mac_permissions_available: bool = False
    manual_repository_available: bool = False
    output_guardrails_available: bool = False
    ram_manager_available: bool = False
    rate_limiter_available: bool = False
    retry_logic_available: bool = False
    right_panel_available: bool = False
    sandbox_installer_available: bool = False
    screen_selector_available: bool = False
    security_checker_available: bool = False
    security_policy_available: bool = False
    self_reflection_available: bool = False
    smart_recovery_available: bool = False
    technical_alerts_available: bool = False
    ura_guardrail_available: bool = False
    ura_identity_available: bool = False
    ura_memory_available: bool = False
    vision_available: bool = False
    visual_automation_available: bool = False
    websocket_available: bool = False
    web_search_available: bool = False
    windsurf_binomio_available: bool = False
    disk_monitor_available: bool = False


@dataclass
class URAConfig:
    """Configuración numérica y parámetros operativos de URA.

    Los flags booleanos están separados en `URAFeatureFlags` (acceso vía `cfg.flags`).
    """

    # Feature flags compuestos
    flags: URAFeatureFlags = field(default_factory=URAFeatureFlags)

    # Environment Awareness (Nivel 21) settings
    env_scan_max_depth: int = 3
    env_scan_max_files: int = 10000
    env_scan_timeout: int = 30
    env_refresh_interval: int = 3600  # 1 hora

    # Tools Awareness (Nivel 22) settings
    tools_scan_timeout: int = 20
    tools_max_libraries: int = 50
    tools_refresh_interval: int = 86400  # 24 horas

    # Hardware Awareness (Nivel 23) settings
    hardware_scan_timeout: int = 10
    hardware_refresh_interval: int = 1800  # 30 minutos

    # Applications Awareness (Nivel 24) settings
    apps_scan_timeout: int = 30
    apps_max_applications: int = 500
    apps_refresh_interval: int = 7200  # 2 horas

    # Tools Interaction (Nivel 25) settings
    tools_max_executions: int = 50
    tools_shell_timeout: int = 30
    tools_python_timeout: int = 10
    tools_rate_limit_interval: float = 2.0
    tools_cache_ttl: int = 3600  # 1 hora
    tools_http_timeout: int = 30

    # Validation settings
    validation_max_command_length: int = 1000
    validation_max_code_length: int = 5000
    validation_max_query_length: int = 500
    validation_allowed_shell_commands: list[str] = field(
        default_factory=lambda: [
            "echo",
            "ls",
            "pwd",
            "cd",
            "cat",
            "grep",
            "find",
            "head",
            "tail",
            "wc",
            "sort",
            "uniq",
        ]
    )
    validation_allowed_python_functions: list[str] = field(
        default_factory=lambda: [
            "print",
            "len",
            "str",
            "int",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "range",
            "sum",
            "min",
            "max",
        ]
    )

    # Storage paths
    storage_base_path: Path = field(default_factory=lambda: Path.home() / ".ura")

    def get_env_config(self) -> dict[str, Any]:
        """Obtener configuración para Nivel 21."""
        return {
            "max_depth": self.env_scan_max_depth,
            "max_files": self.env_scan_max_files,
            "timeout": self.env_scan_timeout,
            "refresh_interval": self.env_refresh_interval,
        }

    def get_tools_config(self) -> dict[str, Any]:
        """Obtener configuración para Nivel 22."""
        return {
            "timeout": self.tools_scan_timeout,
            "max_libraries": self.tools_max_libraries,
            "refresh_interval": self.tools_refresh_interval,
        }

    def get_hardware_config(self) -> dict[str, Any]:
        """Obtener configuración para Nivel 23."""
        return {
            "timeout": self.hardware_scan_timeout,
            "refresh_interval": self.hardware_refresh_interval,
        }

    def get_apps_config(self) -> dict[str, Any]:
        """Obtener configuración para Nivel 24."""
        return {
            "timeout": self.apps_scan_timeout,
            "max_applications": self.apps_max_applications,
            "refresh_interval": self.apps_refresh_interval,
        }

    def get_tools_interaction_config(self) -> dict[str, Any]:
        """Obtener configuración para Nivel 25."""
        return {
            "max_executions": self.tools_max_executions,
            "shell_timeout": self.tools_shell_timeout,
            "python_timeout": self.tools_python_timeout,
            "rate_limit_interval": self.tools_rate_limit_interval,
            "cache_ttl": self.tools_cache_ttl,
            "http_timeout": self.tools_http_timeout,
        }

    # ---- Backward-compat: delegate flag access to self.flags ----
    def __getattr__(self, name: str) -> Any:
        if name.endswith("_available"):
            flags = self.__dict__.get("flags")
            if flags is not None and hasattr(flags, name):
                return getattr(flags, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.endswith("_available") and "flags" in self.__dict__:
            setattr(self.__dict__["flags"], name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Soporta mock.patch.object() que hace delattr al salir del contexto
        if name.endswith("_available") and "flags" in self.__dict__:
            flags = self.__dict__["flags"]
            if hasattr(flags, name):
                # No borramos el atributo del dataclass; lo reseteamos a su default.
                import dataclasses as _dc

                for f in _dc.fields(flags):
                    if f.name == name:
                        setattr(flags, name, f.default)
                        return
        super().__delattr__(name)


# Singleton
_ura_config: URAConfig | None = None


def get_ura_config() -> URAConfig:
    """Obtener el singleton de configuración de URA."""
    global _ura_config
    if _ura_config is None:
        _ura_config = URAConfig()
    return _ura_config


# Alias para compatibilidad
config = get_ura_config()
