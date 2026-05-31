#!/usr/bin/env python3
"""
Hooks de Retroalimentación de URA - Integración Máxima

Sistema de hooks para comunicación entre niveles:
- Cada respuesta actualiza múltiples niveles
- El diario nocturno consolida información
- Los sueños conectan insights de diferentes niveles
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HOOKS_PATH = Path.home() / ".ura" / "feedback_hooks.json"
HOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class FeedbackHook:
    """Hook de retroalimentación."""

    hook_name: str
    trigger_event: str  # response, error, success, user_feedback
    target_levels: list[str]  # Qué niveles actualizar
    action: str  # Qué acción ejecutar
    last_triggered: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FeedbackHook":
        return cls(**data)


class URAFeedbackHooks:
    """Gestor de hooks de retroalimentación de URA."""

    def __init__(self):
        self.hooks = self._load_hooks()
        self.hook_log = []

    def _load_hooks(self) -> dict[str, FeedbackHook]:
        """Cargar hooks desde disco."""
        hooks = {}
        if HOOKS_PATH.exists():
            try:
                with open(HOOKS_PATH) as f:
                    data = json.load(f)
                    hooks = {
                        h["hook_name"]: FeedbackHook.from_dict(h) for h in data.get("hooks", [])
                    }
            except Exception as e:
                logger.error(f"Error cargando hooks: {e}")

        # Si no hay hooks, crear los por defecto
        if not hooks:
            hooks = self._create_default_hooks()

        return hooks

    def _create_default_hooks(self) -> dict[str, FeedbackHook]:
        """Crear hooks por defecto."""
        now = datetime.now().isoformat()
        return {
            "response_hook": FeedbackHook(
                hook_name="response_hook",
                trigger_event="response",
                target_levels=["personality", "reinforcement_learning", "theory_of_mind"],
                action="update_from_response",
                last_triggered=now,
            ),
            "error_hook": FeedbackHook(
                hook_name="error_hook",
                trigger_event="error",
                target_levels=["metaconsciousness", "reinforcement_learning", "emotions"],
                action="record_error_and_learn",
                last_triggered=now,
            ),
            "success_hook": FeedbackHook(
                hook_name="success_hook",
                trigger_event="success",
                target_levels=["reinforcement_learning", "emotions", "anticipation"],
                action="reinforce_success_pattern",
                last_triggered=now,
            ),
            "user_feedback_hook": FeedbackHook(
                hook_name="user_feedback_hook",
                trigger_event="user_feedback",
                target_levels=["personality", "reinforcement_learning", "value_system"],
                action="process_user_feedback",
                last_triggered=now,
            ),
            "nightly_hook": FeedbackHook(
                hook_name="nightly_hook",
                trigger_event="nightly",
                target_levels=["diary", "dream", "goals", "metaconsciousness"],
                action="consolidate_daily_learning",
                last_triggered=now,
            ),
        }

    def _save_hooks(self):
        """Guardar hooks a disco."""
        with open(HOOKS_PATH, "w") as f:
            json.dump({"hooks": [h.to_dict() for h in self.hooks.values()]}, f, indent=2)

    def trigger_hook(self, event: str, data: dict):
        """Activar hooks para un evento específico."""
        triggered_hooks = []

        for hook in self.hooks.values():
            if hook.trigger_event == event:
                # Ejecutar acción en niveles objetivo
                for level in hook.target_levels:
                    self._execute_hook_action(level, hook.action, data)

                hook.last_triggered = datetime.now().isoformat()
                triggered_hooks.append(hook.hook_name)

        self._save_hooks()

        # Registrar en log
        self.hook_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "triggered_hooks": triggered_hooks,
            }
        )

        return triggered_hooks


def _execute_hook_action(self, level: str, action: str, data: dict):
    """Ejecutar acción en un nivel específico."""
    try:
        self._import_level(level)
        if action == "update_from_response":
            self._handle_update_from_response(data)
        elif action == "record_error_and_learn":
            self._handle_record_error_and_learn(data)
        elif action == "reinforce_success_pattern":
            self._handle_reinforce_success_pattern(data)
        elif action == "process_user_feedback":
            self._handle_process_user_feedback(data)
        elif action == "consolidate_daily_learning":
            self._handle_consolidate_daily_learning(data)
    except Exception as e:
        logger.error(f"Error ejecutando hook action en {level}: {e}")


def _import_level(self, level: str):
    """Importar el nivel correspondiente."""
    level_map = {
        "personality": "core.ura_personality",
        "reinforcement_learning": "core.ura_reinforcement_learning",
        "theory_of_mind": "core.ura_theory_of_mind",
        "metaconsciousness": "core.ura_metaconsciousness",
        "emotions": "core.ura_emotions",
        "anticipation": "core.ura_anticipation",
        "value_system": "core.ura_value_system",
        "diary": "core.ura_diary",
        "dream": "core.ura_dream",
        "goals": "core.ura_goals",
    }

    if level not in level_map:
        return


def _handle_update_from_response(self, data: dict):
    """Manejar la acción 'update_from_response'."""
    personality = self._get_ura_personality()
    if "feedback" in data:
        personality.record_feedback(data["feedback"])


def _handle_record_error_and_learn(self, data: dict):
    """Manejar la acción 'record_error_and_learn'."""
    if level == "metaconsciousness":
        meta = self._get_ura_metaconsciousness()
        if "domain" in data:
            meta.record_knowledge(data["domain"], False, data.get("error", ""))
    elif level == "emotions":
        emotions = self._get_ura_emotions()
        emotions.set_emotion("cauto", 0.7, "Error detectado")
    elif level == "reinforcement_learning":
        rl = self._get_ura_reinforcement_learning()
        if "action" in data:
            rl.record_outcome(data["action"], False, -0.5, data.get("error", ""))


def _handle_reinforce_success_pattern(self, data: dict):
    """Manejar la acción 'reinforce_success_pattern'."""
    if level == "reinforcement_learning":
        rl = self._get_ura_reinforcement_learning()
        if "action" in data:
            rl.record_outcome(data["action"], True, 0.8)
    elif level == "emotions":
        emotions = self._get_ura_emotions()
        emotions.set_emotion("satisfecho", 0.8, "Éxito en acción")
    elif level == "anticipation":
        anticipation = self._get_ura_anticipation()
        if "action" in data:
            anticipation.record_action(data["action"])


def _handle_process_user_feedback(self, data: dict):
    """Manejar la acción 'process_user_feedback'."""
    personality = self._get_ura_personality()
    if "feedback" in data:
        personality.record_feedback(data["feedback"])
    elif level == "reinforcement_learning":
        rl = self._get_ura_reinforcement_learning()
        if "action" in data:
            reward = 0.8 if "positive" in data and data["positive"] else -0.3
            rl.record_outcome(data["action"], data.get("success", True), reward)


def _handle_consolidate_daily_learning(self, data: dict):
    """Manejar la acción 'consolidate_daily_learning'."""
    if level == "diary":
        diary = self._get_ura_diary()
        diary.escribir_entrada_diaria()
    elif level == "dream":
        dream = self._get_ura_dream()
        if "conversations" in data:
            dream.generate_nightly_insights(data["conversations"])
    elif level == "goals":
        goals = self._get_ura_goals()
        goals.record_learning("Consolidación nocturna")
    elif level == "metaconsciousness":
        meta = self._get_ura_metaconsciousness()
        meta.self_evaluate("Consolidación diaria", 0.7, "Procesamiento nocturno")


def _get_ura_personality(self):
    """Obtener el objeto de personalidad."""
    from core.ura_personality import get_ura_personality

    return get_ura_personality()


def _get_ura_theory_of_mind(self):
    """Obtener el objeto de teoría de la mente."""
    from core.ura_theory_of_mind import get_ura_theory_of_mind

    return get_ura_theory_of_mind()


def _get_ura_reinforcement_learning(self):
    """Obtener el objeto de aprendizaje por refuerzo."""
    from core.ura_reinforcement_learning import get_ura_reinforcement_learning

    return get_ura_reinforcement_learning()


def _get_ura_emotions(self):
    """Obtener el objeto de emociones."""
    from core.ura_emotions import get_ura_emotions

    return get_ura_emotions()


def _get_ura_anticipation(self):
    """Obtener el objeto de anticipación."""
    from core.ura_anticipation import get_ura_anticipation

    return get_ura_anticipation()


def _get_ura_value_system(self):
    """Obtener el objeto del sistema de valores."""
    from core.ura_value_system import get_ura_value_system

    return get_ura_value_system()


def _get_ura_diary(self):
    """Obtener el objeto del diario."""
    from core.ura_diary import URAdiary

    return URAdiary()


def _get_ura_dream(self):
    """Obtener el objeto de los sueños."""
    from core.ura_dream import get_ura_dream

    return get_ura_dream()


def _get_ura_goals(self):
    """Obtener el objeto de metas."""
    from core.ura_goals import get_ura_goals

    return get_ura_goals()


def _get_ura_metaconsciousness(self):
    """Obtener el objeto de metaconciencia."""
    from core.ura_metaconsciousness import get_ura_metaconsciousness

    return get_ura_metaconsciousness()

    def get_hooks_context(self) -> str:
        """Genera contexto de hooks para el system prompt."""
        active_hooks = list(self.hooks.values())

        context_parts = ["HOOKS DE RETROALIMENTACIÓN (comunicación entre niveles):"]
        for hook in active_hooks[:3]:
            context_parts.append(
                f"- {hook.hook_name}: {hook.trigger_event} → {', '.join(hook.target_levels[:3])}"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_feedback_hooks: URAFeedbackHooks | None = None


def get_ura_feedback_hooks() -> URAFeedbackHooks:
    """Obtener el singleton de hooks de retroalimentación de URA."""
    global _ura_feedback_hooks
    if _ura_feedback_hooks is None:
        _ura_feedback_hooks = URAFeedbackHooks()
    return _ura_feedback_hooks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hooks = get_ura_feedback_hooks()

    # Prueba
    hooks.trigger_hook("response", {"feedback": "hazlo más corto", "message": "esto es muy largo"})

    print("Hooks de retroalimentación creados")
    print(hooks.get_hooks_context())
