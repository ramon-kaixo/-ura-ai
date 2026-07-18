"""F27 — Contratos abstractos de Agentes.

ABCs para todos los componentes del sistema de agentes.
Ninguna lógica de implementación. Solo interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.agents.models import (
        AgentCapability,
        AgentContext,
        AgentExecution,
        AgentPlan,
        AgentResult,
        AgentState,
        AgentTask,
        AuditEvent,
        PlanStep,
        ToolContract,
    )


class CapabilityGate(ABC):
    """Gateway único de autorización.

    Toda operación de un agente sobre la plataforma pasa por aquí.
    Ningún otro componente consulta permisos directamente.
    """

    @abstractmethod
    def check(self, required: AgentCapability) -> None:
        """Verifica que la capability está concedida.

        Lanza PermissionError si no está concedida.
        """
        ...

    @abstractmethod
    def capabilities(self) -> set[AgentCapability]:
        """Retorna el conjunto de capabilities concedidas."""
        ...


class Planner(ABC):
    """Genera un plan a partir de un objetivo.

    No ejecuta pasos. No consulta herramientas.
    Solo genera secuencias de pasos.
    """

    @abstractmethod
    def plan(self, task: AgentTask, context: AgentContext | None = None) -> AgentPlan:
        """Genera un plan para alcanzar el objetivo."""
        ...

    @abstractmethod
    def replan(
        self,
        task: AgentTask,
        current_plan: AgentPlan,
        context: AgentContext,
        failed_step: PlanStep | None = None,
    ) -> AgentPlan:
        """Genera un nuevo plan conservando pasos completados."""
        ...


class Executor(ABC):
    """Ejecuta un plan paso a paso.

    No planifica. No autoriza. Solo ejecuta.
    """

    @abstractmethod
    def execute_step(
        self,
        step: PlanStep,
        context: AgentContext,
        gate: CapabilityGate,
    ) -> AgentContext:
        """Ejecuta un paso del plan y retorna el contexto actualizado."""
        ...

    @abstractmethod
    def execute_plan(
        self,
        plan: AgentPlan,
        context: AgentContext,
        gate: CapabilityGate,
        execution: AgentExecution,
    ) -> AgentContext:
        """Ejecuta todos los pasos del plan secuencialmente."""
        ...


class ToolRunner(ABC):
    """Ejecuta herramientas de forma encapsulada.

    Gestiona timeout, cancelación, reintentos, errores, medición y auditoría.
    Las herramientas nunca se invocan directamente desde Agent o Executor.
    """

    @abstractmethod
    def get_contract(self, tool_name: str) -> ToolContract:
        """Retorna el contrato de una herramienta."""
        ...

    @abstractmethod
    def run(
        self,
        tool_name: str,
        params: dict,
        timeout: int = 30,
    ) -> dict:
        """Ejecuta una herramienta y retorna su resultado."""
        ...

    @abstractmethod
    def cancel(self, tool_name: str) -> None:
        """Cancela una herramienta en ejecución."""
        ...


class Scheduler(ABC):
    """Gestiona la cola de ejecución de agentes.

    No conoce Memory, Knowledge, LLM ni Tools.
    Solo gestiona AgentExecution.
    """

    @abstractmethod
    def submit(self, execution: AgentExecution) -> None:
        """Añade una ejecución a la cola."""
        ...

    @abstractmethod
    def cancel(self, agent_id: str) -> None:
        """Cancela una ejecución en curso o en cola."""
        ...

    @abstractmethod
    def shutdown(self, timeout: int = 30) -> list[AgentResult]:
        """Detiene el scheduler y retorna los resultados pendientes."""
        ...


class Agent(ABC):
    """Orquestador de la ejecución de un agente.

    No contiene lógica de planificación, autorización,
    persistencia ni ejecución de herramientas.
    Coordina Planner, Executor, CapabilityGate y ToolRunner.
    """

    @abstractmethod
    def run(self, task: AgentTask) -> AgentResult:
        """Ejecuta una tarea y retorna el resultado."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Cancela la ejecución en curso."""
        ...


class AuditLogger(ABC):
    """Registra eventos de auditoría.

    Todo cambio observable debe generar un evento.
    """

    @abstractmethod
    def log(self, event: AuditEvent) -> None:
        """Registra un evento de auditoría."""
        ...

    @abstractmethod
    def get_audit(self, agent_id: str) -> list[AuditEvent]:
        """Recupera los eventos de auditoría de un agente."""
        ...


class TaskQueue(ABC):
    """Abstracción de cola de tareas.

    No acoplada a una implementación concreta (PriorityQueue, Redis, etc.).
    """

    @abstractmethod
    def push(self, execution: AgentExecution, priority: int = 0) -> None:
        """Añade una ejecución a la cola con prioridad."""
        ...

    @abstractmethod
    def pop(self) -> AgentExecution | None:
        """Extrae la siguiente ejecución de la cola."""
        ...

    @abstractmethod
    def remove(self, agent_id: str) -> bool:
        """Elimina una ejecución de la cola por agent_id."""
        ...

    @abstractmethod
    def size(self) -> int:
        """Número de ejecuciones en cola."""
        ...


class ToolAdapter(ABC):
    """Adaptador para una herramienta concreta.

    ToolRunner nunca ejecuta herramientas directamente.
    Siempre a través de un ToolAdapter.
    """

    @abstractmethod
    def name(self) -> str:
        """Nombre único de la herramienta."""
        ...

    @abstractmethod
    def run(self, params: dict) -> dict:
        """Ejecuta la herramienta y retorna el resultado."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Cancela la ejecución en curso (cooperativa)."""
        ...


class StateMachine(ABC):
    """Máquina de estados explícita para AgentState.

    Valida todas las transiciones. No permite cambios arbitrarios.
    """

    @abstractmethod
    def transition(self, current: AgentState, target: AgentState) -> AgentState:
        """Valida y ejecuta una transición de estado.

        Lanza ValueError si la transición no es válida.
        """
        ...

    @abstractmethod
    def valid_transitions(self, state: AgentState) -> list[AgentState]:
        """Retorna los estados válidos desde el estado dado."""
        ...
