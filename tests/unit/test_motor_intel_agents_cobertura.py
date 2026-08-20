"""Cobertura 100x100 de motor/intelligence/agents (parte 1). TASK-20260820-007."""

from __future__ import annotations

import pytest

from motor.core.executor import ProcessResult
from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.message import AgentMessage, AgentResult, AgentRole, AgentStatus, AgentTask
from motor.intelligence.agents.researcher import ResearcherAgent
from motor.intelligence.agents.supervisor import MAX_RETRIES, SupervisorAgent
from motor.intelligence.agents.validator import ValidatorAgent

# ── message ──────────────────────────────────────────────────


def test_agent_message_defaults() -> None:
    m = AgentMessage(source="a", target="b", message_type="task", payload={"x": 1})
    assert m.id != ""
    assert m.timestamp != ""
    assert m.correlation_id == m.id


def test_agent_message_con_ids_explicitos() -> None:
    m = AgentMessage(source="a", target="b", message_type="status", payload={}, correlation_id="c1", id="i1", timestamp="t1")
    assert m.id == "i1"
    assert m.correlation_id == "c1"
    assert m.timestamp == "t1"


def test_agent_task_defaults() -> None:
    t = AgentTask(objective="haz algo")
    assert t.id != ""
    assert t.created_at != ""
    assert t.agent_role == AgentRole.EXECUTOR


def test_agent_task_con_id() -> None:
    t = AgentTask(objective="x", id="t1", created_at="c1", priority=5, timeout=30)
    assert t.id == "t1"
    assert t.created_at == "c1"


def test_agent_result_defaults() -> None:
    r = AgentResult(task_id="t", agent_id="a", success=True)
    assert r.id != ""
    assert r.output == {}


def test_agent_result_con_id() -> None:
    r = AgentResult(task_id="t", agent_id="a", success=True, id="r1")
    assert r.id == "r1"


def test_agent_role_valores() -> None:
    assert AgentRole.PLANNER.value == "planner"
    assert AgentRole.VALIDATOR.value == "validator"


def test_agent_status_valores() -> None:
    assert AgentStatus.ERROR.value == "error"
    assert AgentStatus.COMPLETED.value == "completed"


# ── base ─────────────────────────────────────────────────────


class _DummyAgent(Agent):
    def __init__(self) -> None:
        self.id = "d1"
        self.name = "dummy"
        self.role = AgentRole.EXECUTOR
        self.capabilities = ["run"]

    def run(self, task: AgentTask) -> AgentResult:
        return AgentResult(task_id=task.id, agent_id=self.id, success=True)


def test_agent_can_handle_rol_correcto() -> None:
    a = _DummyAgent()
    assert a.can_handle(AgentTask(objective="x", agent_role=AgentRole.EXECUTOR)) is True
    assert a.can_handle(AgentTask(objective="x", agent_role=AgentRole.PLANNER)) is False
    assert a.status == AgentStatus.IDLE


class _ConSuperRun(Agent):
    def __init__(self) -> None:
        self.id = "s1"
        self.name = "super-run"
        self.role = AgentRole.EXECUTOR
        self.capabilities = ["run"]

    def run(self, task: AgentTask) -> AgentResult:
        r = super().run(task)
        if r is None:
            return AgentResult(task_id=task.id, agent_id=self.id, success=True)
        return r


def test_agent_abstract_run_elipsis() -> None:
    a = _ConSuperRun()
    r = a.run(AgentTask(objective="x"))
    assert r.success is True


# ── validator ────────────────────────────────────────────────


def _task(input_data: dict) -> AgentTask:
    return AgentTask(objective="v", input_data=input_data)


def test_validator_ok_sin_issues() -> None:
    v = ValidatorAgent()
    r = v.run(_task({"result": {"success": True}}))
    assert r.success is True
    assert r.output["valid"] is True
    assert r.output["issues"] == []
    assert v.status == AgentStatus.IDLE


def test_validator_sin_result_data() -> None:
    v = ValidatorAgent()
    r = v.run(_task({}))
    assert r.success is False
    assert "No result data provided" in r.output["issues"]


