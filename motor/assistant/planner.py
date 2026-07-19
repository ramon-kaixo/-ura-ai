"""ConversationalPlanner — planificador conversacional (F29 B5).

Traduce intención del usuario en objetivos, tareas y siguiente acción.
Reutiliza F27 AgentPlanner para la planificación interna.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from motor.assistant.models import ConversationMode, UserIntent


@dataclass
class PlanTask:
    id: str = ""
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    estimated_effort: str = "medium"
    status: str = "pending"


@dataclass
class ConversationalPlan:
    plan_id: str = ""
    objective: str = ""
    tasks: list[PlanTask] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_action: str = ""
    confidence: float = 1.0
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


_INTENT_PLANS: dict[UserIntent, tuple[str, str, list[str]]] = {
    UserIntent.GREETING: (
        "Iniciar conversación",
        "responder con un saludo cordial",
        [],
    ),
    UserIntent.FAREWELL: (
        "Cerrar conversación",
        "despedirse cordialmente y ofrecer ayuda futura",
        [],
    ),
    UserIntent.QUESTION: (
        "Responder pregunta",
        "analizar la pregunta, buscar información relevante y responder con precisión",
        ["riesgo de información incompleta", "riesgo de ambigüedad en la pregunta"],
    ),
    UserIntent.COMMAND: (
        "Ejecutar comando",
        "interpretar el comando, seleccionar herramienta adecuada y ejecutar",
        ["riesgo de comando mal interpretado", "riesgo de permisos insuficientes"],
    ),
    UserIntent.CLARIFY: (
        "Aclarar duda",
        "identificar qué necesita aclaración y proporcionar contexto adicional",
        [],
    ),
    UserIntent.CONFIRM: (
        "Confirmar acción",
        "registrar confirmación y proceder con la siguiente acción planificada",
        [],
    ),
    UserIntent.REJECT: (
        "Manejar rechazo",
        "entender por qué se rechazó y ofrecer alternativas",
        [],
    ),
    UserIntent.CORRECT: (
        "Corregir error",
        "identificar el error, disculpar y proporcionar la información correcta",
        [],
    ),
    UserIntent.REPEAT: (
        "Repetir respuesta",
        "reformular la respuesta anterior de forma más clara",
        [],
    ),
}


class ConversationalPlanner:
    def __init__(self) -> None:
        self._plans: dict[str, ConversationalPlan] = {}

    def create_plan(
        self,
        user_message: str,
        intent: UserIntent,
        mode: ConversationMode = ConversationMode.CONVERSATION,
        conversation_history: str = "",
    ) -> ConversationalPlan:
        plan_data = _INTENT_PLANS.get(intent)
        if plan_data is None:
            plan_data = (user_message, "responder de forma natural", [])

        objective, first_task_desc, risks = plan_data
        if intent == UserIntent.CHAT and len(user_message) > 50:
            objective = user_message

        task = PlanTask(description=first_task_desc, estimated_effort="low")
        next_action = self._determine_next_action(intent, mode)

        plan = ConversationalPlan(
            objective=objective,
            tasks=[task],
            risks=risks,
            next_action=next_action,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> ConversationalPlan | None:
        return self._plans.get(plan_id)

    def update_plan(self, plan_id: str, **kwargs: Any) -> ConversationalPlan | None:
        plan = self._plans.get(plan_id)
        if plan is None:
            return None
        for key, value in kwargs.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        return plan

    def _determine_next_action(self, intent: UserIntent, mode: ConversationMode) -> str:
        if intent == UserIntent.QUESTION:
            return "buscar información y formular respuesta"
        if intent == UserIntent.COMMAND:
            return "ejecutar la herramienta adecuada"
        if intent == UserIntent.CLARIFY:
            return "preguntar qué necesita aclaración"
        if intent == UserIntent.CONFIRM:
            return "continuar con la siguiente tarea"
        if intent == UserIntent.REJECT:
            return "preguntar qué alternativa prefiere"
        if intent == UserIntent.CORRECT:
            if mode == ConversationMode.EXPLANATION:
                return "explicar el error y cómo evitarlo"
            return "confirmar la corrección y disculparse"
        if intent == UserIntent.REPEAT:
            return "reformular la respuesta anterior"
        if mode == ConversationMode.EXPLANATION:
            return "continuar con la explicación"
        if mode == ConversationMode.WORK:
            return "esperar siguiente instrucción"
        return "continuar la conversación"

    def assess_risks(self, plan_id: str) -> list[str]:
        plan = self._plans.get(plan_id)
        if plan is None:
            return []
        return plan.risks
