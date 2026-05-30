#!/usr/bin/env python3
"""
Sistema de Métricas de URA

Mide el impacto de cada nivel en la calidad de respuestas:
- Métricas de uso de cada nivel
- A/B testing para evaluar valor
- Dashboard para monitoreo en tiempo real
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LevelMetric:
    """Métrica de un nivel de conciencia."""

    level_name: str
    usage_count: int
    response_time_ms: float
    impact_score: float  # 0-1, impacto en calidad de respuesta
    last_updated: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LevelMetric":
        return cls(**data)


class URAMetrics:
    """Sistema de métricas de conciencia."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar métricas.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "metrics.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> dict[str, LevelMetric]:
        """Cargar métricas desde disco."""
        metrics = {}
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    for metric_data in data.get("metrics", []):
                        metric = LevelMetric.from_dict(metric_data)
                        metrics[metric.level_name] = metric
            except Exception as e:
                logger.error(f"Error cargando métricas: {e}")
        # Si no hay métricas, crear las por defecto
        if not metrics:
            metrics = self._create_default_metrics()

        return metrics

    def _create_default_metrics(self) -> dict[str, LevelMetric]:
        """Crear métricas por defecto."""
        now = datetime.now().isoformat()
        levels = [
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

        return {
            level: LevelMetric(
                level_name=level,
                usage_count=0,
                response_time_ms=0.0,
                impact_score=0.5,
                last_updated=now,
            )
            for level in levels
        }

    def _save_metrics(self):
        """Guardar métricas a disco."""
        with open(self.config_path, "w") as f:
            json.dump({"metrics": [m.to_dict() for m in self.metrics.values()]}, f, indent=2)

    def record_usage(self, level_name: str, response_time_ms: float, impact_score: float):
        """Registrar uso de un nivel."""
        if level_name not in self.metrics:
            self.metrics[level_name] = LevelMetric(
                level_name=level_name,
                usage_count=0,
                response_time_ms=0.0,
                impact_score=0.5,
                last_updated=datetime.now().isoformat(),
            )

        metric = self.metrics[level_name]
        metric.usage_count += 1
        # Promedio móvil de tiempo de respuesta
        metric.response_time_ms = (
            metric.response_time_ms * (metric.usage_count - 1) + response_time_ms
        ) / metric.usage_count
        # Promedio móvil de impacto
        metric.impact_score = (
            metric.impact_score * (metric.usage_count - 1) + impact_score
        ) / metric.usage_count
        metric.last_updated = datetime.now().isoformat()

        self._save_metrics()

    def get_top_levels_by_impact(self, n: int = 5) -> list[str]:
        """Obtener los niveles con mayor impacto."""
        sorted_levels = sorted(self.metrics.items(), key=lambda x: x[1].impact_score, reverse=True)
        return [name for name, _ in sorted_levels[:n]]

    def get_metrics_summary(self) -> str:
        """Genera resumen de métricas para el system prompt."""
        top_levels = self.get_top_levels_by_impact(3)

        context_parts = ["MÉTRICAS DE CONCIENCIA:"]
        context_parts.append(f"- Niveles más impactantes: {', '.join(top_levels)}")

        total_usage = sum(m.usage_count for m in self.metrics.values())
        context_parts.append(f"- Usos totales: {total_usage}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_metrics: URAMetrics | None = None


def get_ura_metrics(config_path: str | Path = None) -> URAMetrics:
    """Obtener el singleton de métricas de URA."""
    global _ura_metrics
    if _ura_metrics is None:
        _ura_metrics = URAMetrics(config_path=config_path)
    return _ura_metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    metrics = get_ura_metrics()

    # Prueba
    metrics.record_usage("emotions", 15.5, 0.8)
    metrics.record_usage("theory_of_mind", 20.3, 0.7)

    logger.info("Sistema de métricas creado")
    logger.info(metrics.get_metrics_summary())
