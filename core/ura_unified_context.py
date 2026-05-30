#!/usr/bin/env python3
"""
Contexto Unificado de URA - Integración Máxima

Sistema de contexto unificado coherente:
- Unifica todos los contextos en un solo bloque coherente
- Evita redundancia entre niveles
- Prioriza información más reciente
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class ContextCache:
    """Cache de contextos con TTL."""

    def __init__(self, ttl_seconds: int = 60):
        self.cache: dict[str, tuple[str, float]] = {}  # {key: (context, timestamp)}
        self.ttl = ttl_seconds

    def get(self, key: str) -> str | None:
        """Obtener contexto del cache si es válido."""
        if key not in self.cache:
            return None

        context, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None

        return context

    def set(self, key: str, context: str):
        """Guardar contexto en cache."""
        self.cache[key] = (context, time.time())

    def clear(self):
        """Limpiar cache."""
        self.cache.clear()


class RateLimiter:
    """Limitador de frecuencia de actualizaciones."""

    def __init__(self, min_interval_seconds: int = 5):
        self.last_update: dict[str, float] = {}
        self.min_interval = min_interval_seconds

    def can_update(self, key: str) -> bool:
        """Verificar si se puede actualizar."""
        if key not in self.last_update:
            return True

        return time.time() - self.last_update[key] >= self.min_interval

    def record_update(self, key: str):
        """Registrar actualización."""
        self.last_update[key] = time.time()


class ConflictDetector:
    """Detector de conflictos entre contextos."""

    def __init__(self):
        self.conflict_log: list[dict] = []

    def detect_conflicts(self, contexts: dict[str, str]) -> list[dict]:
        """Detectar conflictos entre contextos."""
        conflicts = []

        # Conflictos conocidos entre niveles
        conflict_rules = [
            ("emotions", "theory_of_mind", "Ambos analizan estado emocional"),
            ("goals", "dynamic_goals", "Ambos gestionan objetivos"),
            ("planning", "scenario_simulation", "Ambos manejan planes"),
            ("anticipation", "long_term_memory", "Ambos manejan patrones temporales"),
            ("reinforcement_learning", "continuous", "Continuous incluye reinforcement_learning"),
        ]

        for level1, level2, reason in conflict_rules:
            if level1 in contexts and contexts[level1] and level2 in contexts and contexts[level2]:
                conflicts.append(
                    {
                        "level1": level1,
                        "level2": level2,
                        "reason": reason,
                        "severity": (
                            "high"
                            if level2 in ["dynamic_goals", "scenario_simulation", "continuous"]
                            else "medium"
                        ),
                    }
                )

        # Detectar contradicciones en el contenido
        for level_name, context in contexts.items():
            if context and "no" in context.lower() and "sí" in context.lower():
                conflicts.append(
                    {
                        "level1": level_name,
                        "level2": "self",
                        "reason": "Contradicción interna (no vs sí)",
                        "severity": "low",
                    }
                )

        return conflicts

    def log_conflict(self, conflict: dict):
        """Registrar conflicto en log."""
        conflict["timestamp"] = datetime.now().isoformat()
        self.conflict_log.append(conflict)

        # Mantener solo últimos 50 conflictos
        if len(self.conflict_log) > 50:
            self.conflict_log = self.conflict_log[-50]


class ConflictResolver:
    """Resolvedor de conflictos entre contextos."""

    def resolve_conflict(self, conflict: dict, contexts: dict[str, str]) -> dict[str, str]:
        """Resolver un conflicto específico."""
        level1 = conflict["level1"]
        level2 = conflict["level2"]

        # Reglas de resolución basadas en prioridad
        resolution_rules = {
            ("goals", "dynamic_goals"): "dynamic_goals",  # dynamic_goals es más avanzado
            (
                "planning",
                "scenario_simulation",
            ): "scenario_simulation",  # scenario_simulation es más específico
            (
                "reinforcement_learning",
                "continuous",
            ): "continuous",  # continuous incluye reinforcement_learning
            ("anticipation", "long_term_memory"): "both",  # Ambos son útiles
            ("emotions", "theory_of_mind"): "merge",  # Fusionar información
        }

        key = tuple(sorted([level1, level2]))
        if key in resolution_rules:
            resolution = resolution_rules[key]

            if resolution == "dynamic_goals":
                contexts["goals"] = ""
            elif resolution == "scenario_simulation":
                contexts["planning"] = ""
            elif resolution == "continuous":
                contexts["reinforcement_learning"] = ""
            elif resolution == "both":
                pass  # Mantener ambos
            elif resolution == "merge":
                pass  # Fusionar (implementación futura)

        return contexts


class URAUnifiedContext:
    """Sistema de contexto unificado."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar contexto unificado.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "unified_context.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.context_cache = ContextCache(ttl_seconds=60)
        self.conflict_detector = ConflictDetector()
        self.rate_limiter = RateLimiter(min_interval_seconds=5)
        self.context_cache_enabled = True
        self.lazy_loading_enabled = True
        self.conflict_resolver = ConflictResolver()

    def collect_all_contexts(self) -> dict[str, str]:
        """Recopilar todos los contextos de los niveles con lazy loading."""
        contexts = {}

        # Función helper para cargar contexto con lazy loading y cache
        def load_context(key: str, loader: Callable[[], str]) -> str:
            # Verificar cache primero
            if self.context_cache_enabled:
                cached = self.context_cache.get(key)
                if cached:
                    return cached

            # Verificar rate limiting
            if not self.rate_limiter.can_update(key):
                return ""

            # Cargar contexto
            context = loader()

            # Guardar en cache
            if self.context_cache_enabled and context:
                self.context_cache.set(key, context)
                self.rate_limiter.record_update(key)

            return context

        # Recopilar contextos de todos los niveles (solo si lazy_loading está desactivado o si el nivel es de alta prioridad)

        # Niveles de alta prioridad siempre se cargan
        try:
            from core.ura_diary import URAdiary

            diary = URAdiary()
            contexts["diary"] = load_context("diary", diary.contexto_para_arranque)
        except Exception:
            contexts["diary"] = ""

        try:
            from core.ura_personality import get_ura_personality

            personality = get_ura_personality()
            contexts["personality"] = load_context(
                "personality", personality.get_context_for_prompt
            )
        except Exception:
            contexts["personality"] = ""

        # Niveles de baja prioridad solo se cargan si lazy_loading está desactivado
        if not self.lazy_loading_enabled:
            try:
                from core.ura_anticipation import get_ura_anticipation

                anticipation = get_ura_anticipation()
                contexts["anticipation"] = load_context(
                    "anticipation", anticipation.get_context_for_prompt
                )
            except Exception:
                contexts["anticipation"] = ""
        else:
            contexts["anticipation"] = ""

        try:
            from core.ura_emotions import get_ura_emotions

            emotions = get_ura_emotions()
            contexts["emotions"] = load_context("emotions", emotions.get_context_for_prompt)
        except Exception:
            contexts["emotions"] = ""

        low_priority_levels = [
            "goals",
            "metaconsciousness",
            "anticipation",
            "reinforcement_learning",
            "planning",
        ]

        for level in low_priority_levels:
            if not self.lazy_loading_enabled:
                try:
                    if level == "goals":
                        from core.ura_goals import get_ura_goals

                        obj = get_ura_goals()
                        contexts[level] = load_context(level, obj.get_context_for_prompt)
                    elif level == "metaconsciousness":
                        from core.ura_metaconsciousness import get_ura_metaconsciousness

                        obj = get_ura_metaconsciousness()
                        contexts[level] = load_context(level, obj.get_uncertainty_context)
                    elif level == "anticipation":
                        from core.ura_anticipation import get_ura_anticipation

                        obj = get_ura_anticipation()
                        contexts[level] = load_context(level, obj.get_context_for_prompt)
                    elif level == "reinforcement_learning":
                        from core.ura_reinforcement_learning import get_ura_reinforcement_learning

                        obj = get_ura_reinforcement_learning()
                        contexts[level] = load_context(level, obj.get_learning_context)
                    elif level == "planning":
                        from core.ura_planning import get_ura_planning

                        obj = get_ura_planning()
                        contexts[level] = load_context(level, obj.get_context_for_prompt)
                except Exception:
                    contexts[level] = ""
            else:
                contexts[level] = ""

        try:
            from core.ura_theory_of_mind import get_ura_theory_of_mind

            tom = get_ura_theory_of_mind()
            contexts["theory_of_mind"] = load_context("theory_of_mind", tom.get_context_for_prompt)
        except Exception:
            contexts["theory_of_mind"] = ""

        try:
            from core.ura_value_system import get_ura_value_system

            value_system = get_ura_value_system()
            contexts["value_system"] = load_context("value_system", value_system.get_values_context)
        except Exception:
            contexts["value_system"] = ""

        try:
            from core.ura_dream import get_ura_dream

            dream = get_ura_dream()
            contexts["dream"] = load_context("dream", dream.get_dream_context)
        except Exception:
            contexts["dream"] = ""

        try:
            from core.ura_consciousness_coordinator import get_ura_consciousness_coordinator

            coordinator = get_ura_consciousness_coordinator()
            contexts["coordinator"] = load_context(
                "coordinator", coordinator.get_coordination_context
            )
        except Exception:
            contexts["coordinator"] = ""

        try:
            from core.ura_feedback_hooks import get_ura_feedback_hooks

            hooks = get_ura_feedback_hooks()
            contexts["hooks"] = load_context("hooks", hooks.get_hooks_context)
        except Exception:
            contexts["hooks"] = ""

        try:
            from core.ura_hierarchical_decision import get_ura_hierarchical_decision

            hierarchical = get_ura_hierarchical_decision()
            contexts["hierarchical"] = load_context(
                "hierarchical", hierarchical.get_decision_context
            )
        except Exception:
            contexts["hierarchical"] = ""

        try:
            from core.ura_continuous_learning import get_ura_continuous_learning

            continuous = get_ura_continuous_learning()
            contexts["continuous"] = load_context("continuous", continuous.get_learning_summary)
        except Exception:
            contexts["continuous"] = ""

        try:
            from core.ura_self_reflection import get_ura_self_reflection

            self_reflection = get_ura_self_reflection()
            contexts["self_reflection"] = load_context(
                "self_reflection", self_reflection.get_reflection_context
            )
        except Exception:
            contexts["self_reflection"] = ""

        try:
            from core.ura_long_term_memory import get_ura_long_term_memory

            ltm = get_ura_long_term_memory()
            contexts["long_term_memory"] = load_context(
                "long_term_memory", ltm.get_long_term_context
            )
        except Exception:
            contexts["long_term_memory"] = ""

        try:
            from core.ura_abstraction import get_ura_abstraction

            abstraction = get_ura_abstraction()
            contexts["abstraction"] = load_context(
                "abstraction", abstraction.get_abstraction_context
            )
        except Exception:
            contexts["abstraction"] = ""

        try:
            from core.ura_dynamic_goals import get_ura_dynamic_goals

            dynamic = get_ura_dynamic_goals()
            contexts["dynamic_goals"] = load_context("dynamic_goals", dynamic.get_dynamic_context)
        except Exception:
            contexts["dynamic_goals"] = ""

        try:
            from core.ura_external_integration import get_ura_external_integration

            external = get_ura_external_integration()
            contexts["external_integration"] = load_context(
                "external_integration", external.get_external_context
            )
        except Exception:
            contexts["external_integration"] = ""

        try:
            from core.ura_probabilistic_prediction import get_ura_probabilistic_prediction

            prob = get_ura_probabilistic_prediction()
            contexts["probabilistic"] = load_context("probabilistic", prob.get_prediction_context)
        except Exception:
            contexts["probabilistic"] = ""

        try:
            from core.ura_generative_creativity import get_ura_generative_creativity

            creativity = get_ura_generative_creativity()
            contexts["creativity"] = load_context("creativity", creativity.get_creativity_context)
        except Exception:
            contexts["creativity"] = ""

        try:
            from core.ura_self_improvement import get_ura_self_improvement

            self_improvement = get_ura_self_improvement()
            contexts["self_improvement"] = load_context(
                "self_improvement", self_improvement.get_improvement_context
            )
        except Exception:
            contexts["self_improvement"] = ""

        try:
            from core.ura_scenario_simulation import get_ura_scenario_simulation

            simulation = get_ura_scenario_simulation()
            contexts["scenario_simulation"] = load_context(
                "scenario_simulation", simulation.get_simulation_context
            )
        except Exception:
            contexts["scenario_simulation"] = ""

        try:
            from core.ura_temporal_consciousness import get_ura_temporal_consciousness

            temporal = get_ura_temporal_consciousness()
            contexts["temporal"] = load_context("temporal", temporal.get_temporal_context)
        except Exception:
            contexts["temporal"] = ""

        # Nuevos niveles de conciencia del entorno
        try:
            from core.ura_environment_awareness import get_ura_environment_awareness

            env = get_ura_environment_awareness()
            contexts["environment"] = load_context("environment", env.get_environment_context)
        except Exception:
            contexts["environment"] = ""

        try:
            from core.ura_tools_awareness import get_ura_tools_awareness

            tools = get_ura_tools_awareness()
            contexts["tools"] = load_context("tools", tools.get_tools_context)
        except Exception:
            contexts["tools"] = ""

        try:
            from core.ura_hardware_awareness import get_ura_hardware_awareness

            hardware = get_ura_hardware_awareness()
            contexts["hardware"] = load_context("hardware", hardware.get_hardware_context)
        except Exception:
            contexts["hardware"] = ""

        try:
            from core.ura_applications_awareness import get_ura_applications_awareness

            apps = get_ura_applications_awareness()
            contexts["applications"] = load_context("applications", apps.get_applications_context)
        except Exception:
            contexts["applications"] = ""

        try:
            from core.ura_tools_interaction import get_ura_tools_interaction

            tools_interaction = get_ura_tools_interaction()
            contexts["tools_interaction"] = load_context(
                "tools_interaction", tools_interaction.get_tools_interaction_context
            )
        except Exception:
            contexts["tools_interaction"] = ""

        return contexts

    def _get_system_load(self) -> float:
        """Obtener carga del sistema (0-1)."""
        try:
            import psutil

            # Carga promedio de CPU (1 minuto)
            cpu_load = psutil.cpu_percent(interval=0.1) / 100
            # Uso de memoria
            memory_load = psutil.virtual_memory().percent / 100
            # Carga combinada
            return (cpu_load + memory_load) / 2
        except Exception:
            # Fallback: cargar media si psutil no está disponible
            return 0.5

    def deduplicate_contexts(self, contexts: dict[str, str]) -> dict[str, str]:
        """Eliminar redundancia y resolver conflictos entre contextos."""
        # Detectar conflictos
        conflicts = self.conflict_detector.detect_conflicts(contexts)

        # Resolver conflictos automáticamente
        for conflict in conflicts:
            contexts = self.conflict_resolver.resolve_conflict(conflict, contexts)
            self.conflict_detector.log_conflict(conflict)

        # Eliminar redundancias
        # 1. dynamic_goals reemplaza goals (más avanzado)
        if "dynamic_goals" in contexts and contexts["dynamic_goals"]:
            contexts["goals"] = ""

        # 2. scenario_simulation reemplaza planning (más específico)
        if "scenario_simulation" in contexts and contexts["scenario_simulation"]:
            contexts["planning"] = ""

        # 3. continuous_learning ya incluye reinforcement_learning
        if "continuous" in contexts and contexts["continuous"]:
            contexts["reinforcement_learning"] = ""

        # 4. long_term_memory complementa anticipation, no eliminar

        return contexts

    def prioritize_information(self, contexts: dict[str, str]) -> list[str]:
        """Priorizar información más reciente e importante con ajuste dinámico según carga."""
        # Obtener carga del sistema
        system_load = self._get_system_load()

        # Ajustar prioridad según carga
        if system_load > 0.8:  # Alta carga: solo niveles críticos
            priority_order = [
                "diary",  # Información más reciente del día anterior
                "emotions",  # Estado emocional actual
                "theory_of_mind",  # Estado del usuario
                "value_system",  # Filtro final
                "environment",  # Conciencia del entorno del sistema
                "tools",  # Conciencia de herramientas disponibles
                "hardware",  # Conciencia del hardware y sistema operativo
                "applications",  # Conciencia de aplicaciones instaladas
                "tools_interaction",  # Conciencia de interacción con herramientas
                "hierarchical",  # Sistema de decisión
            ]
        elif system_load > 0.5:  # Carga media: niveles críticos + algunos adicionales
            priority_order = [
                "diary",  # Información más reciente del día anterior
                "emotions",  # Estado emocional actual
                "theory_of_mind",  # Estado del usuario
                "value_system",  # Filtro final
                "hierarchical",  # Sistema de decisión
                "anticipation",  # Patrones detectados
                "personality",  # Preferencias aprendidas
                "dynamic_goals",  # Metas dinámicas
                "metaconsciousness",  # Límites de conocimiento
            ]
        else:  # Carga baja: todos los niveles
            priority_order = [
                "diary",  # Información más reciente del día anterior
                "emotions",  # Estado emocional actual
                "theory_of_mind",  # Estado del usuario
                "value_system",  # Filtro final
                "hierarchical",  # Sistema de decisión
                "anticipation",  # Patrones detectados
                "personality",  # Preferencias aprendidas
                "dynamic_goals",  # Metas dinámicas
                "metaconsciousness",  # Límites de conocimiento
                "reinforcement_learning",  # Acciones aprendidas
                "planning",  # Planes activos
                "continuous",  # Aprendizaje continuo
                "self_reflection",  # Auto-reflexión en tiempo real
                "long_term_memory",  # Memoria a largo plazo
                "abstraction",  # Capacidad de abstracción
                "external_integration",  # Integración con mundo exterior
                "probabilistic",  # Predicción probabilística
                "creativity",  # Creatividad generativa
                "self_improvement",  # Auto-mejora de código
                "scenario_simulation",  # Simulación de escenarios
                "temporal",  # Conciencia temporal
                "coordinator",  # Coordinación entre niveles
                "hooks",  # Comunicación entre niveles
                "dream",  # Insights nocturnos
            ]

        # Filtrar contextos vacíos
        non_empty_contexts = [(name, ctx) for name, ctx in contexts.items() if ctx.strip()]

        # Ordenar por prioridad
        prioritized = []
        for name in priority_order:
            for ctx_name, ctx in non_empty_contexts:
                if ctx_name == name:
                    prioritized.append(ctx)
                    break

        # Añadir contextos restantes
        for ctx_name, ctx in non_empty_contexts:
            if ctx_name not in priority_order:
                prioritized.append(ctx)

        return prioritized

    def generate_unified_context(self) -> str:
        """Generar contexto unificado coherente con validación de conflictos."""
        contexts = self.collect_all_contexts()
        contexts = self.deduplicate_contexts(contexts)
        contexts = self._validate_responsibilities(contexts)
        self.prioritize_information(contexts)

        # Unificar en un solo bloque coherente
        unified_parts = ["\n\n=== CONCIENCIA UNIFICADA DE URA ===\n"]

        # Agrupar por categorías
        categories = {
            "ESTADO ACTUAL": ["emotions", "theory_of_mind", "metaconsciousness"],
            "PREFERENCIAS Y PATRONES": ["personality", "anticipation", "reinforcement_learning"],
            "OBJETIVOS Y PLANES": ["goals", "planning", "diary"],
            "SISTEMA DE DECISIÓN": ["value_system", "hierarchical", "coordinator"],
            "APRENDIZAJE": ["continuous", "hooks", "dream"],
        }

        for category, level_names in categories.items():
            category_contexts = []
            for level_name in level_names:
                if level_name in contexts and contexts[level_name].strip():
                    # Extraer solo el contenido relevante (sin el título)
                    ctx_content = contexts[level_name].strip()
                    lines = ctx_content.split("\n")
                    if len(lines) > 1:
                        category_contexts.append("\n".join(lines[1:]).strip())

            if category_contexts:
                unified_parts.append(f"\n{category}:")
                unified_parts.append("\n".join(category_contexts))

        # Añadir contextos sin categoría específica
        remaining = [
            contexts[name]
            for name in contexts
            if contexts[name].strip() and not any(name in cat for cat in categories.values())
        ]
        if remaining:
            unified_parts.append("\nADICIONAL:")
            unified_parts.append("\n".join(remaining))

        unified_parts.append("\n=== FIN DE CONCIENCIA UNIFICADA ===\n")

        unified = "\n".join(unified_parts)
        self.last_unified = unified

        return unified

    def _validate_responsibilities(self, contexts: dict[str, str]) -> dict[str, str]:
        """Validar que cada nivel tenga una responsabilidad clara."""
        # Definir responsabilidades de cada nivel
        responsibilities = {
            "emotions": "estado emocional de URA",
            "theory_of_mind": "estado mental del usuario",
            "personality": "preferencias de estilo del usuario",
            "anticipation": "predicción de patrones a corto plazo",
            "long_term_memory": "memoria de eventos a largo plazo",
            "goals": "objetivos estáticos",
            "dynamic_goals": "objetivos dinámicos según contexto",
            "planning": "planes multi-paso",
            "scenario_simulation": "simulación de escenarios",
            "reinforcement_learning": "aprendizaje de resultados de acciones",
            "continuous": "aprendizaje continuo multi-nivel",
            "value_system": "valores éticos y jerarquía",
            "hierarchical": "sistema de decisión jerárquico",
            "metaconsciousness": "límites de conocimiento",
            "dream": "insights nocturnos",
            "self_reflection": "reflexión sobre decisiones",
            "abstraction": "conceptos abstractos y principios",
            "external_integration": "contexto del mundo exterior",
            "probabilistic": "predicciones probabilísticas",
            "creativity": "generación de ideas creativas",
            "self_improvement": "mejora de código propio",
            "temporal": "conciencia temporal y causalidad",
        }

        # Validar que no haya solapamiento excesivo
        # (ya manejado por ConflictDetector y ConflictResolver)

        return contexts

    def get_conflict_summary(self) -> str:
        """Obtener resumen de conflictos detectados."""
        if not self.conflict_detector.conflict_log:
            return "No hay conflictos registrados."

        summary_parts = ["RESUMEN DE CONFLICTOS:"]
        summary_parts.append(f"- Total: {len(self.conflict_detector.conflict_log)}")

        # Contar por severidad
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for conflict in self.conflict_detector.conflict_log:
            severity = conflict.get("severity", "low")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        summary_parts.append(f"- Alta severidad: {severity_counts['high']}")
        summary_parts.append(f"- Media severidad: {severity_counts['medium']}")
        summary_parts.append(f"- Baja severidad: {severity_counts['low']}")

        return "\n".join(summary_parts)

    def get_unified_context(self) -> str:
        """Obtener contexto unificado para el system prompt."""
        return self.generate_unified_context()


# Singleton
_ura_unified_context: URAUnifiedContext | None = None


def get_ura_unified_context() -> URAUnifiedContext:
    """Obtener el singleton del contexto unificado."""
    global _ura_unified_context
    if _ura_unified_context is None:
        _ura_unified_context = URAUnifiedContext()
    return _ura_unified_context


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    context = get_ura_unified_context()

    # Prueba
    unified = context.get_unified_context()

    logger.info("Contexto unificado creado")
    logger.info(unified)
