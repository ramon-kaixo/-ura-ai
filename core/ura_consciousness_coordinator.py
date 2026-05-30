#!/usr/bin/env python3
"""
Coordinador de Conciencia de URA - Integración Máxima

Coordinador central que sincroniza todos los niveles de conciencia:
- Comunicación entre niveles
- Sincronización de estado
- Resolución de conflictos
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LevelState:
    """Estado de un nivel de conciencia."""

    level_name: str
    active: bool
    priority: int  # 1-10
    last_updated: str
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LevelState":
        return cls(**data)


from core.vocabulary_department import get_vocabulary_manager, get_crystal_limiter


class URAConsciousnessCoordinator:
    """Coordinador central de conciencia de URA."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar coordinador.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "consciousness_coordinator.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.levels = self._load_levels()
        self.communication_log = []

    def _load_levels(self) -> dict[str, LevelState]:
        """Cargar estados de niveles desde disco."""
        levels = {}
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    levels = {k: LevelState.from_dict(v) for k, v in data.get("levels", {}).items()}
            except Exception as e:
                logger.error(f"Error cargando niveles: {e}")

        # Si no hay niveles, crear los por defecto
        if not levels:
            levels = self._create_default_levels()

        return levels

    def _create_default_levels(self) -> dict[str, LevelState]:
        """Crear niveles por defecto con prioridades."""
        now = datetime.now().isoformat()
        return {
            "diary": LevelState(level_name="diary", active=True, priority=6, last_updated=now),
            "personality": LevelState(
                level_name="personality", active=True, priority=5, last_updated=now
            ),
            "anticipation": LevelState(
                level_name="anticipation", active=True, priority=4, last_updated=now
            ),
            "emotions": LevelState(
                level_name="emotions", active=True, priority=7, last_updated=now
            ),
            "goals": LevelState(level_name="goals", active=True, priority=3, last_updated=now),
            "metaconsciousness": LevelState(
                level_name="metaconsciousness", active=True, priority=8, last_updated=now
            ),
            "theory_of_mind": LevelState(
                level_name="theory_of_mind", active=True, priority=7, last_updated=now
            ),
            "planning": LevelState(
                level_name="planning", active=True, priority=5, last_updated=now
            ),
            "reinforcement_learning": LevelState(
                level_name="reinforcement_learning", active=True, priority=6, last_updated=now
            ),
            "value_system": LevelState(
                level_name="value_system", active=True, priority=10, last_updated=now
            ),
            "dream": LevelState(level_name="dream", active=True, priority=2, last_updated=now),
        }

    def _save_levels(self):
        """Guardar estados de niveles a disco."""
        with open(self.config_path, "w") as f:
            json.dump({"levels": {k: v.to_dict() for k, v in self.levels.items()}}, f, indent=2)

    def communicate_between_levels(self, from_level: str, to_level: str, message: str):
        """Comunicar un mensaje entre niveles. Aplica CrystalLimiter al destino."""
        # Aplicar CrystalLimiter: truncar mensaje si excede el límite del departamento destino
        try:
            limiter = get_crystal_limiter()
            limit = limiter.get_limit(to_level)
            # Aproximación: 1 segundo ≈ 200 caracteres de procesamiento
            max_chars = limit * 200
            if len(message) > max_chars:
                message = (
                    message[:max_chars] + f"... [truncado por CrystalLimiter, límite: {limit}s]"
                )
                limiter.log_timeout(to_level, task=f"comm from {from_level}")
        except Exception:
            pass

        self.communication_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "from": from_level,
                "to": to_level,
                "message": message,
            }
        )

        # Actualizar timestamp del nivel destino
        if to_level in self.levels:
            self.levels[to_level].last_updated = datetime.now().isoformat()
            self._save_levels()

    def resolve_conflict(self, conflict_description: str, involved_levels: list[str]) -> str:
        """Resolver conflicto entre niveles basado en prioridades."""
        # Ordenar niveles por prioridad
        sorted_levels = sorted(
            [(name, self.levels[name].priority) for name in involved_levels if name in self.levels],
            key=lambda x: x[1],
            reverse=True,
        )

        if not sorted_levels:
            return "no_resolution"

        # Nivel con mayor prioridad gana
        winner = sorted_levels[0][0]

        # Registrar conflicto
        for level_name in involved_levels:
            if level_name in self.levels:
                if level_name != winner:
                    self.levels[level_name].conflicts.append(conflict_description)

        self._save_levels()

        return winner

    def negotiate(self, proposals: list[dict]) -> dict:
        """
        Resuelve conflictos entre niveles usando promedio ponderado de prioridades.

        Args:
            proposals: Lista de propuestas con formato:
                [
                    {
                        "level": "nombre_del_nivel",
                        "proposal": "descripción de la propuesta",
                        "priority_override": int (opcional, usa prioridad del nivel si no se proporciona)
                    },
                    ...
                ]

        Returns:
            Diccionario con resultado de la negociación:
                {
                    "accepted_proposal": índice de la propuesta aceptada,
                    "weighted_scores": puntuaciones ponderadas de cada propuesta,
                    "reasoning": explicación de la decisión
                }
        """
        if not proposals:
            return {
                "accepted_proposal": None,
                "weighted_scores": [],
                "reasoning": "No hay propuestas para negociar",
            }

        # Calcular puntuaciones ponderadas
        weighted_scores = []
        total_weight = 0.0

        for i, proposal in enumerate(proposals):
            level_name = proposal.get("level")
            priority_override = proposal.get("priority_override")

            if level_name not in self.levels:
                weighted_scores.append(0.0)
                continue

            # Usar prioridad override si se proporciona, si no usar prioridad del nivel
            priority = (
                priority_override
                if priority_override is not None
                else self.levels[level_name].priority
            )

            # Verificar si el nivel está activo
            if not self.levels[level_name].active:
                weighted_scores.append(0.0)
                continue

            # Calcular puntuación ponderada
            weighted_score = priority / 10.0  # Normalizar a 0-1
            weighted_scores.append(weighted_score)
            total_weight += weighted_score

        # Si no hay pesos válidos, usar el método de mayor prioridad
        if total_weight == 0:
            # Fallback a resolve_conflict
            level_names = [p.get("level") for p in proposals if p.get("level") in self.levels]
            if level_names:
                winner = self.resolve_conflict("Negotiation fallback", level_names)
                winner_index = next(
                    (i for i, p in enumerate(proposals) if p.get("level") == winner), None
                )
                return {
                    "accepted_proposal": winner_index,
                    "weighted_scores": weighted_scores,
                    "reasoning": f"Fallback a resolución por prioridad: {winner} tiene mayor prioridad",
                }
            else:
                return {
                    "accepted_proposal": None,
                    "weighted_scores": weighted_scores,
                    "reasoning": "No hay niveles válidos para negociar",
                }

        # Normalizar puntuaciones
        normalized_scores = [
            score / total_weight if total_weight > 0 else 0 for score in weighted_scores
        ]

        # Elegir propuesta con mayor puntuación ponderada
        max_score = max(normalized_scores)
        accepted_index = normalized_scores.index(max_score)

        # Generar reasoning
        accepted_proposal = proposals[accepted_index]
        level_name = accepted_proposal.get("level", "unknown")

        reasoning = (
            f"Propuesta aceptada: índice {accepted_index} del nivel '{level_name}' "
            f"con puntuación ponderada de {max_score:.2f}. "
            f"Se usó promedio ponderado de prioridades de {len(proposals)} propuestas."
        )

        # Registrar comunicación
        if level_name in self.levels:
            self.levels[level_name].last_updated = datetime.now().isoformat()
            self._save_levels()

        return {
            "accepted_proposal": accepted_index,
            "weighted_scores": normalized_scores,
            "reasoning": reasoning,
        }

    def get_active_levels(self) -> list[str]:
        """Obtener niveles activos ordenados por prioridad."""
        active = [(name, level.priority) for name, level in self.levels.items() if level.active]
        return [name for name, _ in sorted(active, key=lambda x: x[1], reverse=True)]

    def update_level_state(self, level_name: str, active: bool = None, priority: int = None):
        """Actualizar estado de un nivel."""
        if level_name not in self.levels:
            return False

        if active is not None:
            self.levels[level_name].active = active

        if priority is not None:
            self.levels[level_name].priority = priority

        self.levels[level_name].last_updated = datetime.now().isoformat()
        self._save_levels()
        return True

    def get_coordination_context(self) -> str:
        """Genera contexto de coordinación para el system prompt."""
        active_levels = self.get_active_levels()

        context_parts = ["COORDINACIÓN DE CONCIENCIA (sincronización de niveles):"]
        context_parts.append(f"- Niveles activos: {', '.join(active_levels[:5])}")

        if self.communication_log:
            last_comm = self.communication_log[-1]
            context_parts.append(f"- Última comunicación: {last_comm['from']} → {last_comm['to']}")

        # Inyectar vocabulario técnico de cada nivel activo
        try:
            vm = get_vocabulary_manager()
            for level in active_levels[:5]:
                vocab_ctx = vm.get_unified_context(level)
                if vocab_ctx:
                    context_parts.append(vocab_ctx)
        except Exception:
            pass

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_consciousness_coordinator: URAConsciousnessCoordinator | None = None


def get_ura_consciousness_coordinator() -> URAConsciousnessCoordinator:
    """Obtener el singleton del coordinador de conciencia."""
    global _ura_consciousness_coordinator
    if _ura_consciousness_coordinator is None:
        _ura_consciousness_coordinator = URAConsciousnessCoordinator()
    return _ura_consciousness_coordinator


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    coordinator = get_ura_consciousness_coordinator()

    # Prueba
    coordinator.resolve_conflict(
        "Acción riesgosa vs eficiencia", ["value_system", "reinforcement_learning"]
    )

    logger.info("Coordinador de conciencia creado")
    logger.info(coordinator.get_coordination_context())