def test_validator_require_success_fail() -> None:
    v = ValidatorAgent()
    r = v.run(_task({"result": {"success": False}}))
    assert r.success is False
    assert "Result indicates failure" in r.output["issues"]


def test_validator_require_success_false_ok() -> None:
    v = ValidatorAgent()
    r = v.run(_task({"require_success": False, "result": {"success": False}}))
    assert r.success is True


def test_validator_require_output() -> None:
    v = ValidatorAgent()
    r = v.run(_task({"require_output": True, "result": {"success": True, "output": None}}))
    assert "Result has no output" in r.output["issues"]


def test_validator_require_output_presente() -> None:
    v = ValidatorAgent()
    r = v.run(_task({"require_output": True, "result": {"success": True, "output": {"a": 1}}}))
    assert r.success is True


def test_validator_excepcion_devuelve_error() -> None:
    v = ValidatorAgent()

    class _Roto:
        def get(self, k, default=None):
            msg = "exploto"
            raise RuntimeError(msg)

    r = v.run(_task({"result": _Roto()}))
    assert r.success is False
    assert "exploto" in r.error


def test_validator_id_generado() -> None:
    v1, v2 = ValidatorAgent(), ValidatorAgent()
    assert v1.id != v2.id
    assert v1.role == AgentRole.VALIDATOR


# ── researcher ───────────────────────────────────────────────


class _FactFake:
    def to_dict(self) -> dict:
        return {"fact_id": "f1"}


class _MemStoreFake:
    def search(self, text: str, k: int) -> list:
        return [_FactFake()]


class _MemStoreVacio:
    def search(self, text: str, k: int) -> list:
        return []


class _EpisodesFake:
    def to_dict(self) -> dict:
        return {"episodes": [1, 2]}


class _RetrieverFake:
    def search(self, query) -> _EpisodesFake:
        return _EpisodesFake()


class _RetrieverVacio:
    def search(self, query):
        return None


def test_researcher_con_memoria_y_retriever() -> None:
    r = ResearcherAgent(memory_store=_MemStoreFake(), context_retriever=_RetrieverFake())
    out = r._gather_context("buscar", {"x": 1})
    assert out["semantic_facts"] == [{"fact_id": "f1"}]
    assert out["sources"] == ["semantic_memory", "episodic_memory"]


def test_researcher_solo_memoria() -> None:
    r = ResearcherAgent(memory_store=_MemStoreFake(), context_retriever=_RetrieverVacio())
    out = r._gather_context("q", {})
    assert out["sources"] == ["semantic_memory"]


class _FalsyStore:
    def __bool__(self) -> bool:
        return False

    def search(self, text: str, k: int) -> list:
        return [_FactFake()]


class _FalsyRetriever:
    def __bool__(self) -> bool:
        return False

    def search(self, query) -> _EpisodesFake:
        return _EpisodesFake()


def test_researcher_memory_store_falsy_no_usa() -> None:
    r = ResearcherAgent(memory_store=_FalsyStore(), context_retriever=_FalsyRetriever())
    out = r._gather_context("q", {})
    assert out["sources"] == []


def test_researcher_solo_retriever() -> None:
    r = ResearcherAgent(memory_store=_FalsyStore(), context_retriever=_RetrieverFake())
    out = r._gather_context("q", {})
    assert out["sources"] == ["episodic_memory"]


def test_researcher_sin_dependencias() -> None:
    r = ResearcherAgent(memory_store=_FalsyStore(), context_retriever=None)
    out = r._gather_context("q", {})
    assert out["sources"] == []


def test_researcher_memoria_vacia_no_agrega() -> None:
    r = ResearcherAgent(memory_store=_MemStoreVacio(), context_retriever=_RetrieverVacio())
    out = r._gather_context("q", {})
    assert out["sources"] == []


def test_researcher_run_ok() -> None:
    r = ResearcherAgent(memory_store=_MemStoreFake(), context_retriever=_RetrieverFake())
    res = r.run(AgentTask(objective="buscar", input_data={}))
    assert res.success is True
    assert res.output["query"] == "buscar"
    assert r.status == AgentStatus.IDLE


