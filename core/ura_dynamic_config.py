#!/usr/bin/env python3
"""
Configuración Dinámica de URA

Activar/desactivar niveles según contexto:
- Perfiles de configuración (bajo consumo, máximo rendimiento)
- Ajuste dinámico de parámetros
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConfigProfile:
    """Perfil de configuración."""

    profile_name: str
    active_levels: list[str]
    cache_ttl: int  # segundos
    rate_limit_interval: int  # segundos
    lazy_loading: bool
    description: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConfigProfile":
        return cls(**data)


class URADynamicConfig:
    """Sistema de configuración dinámica."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar configuración dinámica.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "dynamic_config.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()
        self.current_profile = "balanced"
        # Ensure current_profile exists
        if not any(p.profile_name == self.current_profile for p in self.profiles):
            self.current_profile = self.profiles[0].profile_name if self.profiles else "balanced"

    def _load_profiles(self) -> list[ConfigProfile]:
        """Cargar perfiles desde disco."""
        profiles = []
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    profiles = [ConfigProfile.from_dict(p) for p in data.get("profiles", [])]
            except Exception as e:
                logger.error(f"Error cargando perfiles: {e}")

        # Si no hay perfiles, crear los por defecto
        if not profiles:
            profiles = self._create_default_profiles()

        return profiles

    def _create_default_profiles(self) -> list[ConfigProfile]:
        """Crear perfiles por defecto."""
        datetime.now().isoformat()
        all_levels = [
            "diary",
            "personality",
            "anticipation",
            "emotions",
            "goals",
            "metaconsciousness",
            "theory_of_mind",
            "planning",
            "reinforcement_learning",
            "value_system",
            "dream",
            "coordinator",
            "hooks",
            "hierarchical",
            "continuous",
            "self_reflection",
            "long_term_memory",
            "abstraction",
            "dynamic_goals",
            "external_integration",
            "probabilistic",
            "creativity",
            "self_improvement",
            "scenario_simulation",
            "temporal",
        ]

        critical_levels = ["diary", "emotions", "theory_of_mind", "value_system", "hierarchical"]

        return [
            ConfigProfile(
                profile_name="minimal",
                active_levels=critical_levels,
                cache_ttl=120,
                rate_limit_interval=10,
                lazy_loading=True,
                description="Solo niveles críticos, máximo ahorro de recursos",
            ),
            ConfigProfile(
                profile_name="balanced",
                active_levels=all_levels,
                cache_ttl=60,
                rate_limit_interval=5,
                lazy_loading=True,
                description="Todos los niveles con lazy loading",
            ),
            ConfigProfile(
                profile_name="performance",
                active_levels=all_levels,
                cache_ttl=30,
                rate_limit_interval=2,
                lazy_loading=False,
                description="Todos los niveles sin lazy loading, máximo rendimiento",
            ),
        ]

    def _save_profiles(self):
        """Guardar perfiles a disco."""
        with open(self.config_path, "w") as f:
            json.dump({"profiles": [p.to_dict() for p in self.profiles]}, f, indent=2)

    def set_profile(self, profile_name: str) -> bool:
        """Establecer perfil actual."""
        for profile in self.profiles:
            if profile.profile_name == profile_name:
                self.current_profile = profile_name
                self._save_profiles()
                return True

        return False

    def get_current_profile(self) -> ConfigProfile:
        """Obtener perfil actual."""
        for profile in self.profiles:
            if profile.profile_name == self.current_profile:
                return profile
        # Fallback to first profile if current_profile not found
        return self.profiles[0] if self.profiles else None

    def auto_select_profile(self, system_load: float) -> str:
        """Seleccionar perfil automáticamente según carga del sistema."""
        if system_load > 0.8:
            self.set_profile("minimal")
        elif system_load > 0.5:
            self.set_profile("balanced")
        else:
            self.set_profile("performance")

        return self.current_profile

    def get_config_context(self) -> str:
        """Genera contexto de configuración para el system prompt."""
        profile = self.get_current_profile()

        context_parts = ["CONFIGURACIÓN DINÁMICA:"]
        context_parts.append(f"- Perfil actual: {profile.profile_name}")
        context_parts.append(f"- Niveles activos: {len(profile.active_levels)}/23")
        context_parts.append(f"- Cache TTL: {profile.cache_ttl}s")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_dynamic_config: URADynamicConfig | None = None


def get_ura_dynamic_config(config_path: str | Path = None) -> URADynamicConfig:
    """Obtener el singleton de configuración dinámica de URA."""
    global _ura_dynamic_config
    if _ura_dynamic_config is None:
        _ura_dynamic_config = URADynamicConfig(config_path=config_path)
    return _ura_dynamic_config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = get_ura_dynamic_config()

    # Prueba
    config.auto_select_profile(0.6)
    logger.info("Configuración dinámica creada")
    logger.info(config.get_config_context())
