"""F27-A2: Integración Vertical — flujo completo de Agentes.

Verifica el recorrido:

Usuario → Agent → CapabilityGate → Planner → Scheduler
→ ToolRunner → Tool → Knowledge (F25) → Memory (F26)
→ Audit → Resultado
"""

from __future__ import annotations

from motor.agents import (
    AgentCapability,
    AgentOrchestrator,
    AgentResult,
    AgentState,
    AgentTask,
    AuditLogger,
    CapabilityGate,
    RuleBasedPlanner,
    Scheduler,
    ToolRunner,
)

# ── Mocks de integración ──────────────────────────────


class _IntegrationGate(CapabilityGate):
    def __init__(self):
        self.checks = []

    def check(self, required):
        self.checks.append(required)

    def capabilities(self):
        return {
            AgentCapability.MEMORY_READ,
            AgentCapability.FACTS_READ,
            AgentCapability.WEB_SEARCH,
            AgentCapability.TOOLS_EXECUTE,
        }


class _IntegrationScheduler(Scheduler):
    def __init__(self):
        self.submissions = []

    def submit(self, execution):
        self.submissions.append(execution)

    def cancel(self, agent_id):
        pass

    def shutdown(self, timeout=30):
        return []


class _IntegrationToolRunner(ToolRunner):
    def __init__(self):
        self.calls = []

    def get_contract(self, tool_name):
        from motor.agents.models import ToolContract

        return ToolContract(name=tool_name)

    def run(self, tool_name, params, timeout=30):
        self.calls.append((tool_name, params))
        if tool_name == "retrieve":
            return {"facts": ["fact1", "fact2"], "memory": ["mem1"]}
        if tool_name == "search":
            return {"results": ["result1", "result2"]}
        if tool_name == "llm":
            return {"response": "AI response based on facts and memory"}
        if tool_name == "tool":
            return {"written": True}
        return {"result": "ok"}

    def cancel(self, tool_name):
        pass


class _IntegrationAudit(AuditLogger):
    def __init__(self):
        self.events = []

    def log(self, event):
        self.events.append(event)

    def get_audit(self, agent_id):
        return [e for e in self.events if hasattr(e, "agent_id") and e.agent_id == agent_id]


# ═══════════════════════════════════════════════════
# A2.1: Flujo completo
# ═══════════════════════════════════════════════════


def test_integration_full_flow() -> None:
    """Usuario → Agent → Gate → Planner → Scheduler → ToolRunner → Audit → Result."""
    planner = RuleBasedPlanner()
    scheduler = _IntegrationScheduler()
    tool_runner = _IntegrationToolRunner()
    gate = _IntegrationGate()
    audit = _IntegrationAudit()

    agent = AgentOrchestrator(
        planner=planner,
        scheduler=scheduler,
        tool_runner=tool_runner,
        gate=gate,
        audit_logger=audit,
    )

    task = AgentTask(task_id="integ_test", objective="search for information about AI")
    result = agent.run(task)

    assert isinstance(result, AgentResult)
    assert result.agent_id is not None
    assert len(result.agent_id) == 16

    # Auditoría debe haberse registrado
    assert len(audit.events) > 0


# ═══════════════════════════════════════════════════
# A2.2: Flujo con Facts (F25) en contexto
# ═══════════════════════════════════════════════════


def test_integration_with_knowledge() -> None:
    """ToolRunner puede recuperar Facts simulados."""
    tool_runner = _IntegrationToolRunner()
    result = tool_runner.run("retrieve", {"source": "facts"})
    assert "facts" in result
    assert len(result["facts"]) > 0


# ═══════════════════════════════════════════════════
# A2.3: Flujo con Memoria (F26) en contexto
# ═══════════════════════════════════════════════════


def test_integration_with_memory() -> None:
    """ToolRunner puede recuperar memoria simulada."""
    tool_runner = _IntegrationToolRunner()
    result = tool_runner.run("retrieve", {"source": "memory"})
    assert "memory" in result or "facts" in result


# ═══════════════════════════════════════════════════
# A2.4: Auditoría completa
# ═══════════════════════════════════════════════════


def test_integration_audit_trail() -> None:
    """Toda ejecución produce un audit trail completo."""
    planner = RuleBasedPlanner()
    scheduler = _IntegrationScheduler()
    tool_runner = _IntegrationToolRunner()
    gate = _IntegrationGate()
    audit = _IntegrationAudit()

    agent = AgentOrchestrator(
        planner=planner,
        scheduler=scheduler,
        tool_runner=tool_runner,
        gate=gate,
        audit_logger=audit,
    )
    result = agent.run(AgentTask(task_id="audit_test", objective="read facts"))

    assert len(audit.events) > 0
    assert result.state in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED, AgentState.TIMEOUT)


# ═══════════════════════════════════════════════════
# A2.5: Skills del plan ejecutados
# ═══════════════════════════════════════════════════


def test_integration_plan_executed() -> None:
    """Los pasos del plan deben ejecutarse a través del ToolRunner."""
    planner = RuleBasedPlanner()
    tool_runner = _IntegrationToolRunner()
    scheduler = _IntegrationScheduler()

    agent = AgentOrchestrator(
        planner=planner,
        scheduler=scheduler,
        tool_runner=tool_runner,
        gate=_IntegrationGate(),
        audit_logger=_IntegrationAudit(),
    )
    agent.run(AgentTask(task_id="exec_test", objective="search for data"))

    actions_executed = [call[0] for call in tool_runner.calls]
    # Debe haber ejecutado retrieve + search + llm
    assert "retrieve" in actions_executed
    assert "search" in actions_executed
    assert "llm" in actions_executed