def test_researcher_run_error() -> None:
    class _Roto:
        def search(self, text: str, k: int) -> list:
            msg = "roto"
            raise RuntimeError(msg)

    r = ResearcherAgent(memory_store=_Roto(), context_retriever=None)
    res = r.run(AgentTask(objective="x"))
    assert res.success is False
    assert "roto" in res.error


def test_researcher_auto_discover_falla_silenciosamente(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _bloquea(name: str, *args, **kwargs):
        if name.startswith("motor.intelligence.memory"):
            msg = f"No module named '{name}'"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _bloquea)
    r = ResearcherAgent(memory_store=None, context_retriever=None)
    assert r._memory_store is None
    assert r._context_retriever is None


def test_researcher_auto_discover_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CR:
        pass

    class _SM:
        pass

    fake = type("fakemod", (), {"ContextRetriever": lambda s: _CR(), "EpisodeStore": lambda: None, "SemanticMemoryStore": lambda: _SM()})
    monkeypatch.setitem(__import__("sys").modules, "motor.intelligence.memory.retrieval", fake)
    monkeypatch.setitem(__import__("sys").modules, "motor.intelligence.memory.episodic", fake)
    monkeypatch.setitem(__import__("sys").modules, "motor.intelligence.memory.semantic", fake)
    r = ResearcherAgent(memory_store=None, context_retriever=None)
    assert isinstance(r._context_retriever, _CR)
    assert isinstance(r._memory_store, _SM)


def test_researcher_auto_discover_retriever_presente(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SM:
        pass

    fake = type("fakemod", (), {"SemanticMemoryStore": lambda: _SM()})
    monkeypatch.setitem(__import__("sys").modules, "motor.intelligence.memory.semantic", fake)
    r = ResearcherAgent(memory_store=None, context_retriever=_RetrieverFake())
    assert r._context_retriever is not None
    assert isinstance(r._memory_store, _SM)


# ── executor ─────────────────────────────────────────────────


class _FakeExec:
    def __init__(self, result: ProcessResult) -> None:
        self._r = result

    def run(self, cmd, timeout: int = 30) -> ProcessResult:
        return self._r


def test_executor_ok() -> None:
    fx = _FakeExec(ProcessResult(ok=True, cmd=["echo"], returncode=0, stdout="salida", stderr=""))
    e = ExecutorAgent(executor=fx)
    r = e.run(AgentTask(objective="op", input_data={"cmd": ["echo", "hola"]}))
    assert r.success is True
    assert r.output["stdout"] == "salida"
    assert r.output["returncode"] == 0
    assert e.status == AgentStatus.IDLE


def test_executor_falla_lanza_error() -> None:
    fx = _FakeExec(ProcessResult(ok=False, cmd=["bad"], returncode=2, stdout="", stderr="falló"))
    e = ExecutorAgent(executor=fx)
    r = e.run(AgentTask(objective="op", input_data={"cmd": ["bad"]}))
    assert r.success is False
    assert "falló" in r.error


def test_executor_allow_failure() -> None:
    fx = _FakeExec(ProcessResult(ok=False, cmd=["bad"], returncode=2, stdout="", stderr="falló"))
    e = ExecutorAgent(executor=fx)
    r = e.run(AgentTask(objective="op", input_data={"cmd": ["bad"], "allow_failure": True}))
    assert r.success is True
    assert r.output["returncode"] == 2


def test_executor_cmd_por_defecto() -> None:
    class _Registra:
        def __init__(self) -> None:
            self.cmd = None

        def run(self, cmd, timeout: int = 30) -> ProcessResult:
            self.cmd = cmd
            return ProcessResult(ok=True, cmd=cmd, returncode=0, stdout="", stderr="")

    fx = _Registra()
    e = ExecutorAgent(executor=fx)
    e.run(AgentTask(objective="op"))
    assert fx.cmd == ["echo", "executed:", "op"]


def test_executor_excepcion_interna() -> None:
    class _Explota:
        def run(self, cmd, timeout: int = 30) -> ProcessResult:
            msg = "boom"
            raise RuntimeError(msg)

    e = ExecutorAgent(executor=_Explota())
    r = e.run(AgentTask(objective="op"))
    assert r.success is False
    assert "boom" in r.error


# ── supervisor ───────────────────────────────────────────────


class _AgenteStub:
    def __init__(self, agent_id: str, role: AgentRole, results: list[AgentResult], lanzar: bool = False) -> None:
        self.id = agent_id
        self.name = f"agent-{agent_id}"
        self.role = role
        self._results = list(results)
        self._lanzar = lanzar

    def run(self, task: AgentTask) -> AgentResult:
        if self._lanzar:
            msg = "interno"
            raise RuntimeError(msg)
        return self._results.pop(0) if self._results else AgentResult(task_id=task.id, agent_id=self.id, success=True)


def test_supervisor_coordina_exito() -> None:
    s = SupervisorAgent()
    ok = _AgenteStub("a1", AgentRole.EXECUTOR, [])
    s.register_agent(ok)
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.success is True
    assert r.output["total_steps"] == 1
    assert r.output["steps"][0]["status"] == "completed"


def test_supervisor_sin_agente_skips() -> None:
    s = SupervisorAgent()
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.RESEARCHER}]}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.success is False
    assert r.output["steps"][0]["status"] == "skipped"
    assert r.output["steps"][0]["reason"] == "no_agent"


