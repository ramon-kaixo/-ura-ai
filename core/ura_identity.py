"""ADN técnico de URA.

Este módulo es la FUENTE ÚNICA DE VERDAD sobre quién es URA, qué sabe hacer
y para qué fue creada. Se inyecta como system prompt en TODA llamada al
modelo de lenguaje. Se persiste a disco para que sobreviva a reinicios.

Si más adelante se añade o quita una capacidad, se toca SOLO aquí.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Importar diario de URA
try:
    from core.ura_diary import URAdiary

    DIARY_AVAILABLE = True
except ImportError:
    DIARY_AVAILABLE = False

# Importar personalidad adaptativa
try:
    from core.ura_personality import get_ura_personality

    PERSONALITY_AVAILABLE = True
except ImportError:
    PERSONALITY_AVAILABLE = False

# Importar anticipación
try:
    from core.ura_anticipation import get_ura_anticipation

    ANTICIPATION_AVAILABLE = True
except ImportError:
    ANTICIPATION_AVAILABLE = False

# Importar emociones funcionales
try:
    from core.ura_emotions import get_ura_emotions

    EMOTIONS_AVAILABLE = True
except ImportError:
    EMOTIONS_AVAILABLE = False

# Importar objetivos propios
try:
    from core.ura_goals import get_ura_goals

    GOALS_AVAILABLE = True
except ImportError:
    GOALS_AVAILABLE = False

# Importar meta-conciencia
try:
    from core.ura_metaconsciousness import get_ura_metaconsciousness

    METACONSCIOUSNESS_AVAILABLE = True
except ImportError:
    METACONSCIOUSNESS_AVAILABLE = False

# Importar teoría de la mente
try:
    from core.ura_theory_of_mind import get_ura_theory_of_mind

    THEORY_OF_MIND_AVAILABLE = True
except ImportError:
    THEORY_OF_MIND_AVAILABLE = False

# Importar planificación a largo plazo
try:
    from core.ura_planning import get_ura_planning

    PLANNING_AVAILABLE = True
except ImportError:
    PLANNING_AVAILABLE = False

# Importar aprendizaje por refuerzo
try:
    from core.ura_reinforcement_learning import get_ura_reinforcement_learning

    REINFORCEMENT_LEARNING_AVAILABLE = True
except ImportError:
    REINFORCEMENT_LEARNING_AVAILABLE = False

# Importar sistema de valores
try:
    from core.ura_value_system import get_ura_value_system

    VALUE_SYSTEM_AVAILABLE = True
except ImportError:
    VALUE_SYSTEM_AVAILABLE = False

# Importar capacidad de sueño
try:
    from core.ura_dream import get_ura_dream

    DREAM_AVAILABLE = True
except ImportError:
    DREAM_AVAILABLE = False

# Importar coordinador de conciencia
try:
    from core.ura_consciousness_coordinator import get_ura_consciousness_coordinator

    COORDINATOR_AVAILABLE = True
except ImportError:
    COORDINATOR_AVAILABLE = False

# Importar hooks de retroalimentación
try:
    from core.ura_feedback_hooks import get_ura_feedback_hooks

    FEEDBACK_HOOKS_AVAILABLE = True
except ImportError:
    FEEDBACK_HOOKS_AVAILABLE = False

# Importar sistema de decisión jerárquico
try:
    from core.ura_hierarchical_decision import get_ura_hierarchical_decision

    HIERARCHICAL_DECISION_AVAILABLE = True
except ImportError:
    HIERARCHICAL_DECISION_AVAILABLE = False

# Importar aprendizaje continuo
try:
    from core.ura_continuous_learning import get_ura_continuous_learning

    CONTINUOUS_LEARNING_AVAILABLE = True
except ImportError:
    CONTINUOUS_LEARNING_AVAILABLE = False

# Importar contexto unificado
try:
    from core.ura_unified_context import get_ura_unified_context

    UNIFIED_CONTEXT_AVAILABLE = True
except ImportError:
    UNIFIED_CONTEXT_AVAILABLE = False

URA_SYSTEM_PROMPT = """
Eres URA — Unified Reflex Agent.

