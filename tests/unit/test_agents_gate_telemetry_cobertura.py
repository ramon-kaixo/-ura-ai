"""Cobertura 100x100 de gate/base/planner + core secrets/groq/interfaces/telemetry. TASK-20260820-016."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import motor.core.agents.telemetry as tel
import motor.core.secrets as sec
from motor.agents.base import (
    Agent,
    AuditLogger,
    CapabilityGate,
    Executor,
    Planner,
    Scheduler,
    StateMachine,
    TaskQueue,
    ToolAdapter,
    ToolRunner,
)
from motor.agents.gate import AgentCapabilityGate, DenialCode, PermissionDecision
from motor.agents.models import (
    AgentCapability,
    AgentContext,
    AgentExecution,
    AgentPlan,
    AgentPolicy,
    AgentTask,
    PlanStep,
)
from motor.agents.planner import RuleBasedPlanner
from motor.core.agents.telemetry import Telemetria
from motor.core.interfaces.llm import ILLMClient
from motor.core.interfaces.repository import IVectorStore
from motor.core.interfaces.secrets import ISecretStore
from motor.core.llm.groq import GroqProvider
from motor.core.secrets import KNOWN_SECRETS, get_secret, has_secret, list_available, require_secret

# ── interfaces (Protocols) ───────────────────────────────────


def test_illm_client_protocol() -> None:
    class _Cliente:
        def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
            return "respuesta"

        def health(self) -> dict:
            return {"status": "ok"}

    assert isinstance(_Cliente(), ILLMClient)


def test_ivector_store_protocol() -> None:
    class _Store:
        def guardar_incidente(self, incidente: dict) -> bool:
            return True

        def buscar_similares(self, vector: list[float], limite: int = 5) -> list[dict]:
            return []

    assert isinstance(_Store(), IVectorStore)


def test_isecret_store_protocol() -> None:
    class _Secretos:
        def get_secret(self, name: str, default: str | None = None) -> str | None:
            return default

    assert isinstance(_Secretos(), ISecretStore)


def test_llm_client_elipsis() -> None:
    class _Parcial:
        def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
            r = ILLMClient.generate(self, prompt, model, options)
            if r is None:
                return ""
            return r

        def health(self) -> dict:
            r = ILLMClient.health(self)
            if r is None:
                return {}
            return r

    p = _Parcial()
    assert p.generate("x") == ""
    assert p.health() == {}


def test_vector_store_elipsis() -> None:
    class _Parcial:
        def guardar_incidente(self, incidente: dict) -> bool:
            r = IVectorStore.guardar_incidente(self, incidente)
            if r is None:
                return False
            return r

        def buscar_similares(self, vector: list[float], limite: int = 5) -> list[dict]:
            r = IVectorStore.buscar_similares(self, vector, limite)
            if r is None:
                return []
            return r

    p = _Parcial()
    assert p.guardar_incidente({}) is False
    assert p.buscar_similares([0.1]) == []


def test_secret_store_elipsis() -> None:
    class _Parcial:
        def get_secret(self, name: str, default: str | None = None) -> str | None:
            r = ISecretStore.get_secret(self, name, default)
            return r

    assert _Parcial().get_secret("x") is None


# ── secrets ──────────────────────────────────────────────────


def test_get_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_TEST_SECRET", "valor-env")
    assert get_secret("URA_TEST_SECRET") == "valor-env"
    assert has_secret("URA_TEST_SECRET") is True


def test_get_secret_file(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "secrets.env"
    f.write_text("# comentario\n\nURA_FILE_SECRET='valor-archivo'\nURA_OTRO=\"comillas\"\nLINEA_SIN_IGUAL\n")
    monkeypatch.setattr(sec, "RUTA_SECRETOS", str(f))
    sec._clear_cache()
    try:
        assert get_secret("URA_FILE_SECRET") == "valor-archivo"
        assert get_secret("URA_OTRO") == "comillas"
        assert get_secret("URA_INEXISTENTE") is None
        assert get_secret("URA_INEXISTENTE", "default") == "default"
    finally:
        sec._clear_cache()


def test_get_secret_prioridad_env_sobre_file(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "secrets.env"
    f.write_text("URA_PRIORIDAD=archivo\n")
    monkeypatch.setattr(sec, "RUTA_SECRETOS", str(f))
    monkeypatch.setenv("URA_PRIORIDAD", "env")
    sec._clear_cache()
    try:
        assert get_secret("URA_PRIORIDAD") == "env"
    finally:
        sec._clear_cache()


def test_load_file_secrets_oserror(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Roto:
        def __init__(self) -> None:
            pass

        def exists(self) -> bool:
            return True

        def read_text(self, **k):
            msg = "permiso"
            raise OSError(msg)

    monkeypatch.setattr(sec, "Path", lambda p: _Roto())
    sec._clear_cache()
    try:
        assert sec._load_file_secrets() == {}
    finally:
        sec._clear_cache()


def test_load_file_secrets_no_existe(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sec, "RUTA_SECRETOS", str(tmp_path / "no-existe.env"))
    sec._clear_cache()
    try:
        assert sec._load_file_secrets() == {}  # path no existe → {} y cachea
    finally:
        sec._clear_cache()


def test_load_file_secrets_cacheado(monkeypatch: pytest.MonkeyPatch) -> None:
    # segunda llamada usa caché (línea 74)
    sec._cached_file_secrets = {"CACHE": "1"}
    try:
        assert sec._load_file_secrets() == {"CACHE": "1"}
    finally:
        sec._clear_cache()


def test_require_secret_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URA_REQ", "valor")
    assert require_secret("URA_REQ") == "valor"


def test_require_secret_falta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("URA_REQ_NO_EXISTE", raising=False)
    with pytest.raises(KeyError):
        require_secret("URA_REQ_NO_EXISTE")


def test_list_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "x")
    available = list_available()
    assert "GROQ_API_KEY" in available
    assert all(s in KNOWN_SECRETS for s in available)


# ── groq ─────────────────────────────────────────────────────


def test_groq_provider_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GROQ_MODEL", "m")
    monkeypatch.setenv("GROQ_TIMEOUT", "30")
    monkeypatch.setenv("GROQ_TEMPERATURE", "0.7")
    monkeypatch.setenv("GROQ_MAX_TOKENS", "2048")
    p = GroqProvider()
    assert p._provider_name == "groq"
    assert p._api_key == "k"
    assert p._model == "m"
    assert p._timeout == 30
    assert p._temperature == 0.7
    assert p._max_tokens == 2048
    assert p._base_url == "https://api.groq.com/openai/v1"
    caps = p.capabilities
    assert caps["chat"] is True
    assert caps["embeddings"] is False
    assert caps["max_context"] == 131072


def test_groq_provider_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_TIMEOUT", raising=False)
    monkeypatch.delenv("GROQ_TEMPERATURE", raising=False)
    monkeypatch.delenv("GROQ_MAX_TOKENS", raising=False)
    p = GroqProvider()
    assert p._model == "llama-3.1-70b-versatile"
    assert p._timeout == 60
    assert p._temperature == 0.3
    assert p._max_tokens == 4096


def test_groq_embed() -> None:
    p = GroqProvider.__new__(GroqProvider)
    res = p.embed(["texto"])
    assert len(res) == 1
    assert len(res[0]) == 768
    assert res[0][0] == 0.0


def test_groq_embed_async() -> None:
    import asyncio

    p = GroqProvider.__new__(GroqProvider)
    res = asyncio.run(p.embed_async(["texto"]))
    assert len(res) == 1
    assert len(res[0]) == 768


# ── gate ─────────────────────────────────────────────────────


def _execution(caps=None, cancelled=False, cost=0) -> AgentExecution:
    return AgentExecution(
        agent_id="a1",
        task=AgentTask(task_id="t1", objective="objetivo"),
        capabilities=set(caps or [AgentCapability.MEMORY_READ]),
        policy=AgentPolicy(max_cost_units=100),
        cancelled=cancelled,
        cost_units=cost,
    )


def test_denial_code_valores() -> None:
    assert DenialCode.GATE_CLOSED.value == "gate_closed"
    assert DenialCode.BUDGET_EXCEEDED.value == "budget_exceeded"


def test_permission_decision_defaults() -> None:
    d = PermissionDecision(granted=True, capability=AgentCapability.MEMORY_READ, agent_id="a1")
    assert d.denial_code is None
    assert d.cached is False


def test_gate_check_ok() -> None:
    g = AgentCapabilityGate(_execution())
    g.check(AgentCapability.MEMORY_READ)  # no lanza
    assert g.granted_count == 1
    assert g.denied_count == 0
    assert g.decision_count == 1
    assert g.decisions[0].granted is True


def test_gate_check_denegada() -> None:
    g = AgentCapabilityGate(_execution())
    with pytest.raises(PermissionError) as e:
        g.check(AgentCapability.WEB_SEARCH)
    assert "capability_not_granted" in str(e.value)
    assert g.denied_count == 1


def test_gate_check_capability_no_reconocida() -> None:
    g = AgentCapabilityGate(_execution())

    class _Raro:
        value = "raro"

    with pytest.raises(PermissionError) as e:
        g.check(_Raro())  # type: ignore[arg-type]
    assert "capability_not_recognized" in str(e.value)


def test_gate_cerrado() -> None:
    g = AgentCapabilityGate(_execution())
    g.close()
    assert g.closed is True
    with pytest.raises(PermissionError) as e:
        g.check(AgentCapability.MEMORY_READ)
    assert "gate_closed" in str(e.value)


def test_gate_agente_cancelado() -> None:
    g = AgentCapabilityGate(_execution(cancelled=True))
    with pytest.raises(PermissionError) as e:
        g.check(AgentCapability.MEMORY_READ)
    assert "agent_cancelled" in str(e.value)


def test_gate_budget_excedido() -> None:
    g = AgentCapabilityGate(_execution(cost=150))
    with pytest.raises(PermissionError) as e:
        g.check(AgentCapability.MEMORY_READ)
    assert "budget_exceeded" in str(e.value)


def test_gate_capabilities() -> None:
    g = AgentCapabilityGate(_execution())
    assert g.capabilities() == {AgentCapability.MEMORY_READ}


def test_gate_cache() -> None:
    g = AgentCapabilityGate(_execution(), enable_cache=True)
    g.check(AgentCapability.MEMORY_READ)
    g.check(AgentCapability.MEMORY_READ)  # cache hit
    assert g.decision_count == 2
    assert g.decisions[1].cached is True


def test_gate_sin_cache() -> None:
    g = AgentCapabilityGate(_execution(), enable_cache=False)
    g.check(AgentCapability.MEMORY_READ)
    g.check(AgentCapability.MEMORY_READ)
    assert g.decisions[1].cached is False


def test_gate_audit_events() -> None:
    g = AgentCapabilityGate(_execution())
    g.check(AgentCapability.MEMORY_READ)
    try:
        g.check(AgentCapability.WEB_SEARCH)
    except PermissionError:
        pass
    events = g.audit_events()
    assert len(events) == 2
    assert events[0].event_type == "capability.check"
    assert events[0].data["granted"] is True
    assert events[1].data["denial_code"] == "capability_not_granted"


# ── planner ──────────────────────────────────────────────────


def _task(objective: str) -> AgentTask:
    return AgentTask(task_id="t1", objective=objective)


def test_planner_search() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("search information"))
    actions = [s.action for s in plan.steps]
    assert actions[0] == "retrieve"
    assert actions[1] == "search"
    assert actions[-1] == "llm"
    assert plan.immutable is True
    assert plan.plan_id != ""


def test_planner_facts() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("lee los facts"))
    actions = [s.action for s in plan.steps]
    assert "retrieve" in actions


def test_planner_summarize() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("summarize este texto"))
    actions = [s.action for s in plan.steps]
    assert actions[-2] == "llm"  # summarize
    assert actions[-1] == "llm"  # respond


def test_planner_write() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("save el informe"))
    actions = [s.action for s in plan.steps]
    assert actions[-2] == "tool"
    assert actions[-1] == "llm"


def test_planner_sin_keywords() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("hola"))
    assert len(plan.steps) == 2  # retrieve + llm respond


def test_planner_make_step() -> None:
    s = RuleBasedPlanner._make_step(3, "action", {"k": "v"})
    assert s.step_id != ""
    assert s.action == "action"
    assert s.params == {"k": "v"}
    s2 = RuleBasedPlanner._make_step(4, "action2")
    assert s2.params == {}


def test_planner_replan_con_fallo() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("busca información"))
    failed = plan.steps[1]  # search
    nuevo = p.replan(_task("busca información"), plan, AgentContext(), failed_step=failed)
    assert nuevo.plan_id != plan.plan_id
    actions = [s.action for s in nuevo.steps]
    assert actions[0] == "retrieve"  # paso conservado
    assert "retrieve" in actions[1:]  # fallback tras fallo


def test_planner_replan_tras_fallo_descarta_resto() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("search and save the report"))  # retrieve, search, retrieve, llm, tool, llm
    failed = plan.steps[2]  # el retrieve de save falla → descarta llm/tool posteriores
    nuevo = p.replan(_task("search and save the report"), plan, AgentContext(), failed_step=failed)
    assert nuevo.plan_id != plan.plan_id
    # pasos 0,1 conservados; el fallo en 2 genera fallback (retrieve + llm)
    assert nuevo.steps[0].action == "retrieve"
    assert nuevo.steps[1].action == "search"
    assert nuevo.steps[2].action == "retrieve"  # fallback
    assert nuevo.steps[-1].action == "llm"  # respond
    assert len(nuevo.steps) == 4  # 2 conservados + 2 del fallback


def test_planner_replan_sin_fallo() -> None:
    p = RuleBasedPlanner()
    plan = p.plan(_task("hola"))
    nuevo = p.replan(_task("hola"), plan, AgentContext())
    assert nuevo is plan  # sin fallo → plan original


def test_planner_generate_remaining_search() -> None:
    p = RuleBasedPlanner()
    steps = p._generate_remaining("x", PlanStep(step_id="s", action="search"))
    assert steps[0].params.get("fallback") is True


def test_planner_generate_remaining_tool() -> None:
    p = RuleBasedPlanner()
    steps = p._generate_remaining("x", PlanStep(step_id="s", action="tool"))
    assert steps[0].action == "llm"
    assert steps[0].params.get("action") == "suggest"


def test_planner_generate_remaining_otro() -> None:
    p = RuleBasedPlanner()
    steps = p._generate_remaining("x", PlanStep(step_id="s", action="otro"))
    assert steps[0].params.get("fallback") is True


# ── base ABCs ────────────────────────────────────────────────


def test_abc_lanzan() -> None:
    with pytest.raises(TypeError):
        CapabilityGate()
    with pytest.raises(TypeError):
        Planner()
    with pytest.raises(TypeError):
        Executor()
    with pytest.raises(TypeError):
        ToolRunner()
    with pytest.raises(TypeError):
        Scheduler()
    with pytest.raises(TypeError):
        Agent()
    with pytest.raises(TypeError):
        AuditLogger()
    with pytest.raises(TypeError):
        TaskQueue()
    with pytest.raises(TypeError):
        ToolAdapter()
    with pytest.raises(TypeError):
        StateMachine()


# ── base: elipsis vía super() ────────────────────────────────


class _GateSuper(CapabilityGate):
    def check(self, required: AgentCapability) -> None:
        super().check(required)

    def capabilities(self) -> set[AgentCapability]:
        r = super().capabilities()
        if r is None:
            return set()
        return r


class _PlannerSuper(Planner):
    def plan(self, task: AgentTask, context: AgentContext | None = None) -> AgentPlan:
        r = super().plan(task, context)
        if r is None:
            return AgentPlan(plan_id="x")
        return r

    def replan(self, task, current_plan, context, failed_step=None) -> AgentPlan:
        r = super().replan(task, current_plan, context, failed_step)
        if r is None:
            return AgentPlan(plan_id="y")
        return r


class _ExecutorSuper(Executor):
    def execute_step(self, step, context, gate) -> AgentContext:
        r = super().execute_step(step, context, gate)
        if r is None:
            return AgentContext()
        return r

    def execute_plan(self, plan, context, gate, execution) -> AgentContext:
        r = super().execute_plan(plan, context, gate, execution)
        if r is None:
            return AgentContext()
        return r


class _ToolRunnerSuper(ToolRunner):
    def get_contract(self, tool_name: str):
        r = super().get_contract(tool_name)
        return r

    def run(self, tool_name: str, params: dict, timeout: int = 30) -> dict:
        r = super().run(tool_name, params, timeout)
        if r is None:
            return {}
        return r

    def cancel(self, tool_name: str) -> None:
        super().cancel(tool_name)


class _SchedulerSuper(Scheduler):
    def submit(self, execution) -> None:
        super().submit(execution)

    def cancel(self, agent_id: str) -> None:
        super().cancel(agent_id)

    def shutdown(self, timeout: int = 30) -> list:
        r = super().shutdown(timeout)
        if r is None:
            return []
        return r


class _AgentSuper(Agent):
    def run(self, task: AgentTask):
        r = super().run(task)
        return r

    def cancel(self) -> None:
        super().cancel()


class _AuditSuper(AuditLogger):
    def log(self, event) -> None:
        super().log(event)

    def get_audit(self, agent_id: str) -> list:
        r = super().get_audit(agent_id)
        if r is None:
            return []
        return r


class _TaskQueueSuper(TaskQueue):
    def push(self, execution, priority: int = 0) -> None:
        super().push(execution, priority)

    def pop(self):
        r = super().pop()
        return r

    def remove(self, agent_id: str) -> bool:
        r = super().remove(agent_id)
        if r is None:
            return False
        return r

    def size(self) -> int:
        r = super().size()
        if r is None:
            return 0
        return r


class _ToolAdapterSuper(ToolAdapter):
    def name(self) -> str:
        r = super().name()
        if r is None:
            return ""
        return r

    def run(self, params: dict) -> dict:
        r = super().run(params)
        if r is None:
            return {}
        return r

    def cancel(self) -> None:
        super().cancel()


class _StateMachineSuper(StateMachine):
    def transition(self, current, target):
        r = super().transition(current, target)
        return r

    def valid_transitions(self, state) -> list:
        r = super().valid_transitions(state)
        if r is None:
            return []
        return r


def test_abc_elipsis_via_super() -> None:
    _GateSuper().capabilities()
    _GateSuper().check(AgentCapability.MEMORY_READ)  # type: ignore[arg-type]
    _PlannerSuper().plan(AgentTask(task_id="t", objective="o"))
    _PlannerSuper().replan(AgentTask(task_id="t", objective="o"), AgentPlan(plan_id="p"), AgentContext())
    _ExecutorSuper().execute_step(None, None, None)  # type: ignore[arg-type]
    _ExecutorSuper().execute_plan(None, None, None, None)  # type: ignore[arg-type]
    _ToolRunnerSuper().get_contract("x")  # type: ignore[arg-type]
    _ToolRunnerSuper().run("x", {})
    _ToolRunnerSuper().cancel("x")
    _SchedulerSuper().submit(None)  # type: ignore[arg-type]
    _SchedulerSuper().cancel("a")
    _SchedulerSuper().shutdown()
    _AgentSuper().run(AgentTask(task_id="t", objective="o"))  # type: ignore[arg-type]
    _AgentSuper().cancel()
    _AuditSuper().log(None)  # type: ignore[arg-type]
    _AuditSuper().get_audit("a")
    _TaskQueueSuper().push(None)  # type: ignore[arg-type]
    _TaskQueueSuper().pop()
    _TaskQueueSuper().remove("a")
    _TaskQueueSuper().size()
    _ToolAdapterSuper().name()
    _ToolAdapterSuper().run({})
    _ToolAdapterSuper().cancel()
    _StateMachineSuper().transition(None, None)  # type: ignore[arg-type]
    _StateMachineSuper().valid_transitions(None)  # type: ignore[arg-type]


# ── telemetry ────────────────────────────────────────────────


class _LLMFake:
    def health(self) -> dict:
        return {"status": "ok", "modelos_disponibles": ["m1", "m2", "m3"]}

    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
        return ""


def test_telemetry_check_ollama_ok() -> None:
    t = Telemetria(llm=_LLMFake())
    assert t._check_ollama() == "3 modelos"


def test_telemetry_check_ollama_down(monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.core.llm as llm_mod

    monkeypatch.setattr(llm_mod, "health", lambda: {"status": "error"})
    t = Telemetria(llm=None)
    assert t._check_ollama() == "down"


def test_telemetry_hardware_con_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _VM:
        total = 16 * 1024 * 1024 * 1024
        available = 8 * 1024 * 1024 * 1024
        percent = 50.0

    fake_psutil = types.ModuleType("psutil")
    fake_psutil.virtual_memory = lambda: _VM()
    fake_psutil.cpu_percent = lambda interval=0.1: 25.0
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    m = Telemetria.hardware()
    assert m["ram_total_mb"] == 16384
    assert m["ram_libre_mb"] == 8192
    assert m["cpu_pct"] == 25.0


def test_telemetry_hardware_sin_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name == "psutil":
            msg = "no psutil"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    m = Telemetria.hardware()
    assert m["ram_total_mb"] > 0
    assert "ram_libre_mb" in m


def test_telemetry_hardware_meminfo_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    class _Roto:
        def open(self, *a, **k):
            msg = "no permiso"
            raise OSError(msg)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _no_psutil(name: str, *a, **k):
        if name == "psutil":
            msg = "no psutil"
            raise ImportError(msg)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_psutil)
    monkeypatch.setattr(tel.Path, "open", _Roto.open)
    m = Telemetria.hardware()
    assert m["ram_libre_mb"] == 8192  # fallback


def test_telemetry_red_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _R:
        status_code = 200
        text = '{"status": "ok"}'

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.get = lambda *a, **k: _R()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setattr(Telemetria, "_check_ollama", lambda self: "2 modelos")
    t = Telemetria(llm=None)
    status = t.red()
    assert status["model_router"] == "ok"
    assert status["ollama"] == "2 modelos"


def test_telemetry_red_router_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    def _roto(*a, **k):
        msg = "sin red"
        raise ConnectionError(msg)

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.get = _roto
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setattr(Telemetria, "_check_ollama", lambda self: "2 modelos")
    t = Telemetria(llm=None)
    status = t.red()
    assert status["model_router"] == "down"


def test_telemetry_red_ollama_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _R:
        status_code = 200
        text = '{"status": "ok"}'

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.get = lambda *a, **k: _R()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    def _roto(self) -> str:
        msg = "ollama caido"
        raise ConnectionError(msg)

    monkeypatch.setattr(Telemetria, "_check_ollama", _roto)
    t = Telemetria(llm=None)
    status = t.red()
    assert status["ollama"] == "down"


def test_telemetry_llm_stats(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "chunk_config.json"
    f.write_text(json.dumps({"chunk_actual": 4096, "modelo": "qwen", "historico": [1, 2, 3]}))
    monkeypatch.setattr(tel, "NERVIOSO", Path(str(tmp_path)))
    stats = Telemetria.llm_stats()
    assert stats["chunk_actual"] == 4096
    assert stats["modelo"] == "qwen"
    assert stats["historico_ajustes"] == 3


def test_telemetry_llm_stats_default(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tel, "NERVIOSO", Path(str(tmp_path)))
    stats = Telemetria.llm_stats()
    assert stats == {"chunk_actual": 8192, "modelo": "?", "historico_ajustes": 0}


def test_telemetry_f821_count(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        returncode = 0
        stdout = "x.py:1:5 F821 y.py:2:6 F821"

    monkeypatch.setattr(tel.subprocess, "run", lambda *a, **k: _R())
    assert Telemetria.f821_count() == 2


def test_telemetry_f821_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _roto(*a, **k):
        msg = "ruff no existe"
        raise OSError(msg)

    monkeypatch.setattr(tel.subprocess, "run", _roto)
    assert Telemetria.f821_count() == -1


def test_telemetry_reporte_completo(monkeypatch: pytest.MonkeyPatch) -> None:
    t = Telemetria(llm=_LLMFake())
    monkeypatch.setattr(Telemetria, "hardware", staticmethod(lambda: {"ram_total_mb": 1}))
    monkeypatch.setattr(Telemetria, "red", lambda self: {"model_router": "ok"})
    monkeypatch.setattr(Telemetria, "llm_stats", staticmethod(lambda: {"chunk_actual": 1}))
    monkeypatch.setattr(Telemetria, "f821_count", staticmethod(lambda: 0))
    r = t.reporte_completo()
    assert r["hardware"]["ram_total_mb"] == 1
    assert r["red"]["model_router"] == "ok"
    assert r["f821"] == 0


def test_telemetry_shadow_hooks() -> None:
    t = Telemetria(llm=None)
    t.on_layer_start(1, "layer")  # no lanza
    t.on_layer_end(1, "layer", "ok", 5.0)  # no lanza