def test_supervisor_cancelled_break() -> None:
    s = SupervisorAgent()
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}, {"objective": "t2"}]}
    s.run(AgentTask(objective="o", context=ctx))
    # sin agente → t2 skipped; con cancel al inicio:
    r2 = s.run(AgentTask(objective="o", context={"subtasks": [{"objective": "t1"}]}))
    assert r2.output["steps"][0]["status"] == "skipped"


def test_supervisor_cancellation_check() -> None:
    s = SupervisorAgent()
    ok = _AgenteStub("a1", AgentRole.EXECUTOR, [])
    s.register_agent(ok)
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.success is True


def test_supervisor_cancelled_en_subtask() -> None:
    s = SupervisorAgent()
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}

    def cancel() -> bool:
        return True

    result = s._coordinate("o", ctx, cancel)
    assert result["steps"][0]["status"] == "cancelled"


def test_supervisor_retries_hasta_agotar() -> None:
    s = SupervisorAgent()
    fail = _AgenteStub(
        "a1",
        AgentRole.EXECUTOR,
        [AgentResult(task_id="t", agent_id="a1", success=False, error="falla")] * (MAX_RETRIES + 1),
    )
    s.register_agent(fail)
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.success is False
    fails = [st for st in r.output["steps"] if st["status"] == "failed"]
    assert len(fails) == MAX_RETRIES + 1


def test_supervisor_agente_que_lanza() -> None:
    s = SupervisorAgent()
    malo = _AgenteStub("a1", AgentRole.EXECUTOR, [], lanzar=True)
    s.register_agent(malo)
    ctx = {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.output["steps"][0]["status"] == "error"


def test_supervisor_cancel_en_run_subtask() -> None:
    s = SupervisorAgent()
    llamadas = {"n": 0}

    def cancel() -> bool:
        llamadas["n"] += 1
        return llamadas["n"] >= 2

    ok = _AgenteStub("a1", AgentRole.EXECUTOR, [])
    s.register_agent(ok)
    result = s._coordinate("o", {"subtasks": [{"objective": "t1", "agent_role": AgentRole.EXECUTOR}]}, cancel)
    assert result["steps"][0]["status"] == "cancelled"


def test_supervisor_run_excepcion() -> None:
    s = SupervisorAgent()
    r = s.run(AgentTask(objective="o", context={"subtasks": None}))
    assert r.success is False
    assert s.status == AgentStatus.IDLE


def test_supervisor_find_agent_por_rol() -> None:
    s = SupervisorAgent()
    a = _AgenteStub("a1", AgentRole.EXECUTOR, [])
    s.register_agent(a)
    assert s._find_agent(AgentRole.EXECUTOR) is a
    assert s._find_agent(AgentRole.PLANNER) is None
    assert s._find_agent(None) is None


def test_supervisor_run_ok_status_idle() -> None:
    s = SupervisorAgent()
    ctx = {"subtasks": []}
    r = s.run(AgentTask(objective="o", context=ctx))
    assert r.success is True
    assert s.status == AgentStatus.IDLE