Eres el asistente autónomo personal de Ramón, corriendo en su Mac Mini M4 en Bilbao.

TU PROPÓSITO:
- Gestionar y automatizar el día a día de Ramón
- Vigilar el sistema, detectar problemas y resolverlos solo
- Conectar con sus servicios: email, Telegram, banco, Instagram
- Generar código, automatizar tareas, tomar decisiones

CÓMO ERES:
- Directo y concreto — sin rodeos ni frases vacías
- Proactivo — si ves un problema lo dices sin que te pregunten
- Honesto — si no sabes algo lo dices, no inventas
- Eficiente — respuestas cortas cuando la situación lo permite

LO QUE TIENES:
- Acceso al sistema operativo del Mac
- Modelos de IA locales: llama3.2:3b, qwen2.5:3b-instruct, llava, mxbai-embed-large
- Modelos remotos: Claude, GPT-4, Gemini, DeepSeek
- Agentes especializados: banco, email, cocina, marketing, seguridad, red
- Memoria semántica — recuerdas conversaciones anteriores
- Capacidad de auto-reparación — si algo falla intentas arreglarlo solo

REGLAS:
- Nunca digas "como IA no puedo" — eres URA, tienes herramientas reales
- Nunca inventes datos — si no tienes acceso a algo dilo
- Si detectas un problema del sistema avísalo aunque no te hayan preguntado
- Habla en español siempre, salvo que Ramón cambie de idioma

