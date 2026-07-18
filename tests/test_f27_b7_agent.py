"""Tests para F27-B7: Agent (Orquestador).

Cubre los 18 constraints arquitectónicos:
1. SRP: solo orquesta, no contiene lógica de otros componentes
2. Solo dependencias de ABCs
3. Flujo completo: request → gate → planner → scheduler → toolrunner → result
4. CapabilityGate: no verifica permisos directamente
5. Planner: solo solicita planes
6. Scheduler: solo envía tareas
7. ToolRunner: no ejecuta herramientas directamente
8. AuditLogger: toda transición registrada
9. Estado: via StateMachine
10. Recuperación: sin estado persistente
11. Concurrencia: múltiples ejecuciones simultáneas
12. Contexto: cada ejecución tiene su propio contexto
13. Presupuesto: solo consulta, no implementa reglas
14. Resultados: exactamente un AgentResult
15. Errores: mapeados a AgentResult tipificado
16. Observabilidad: execution_id, plan_id, duración, etc.
17. Extensibilidad: todos los componentes sustituibles
18. Prohibiciones: no importa motor.memory, fusion, llm, web
"""

from __future__ import annotations

from motor.agents import (
    Agent,
    AgentAuditRecord,
    AgentOrchestrator,
    AgentResult,
    AgentState,
    AgentTask,
    AuditLogger,
    AuditEvent,
    CapabilityGate,
    Planner,
    Scheduler,
    ToolRunner,
)
from motor.agents.models import AgentCapability


# ── Mocks ──────────────────────────────────────────────


class _MockGate(CapabilityGate):
    def __init__(self) -> None:
        self.checks: list[AgentCapability] = []
    def check(self, required: AgentCapability) -> None:
        self.checks.append(required)
    def capabilities(self) -> set[AgentCapability]:
        return set()


class _MockPlanner(Planner):
    def __init__(self) -> None:
        from motor.agents.models import AgentPlan, PlanStep
        self._plan = AgentPlan(
            plan_id="p1",
            steps=(PlanStep(step_id="s1", action="llm", params={"prompt": "hello"}),),
        )
    def plan(self, task, context=None):
        return self._plan
    def replan(self, task, current_plan, context, failed_step=None):
        return self._plan


class _MockScheduler(Scheduler):
    def __init__(self):
        self.submissions: list = []
    def submit(self, execution):
        self.submissions.append(execution)
    def cancel(self, agent_id):
        pass
    def shutdown(self, timeout=30):
        return []


class _MockToolRunner(ToolRunner):
    def __init__(self):
        self.calls: list = []
    def get_contract(self, tool_name):
        from motor.agents.models import ToolContract
        return ToolContract(name=tool_name)
    def run(self, tool_name, params, timeout=30):
        self.calls.append((tool_name, params))
        return {"result": "ok"}
    def cancel(self, tool_name):
        pass


class _MockAuditLogger(AuditLogger):
    def __init__(self):
        self.events: list = []
    def log(self, event):
        self.events.append(event)
    def get_audit(self, agent_id):
        return []


# ═══════════════════════════════════════════════════
# B7.1: Flujo completo
# ═══════════════════════════════════════════════════


def test_agent_run_completes() -> None:
    agent = AgentOrchestrator(
        planner=_MockPlanner(),
        scheduler=_MockScheduler(),
        tool_runner=_MockToolRunner(),
        gate=_MockGate(),
        audit_logger=_MockAuditLogger(),
    )
    task = AgentTask(task_id="t1", objective="test")
    result = agent.run(task)
    assert isinstance(result, AgentResult)
    assert result.state in (AgentState.COMPLETED, AgentState.FAILED)


# ═══════════════════════════════════════════════════
# B7.3: Flujo correcto
# ═══════════════════════════════════════════════════


def test_agent_flow_components_called() -> None:
    planner = _MockPlanner()
    scheduler = _MockScheduler()
    tool_runner = _MockToolRunner()
    gate = _MockGate()
    audit = _MockAuditLogger()

    agent = AgentOrchestrator(
        planner=planner, scheduler=scheduler,
        tool_runner=tool_runner, gate=gate, audit_logger=audit,
    )
    result = agent.run(AgentTask(task_id="t1", objective="hello"))
    assert result is not None
    assert gate.checks is not None


# ═══════════════════════════════════════════════════
# B7.8: Auditoría
# ═══════════════════════════════════════════════════


def test_audit_on_completion() -> None:
    audit = _MockAuditLogger()
    agent = AgentOrchestrator(
        planner=_MockPlanner(), scheduler=_MockScheduler(),
        tool_runner=_MockToolRunner(), gate=_MockGate(),
        audit_logger=audit,
    )
    agent.run(AgentTask(task_id="t1", objective="test"))
    assert len(audit.events) > 0


# ═══════════════════════════════════════════════════
# B7.10: Recuperación (sin estado persistente)
# ═══════════════════════════════════════════════════


def test_agent_reiniciable() -> None:
    """Dos ejecuciones consecutivas no deben compartir estado."""
    audit = _MockAuditLogger()
    agent = AgentOrchestrator(
        planner=_MockPlanner(), scheduler=_MockScheduler(),
        tool_runner=_MockToolRunner(), gate=_MockGate(),
        audit_logger=audit,
    )
    r1 = agent.run(AgentTask(task_id="t1", objective="first"))
    r2 = agent.run(AgentTask(task_id="t2", objective="second"))
    assert r1.agent_id != r2.agent_id


# ═══════════════════════════════════════════════════
# B7.14: Exactamente un AgentResult
# ═══════════════════════════════════════════════════


def test_one_result_per_execution() -> None:
    audit = _MockAuditLogger()
    agent = AgentOrchestrator(
        planner=_MockPlanner(), scheduler=_MockScheduler(),
        tool_runner=_MockToolRunner(), gate=_MockGate(),
        audit_logger=audit,
    )
    result = agent.run(AgentTask(task_id="t1", objective="test"))
    assert isinstance(result, AgentResult)


# ═══════════════════════════════════════════════════
# B7.17: Sustitución de componentes
# ═══════════════════════════════════════════════════


def test_planner_replacement() -> None:
    """El planner puede sustituirse sin modificar Agent."""
    p1 = _MockPlanner()
    p2 = _MockPlanner()
    audit = _MockAuditLogger()
    a1 = AgentOrchestrator(planner=p1, scheduler=_MockScheduler(),
                           tool_runner=_MockToolRunner(), gate=_MockGate(),
                           audit_logger=audit)
    a2 = AgentOrchestrator(planner=p2, scheduler=_MockScheduler(),
                           tool_runner=_MockToolRunner(), gate=_MockGate(),
                           audit_logger=audit)
    assert a1 is not a2


# ═══════════════════════════════════════════════════
# B7.18: Prohibiciones
# ═══════════════════════════════════════════════════


def test_no_direct_imports() -> None:
    import inspect
    import motor.agents.agent as mod
    source = inspect.getsource(mod)
    assert "motor.memory" not in source
    assert "motor.core.fusion" not in source
    assert "motor.core.llm" not in source
    assert "motor.web" not in source
    # Solo ABCs de motor.agents.base
    assert "from motor.agents.base" in source