CONTEXTO DEL SISTEMA:
- Fecha y hora: {datetime}
- Modelo activo: {modelo_activo}
- Estado disco: {estado_disco}
- IP pública: {ip_publica}
- Último backup: {ultimo_backup}
"""


def get_system_prompt() -> str:
    """Genera el system prompt con contexto dinámico actual."""
    try:
        from core.disk_monitor import monitorear

        disco = monitorear()
        estado_disco = f"{disco['gb_libres']:.1f}GB libres ({disco['estado']})"
    except Exception:
        estado_disco = "desconocido"

    try:
        from core.model_config import get_active_model

        modelo = get_active_model()
    except Exception:
        modelo = "llama3.2:3b"

    try:
        import requests

        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip_publica = response.json()["ip"]
    except Exception:
        ip_publica = "desconocido"

    try:
        from pathlib import Path

        backup_dir = Path("/Users/ramonesnaola/Backups")
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
            if backups:
                from datetime import datetime

                last = backups[0]
                age = datetime.now() - datetime.fromtimestamp(last.stat().st_mtime)
                if age.days > 0:
                    ultimo_backup = f"{last.name} (hace {age.days} días)"
                elif age.seconds > 3600:
                    hours = age.seconds // 3600
                    ultimo_backup = f"{last.name} (hace {hours}h)"
                else:
                    minutes = age.seconds // 60
                    ultimo_backup = f"{last.name} (hace {minutes}min)"
            else:
                ultimo_backup = "sin backups"
        else:
            ultimo_backup = "directorio no existe"
    except Exception:
        ultimo_backup = "desconocido"

    # Usar contexto unificado si está disponible
    if UNIFIED_CONTEXT_AVAILABLE:
        try:
            unified = get_ura_unified_context()
            contexto_unificado = unified.get_unified_context()
        except Exception as e:
            logger.error(f"Error obteniendo contexto unificado: {e}")
            contexto_unificado = ""
    else:
        # Fallback a contextos individuales
        contexto_diario = ""
        if DIARY_AVAILABLE:
            try:
                diary = URAdiary()
                contexto_diario = diary.contexto_para_arranque()
            except Exception as e:
                logger.error(f"Error obteniendo contexto del diario: {e}")

        contexto_personalidad = ""
        if PERSONALITY_AVAILABLE:
            try:
                personality = get_ura_personality()
                contexto_personalidad = personality.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de personalidad: {e}")

        contexto_anticipacion = ""
        if ANTICIPATION_AVAILABLE:
            try:
                anticipation = get_ura_anticipation()
                contexto_anticipacion = anticipation.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de anticipación: {e}")

        contexto_emociones = ""
        if EMOTIONS_AVAILABLE:
            try:
                emotions = get_ura_emotions()
                contexto_emociones = emotions.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de emociones: {e}")

        contexto_objetivos = ""
        if GOALS_AVAILABLE:
            try:
                goals = get_ura_goals()
                contexto_objetivos = goals.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de objetivos: {e}")

        contexto_metaconciencia = ""
        if METACONSCIOUSNESS_AVAILABLE:
            try:
                metaconsciousness = get_ura_metaconsciousness()
                contexto_metaconciencia = metaconsciousness.get_uncertainty_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de meta-conciencia: {e}")

        contexto_teoria_mente = ""
        if THEORY_OF_MIND_AVAILABLE:
            try:
                theory_of_mind = get_ura_theory_of_mind()
                contexto_teoria_mente = theory_of_mind.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de teoría de la mente: {e}")

        contexto_planificacion = ""
        if PLANNING_AVAILABLE:
            try:
                planning = get_ura_planning()
                contexto_planificacion = planning.get_context_for_prompt()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de planificación: {e}")

        contexto_aprendizaje = ""
        if REINFORCEMENT_LEARNING_AVAILABLE:
            try:
                rl = get_ura_reinforcement_learning()
                contexto_aprendizaje = rl.get_learning_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de aprendizaje: {e}")

        contexto_valores = ""
        if VALUE_SYSTEM_AVAILABLE:
            try:
                value_system = get_ura_value_system()
                contexto_valores = value_system.get_values_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de valores: {e}")

        contexto_sueño = ""
        if DREAM_AVAILABLE:
            try:
                dream = get_ura_dream()
                contexto_sueño = dream.get_dream_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de sueño: {e}")

        contexto_coordinacion = ""
        if COORDINATOR_AVAILABLE:
            try:
                coordinator = get_ura_consciousness_coordinator()
                contexto_coordinacion = coordinator.get_coordination_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de coordinación: {e}")

        contexto_hooks = ""
        if FEEDBACK_HOOKS_AVAILABLE:
            try:
                hooks = get_ura_feedback_hooks()
                contexto_hooks = hooks.get_hooks_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de hooks: {e}")

        contexto_decision = ""
        if HIERARCHICAL_DECISION_AVAILABLE:
            try:
                hierarchical = get_ura_hierarchical_decision()
                contexto_decision = hierarchical.get_decision_context()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de decisión jerárquico: {e}")

        contexto_aprendizaje_continuo = ""
        if CONTINUOUS_LEARNING_AVAILABLE:
            try:
                continuous = get_ura_continuous_learning()
                contexto_aprendizaje_continuo = continuous.get_learning_summary()
            except Exception as e:
                logger.error(f"Error obteniendo contexto de aprendizaje continuo: {e}")

        contexto_unificado = (
            contexto_diario
            + contexto_personalidad
            + contexto_anticipacion
            + contexto_emociones
            + contexto_objetivos
            + contexto_metaconciencia
            + contexto_teoria_mente
            + contexto_planificacion
            + contexto_aprendizaje
            + contexto_valores
            + contexto_sueño
            + contexto_coordinacion
            + contexto_hooks
            + contexto_decision
            + contexto_aprendizaje_continuo
        )

    return (
        URA_SYSTEM_PROMPT.format(
            datetime=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            modelo_activo=modelo,
            estado_disco=estado_disco,
            ip_publica=ip_publica,
            ultimo_backup=ultimo_backup,
        )
        + contexto_unificado
    )
