"""Cobertura 100x100 de motor/intelligence/agents (parallel + reflection). TASK-20260820-007."""

from __future__ import annotations

import time

from motor.intelligence.agents.message import AgentResult, AgentTask
from motor.intelligence.agents.parallel import ParallelExecutor
from motor.intelligence.agents.reflection import (
    AlwaysRejectStrategy,
    ReflectionAction,
    ReflectionAgent,
    ReflectionDecision,
    ReflectionStrategy,
    RuleBasedReflectionStrategy,
)


def _task(oid: str = "t1") -> AgentTask:
    return AgentTask(objective=f"o-{oid}", id=oid)


def _result(task_id: str = "t1", success: bool = True, error: str = "", output: dict | None = None) -> AgentResult:
    return AgentResult(task_id=task_id, agent_id="a", success=success, error=error, output=output or {})


class _FastAgent:
    def __init__(self, result: AgentResult | None = None, delay: float = 0.0, lanzar: bool = False) -> None:
        self.id = f"agent-{id(self)}"
        self.name = "fast"
        self._result = result
        self._delay = delay
        self._lanzar = lanzar

    def run(self, task: AgentTask) -> AgentResult:
        if self._delay:
            time.sleep(self._delay)
        if self._lanzar:
            msg = "internal-error"
            raise RuntimeError(msg)
        return self._result or _result(task.id)


# ── ParallelExecutor ─────────────────────────────────────────


def test_parallel_max_workers_min_1() -> None:
    p = ParallelExecutor(max_workers=0)
    assert p.max_workers == 1


def test_parallel_sin_tasks() -> None:
    p = ParallelExecutor()
    r = p.execute([])
    assert r.total_tasks == 0
    assert r.completed == 0
    assert r.success is True


def test_parallel_ok() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent())
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2"))])
    assert r.total_tasks == 2
    assert r.completed == 2
    assert r.failed == 0
    assert r.success is True
    assert len(r.results) == 2


def test_parallel_workflow_id_auto() -> None:
    p = ParallelExecutor()
    r = p.execute([], workflow_id=None)
    assert r.workflow_id != ""


def test_parallel_cancelled_antes_de_ejecutar() -> None:
    p = ParallelExecutor()
    wf = "wf-x"
    p.cancel(wf)
    r = p.execute([("a1", _task())], workflow_id=wf)
    assert r.cancelled == 1
    assert r.cancelled_by_user is True


def test_parallel_cancel_duplicado_false() -> None:
    p = ParallelExecutor()
    assert p.cancel("wf1") is True
    assert p.cancel("wf1") is False
    assert p.is_cancelled("wf1") is True
    assert p.is_cancelled("wf2") is False


def test_parallel_cancel_durante_submit() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent())
    wf = "wf-cancel-mid"
    p.cancel(wf)

    class _CancelaEnIteracion:
        def __init__(self) -> None:
            self.n = 0

        def __call__(self, *a, **k) -> None:
            self.n += 1

    # cancel en la 2ª iteración del submit loop
    original = p.is_cancelled

    def _is_cancelled(wid: str) -> bool:
        return original(wid)

    p.is_cancelled = _is_cancelled
    # forzamos cancel tras primer submit
    estado = {"n": 0}

    def _cancel2(wid: str) -> bool:
        estado["n"] += 1
        if estado["n"] >= 2:
            p._cancelled.add(wid)
        return original(wid)

    p.is_cancelled = _cancel2
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2")), ("a3", _task("t3"))], workflow_id=wf)
    assert r.cancelled_by_user is True
    assert r.total_tasks == 3


def test_parallel_future_falla() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent(lanzar=True))
    r = p.execute([("a1", _task("t1"))])
    assert r.failed == 1
    assert r.success is False
    assert len(r.errors) == 1


def test_parallel_resultado_fallido() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent(result=_result("t1", success=False, error="mal")))
    r = p.execute([("a1", _task("t1"))])
    assert r.failed == 1
    assert "mal" in r.errors[0]


def test_parallel_agente_no_encontrado() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: None)
    r = p.execute([("a1", _task("t1"))])
    assert r.failed == 1
    assert "agent_not_found" in r.errors[0]


def test_parallel_sin_find_agent() -> None:
    p = ParallelExecutor()
    r = p.execute([("a1", _task("t1"))])
    assert r.failed == 1
    assert "agent_not_found" in r.errors[0]


def test_parallel_fail_fast() -> None:
    def _fnd(aid: str):
        return _FastAgent(result=_result(aid, success=False, error="fail"))

    p = ParallelExecutor(find_agent_fn=_fnd, fail_fast=True)
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2")), ("a3", _task("t3"))])
    assert r.failed == 1
    assert r.success is False


def test_parallel_cancel_on_error() -> None:
    def _fnd(aid: str):
        return _FastAgent(result=_result(aid, success=False, error="fail"))

    p = ParallelExecutor(find_agent_fn=_fnd, cancel_on_error=True)
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2"))])
    assert r.failed >= 1
    assert p.is_cancelled(r.workflow_id) is True


def test_parallel_global_timeout() -> None:
    def _fnd(aid: str):
        return _FastAgent(delay=1.0)

    p = ParallelExecutor(find_agent_fn=_fnd, global_timeout=0.1)
    r = p.execute([("a1", _task("t1"))])
    assert r.timed_out >= 1
    assert r.success is False


def test_parallel_global_timeout_parcial() -> None:
    def _fnd(aid: str):
        return _FastAgent(delay=0.5)

    p = ParallelExecutor(find_agent_fn=_fnd, global_timeout=0.2)
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2"))])
    assert r.timed_out >= 1


def test_parallel_excepcion_en_future() -> None:
    class _Roto:
        def run(self, task: AgentTask) -> AgentResult:
            msg = "roto"
            raise RuntimeError(msg)

    p = ParallelExecutor(find_agent_fn=lambda aid: _Roto())
    r = p.execute([("a1", _task("t1"))])
    assert r.failed == 1
    assert "roto" in r.errors[0]


def test_parallel_close_limpia_cancelled() -> None:
    p = ParallelExecutor()
    p.cancel("wf1")
    p.close()
    assert p.is_cancelled("wf1") is False


def test_parallel_cancel_durante_submit_loop() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent())
    wf = "wf-submit-cancel"
    estado = {"n": 0}
    original = p.is_cancelled

    def _cancel_en_2da(wid: str) -> bool:
        estado["n"] += 1
        if estado["n"] == 2:
            p._cancelled.add(wid)
        return original(wid)

    p.is_cancelled = _cancel_en_2da
    r = p.execute([("a1", _task("t1")), ("a2", _task("t2")), ("a3", _task("t3"))], workflow_id=wf)
    assert r.cancelled_by_user is True
    assert r.cancelled >= 2  # 2ª llamada cancela: resto de tareas canceladas


def test_parallel_deadline_superado() -> None:
    import motor.intelligence.agents.parallel as pmod

    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent(), global_timeout=5.0)
    clock = {"t": 0.0}

    def _fake_monotonic() -> float:
        clock["t"] += 5.1
        return clock["t"]

    pmod.time.monotonic = _fake_monotonic
    try:
        r = p.execute([("a1", _task("t1"))])
        assert r.timed_out >= 1
        assert "global timeout" in r.errors[0]
    finally:
        pmod.time.monotonic = time.monotonic


def test_parallel_future_excepcion_en_result() -> None:
    p = ParallelExecutor(find_agent_fn=lambda aid: _FastAgent())
    p._run_single = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("future-boom"))
    r = p.execute([("a1", _task("t1"))])
    assert r.timed_out == 1
    assert "future-boom" in r.errors[0]


def test_parallel_run_single_cancelled() -> None:
    p = ParallelExecutor()
    p.cancel("wfx")
    r = p._run_single("a1", _task("t1"), "wfx")
    assert r.success is False
    assert r.error == "cancelled"


# ── reflection ───────────────────────────────────────────────


def test_rule_based_falla_devuelve_revise() -> None:
    s = RuleBasedReflectionStrategy()
    d = s.reflect(_result("t", success=False, error="boom"), iteration=1)
    assert d.action == ReflectionAction.REVISE
    assert d.confidence == 0.0
    assert d.metadata["result_error"] == "boom"
    assert d.iteration == 1


def test_rule_based_acepta_por_confianza() -> None:
    s = RuleBasedReflectionStrategy(min_confidence=0.7)
    d = s.reflect(_result("t", success=True, output={"confidence": 0.9}), iteration=2)
    assert d.action == ReflectionAction.ACCEPT
    assert d.confidence == 0.9
    assert "above_threshold" in d.reason


def test_rule_based_revisa_bajo_umbral() -> None:
    s = RuleBasedReflectionStrategy(min_confidence=0.7)
    d = s.reflect(_result("t", success=True, output={"confidence": 0.4}), iteration=3)
    assert d.action == ReflectionAction.REVISE
    assert "below_threshold" in d.reason


def test_rule_based_confianza_sin_output() -> None:
    s = RuleBasedReflectionStrategy(min_confidence=0.5)
    d = s.reflect(_result("t", success=True), iteration=0)
    assert d.confidence == 1.0


def test_rule_based_confianza_no_numerica() -> None:
    s = RuleBasedReflectionStrategy(min_confidence=0.5)
    d = s.reflect(_result("t", success=True, output={"confidence": "alto"}), iteration=0)
    assert d.confidence == 1.0


def test_rule_based_confianza_forzada_rango() -> None:
    s = RuleBasedReflectionStrategy(min_confidence=0.5)
    d = s.reflect(_result("t", success=True, output={"confidence": 5.0}), iteration=0)
    assert d.confidence == 1.0
    d2 = s.reflect(_result("t", success=True, output={"confidence": -2.0}), iteration=0)
    assert d2.confidence == 0.0


def test_always_reject() -> None:
    s = AlwaysRejectStrategy()
    d = s.reflect(_result("t"), iteration=1)
    assert d.action == ReflectionAction.REJECT
    assert d.reason == "always_reject"


def test_reflection_agent_run_sin_initial() -> None:
    a = ReflectionAgent()
    r = a.run(AgentTask(objective="x", input_data={}))
    assert r.success is False
    assert r.error == "no_initial_result_provided"
    assert a.status.value == "idle"


def test_reflection_agent_initial_no_agent_result() -> None:
    a = ReflectionAgent()
    r = a.run(AgentTask(objective="x", input_data={"initial_result": {"no": "es"}}))
    assert r.success is False
    assert r.error == "initial_result_not_agent_result"


def test_reflection_agent_acepta() -> None:
    a = ReflectionAgent(min_confidence=0.5)
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t", success=True, output={"confidence": 0.9})}))
    assert r.success is True
    assert r.output["stopped_by"] == "accept"
    assert r.output["final_decision"]["action"] == "accept"


def test_reflection_agent_stop_on_accept_false() -> None:
    a = ReflectionAgent(min_confidence=0.5, stop_on_accept=False)
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t", success=True, output={"confidence": 0.9})}))
    assert r.success is True
    assert r.output["stopped_by"] == "confidence"


def test_reflection_agent_rechaza() -> None:
    a = ReflectionAgent(strategy=AlwaysRejectStrategy())
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t")}))
    assert r.success is False
    assert r.output["stopped_by"] == "reject"


def test_reflection_agent_revisa_y_agota_iteraciones() -> None:
    a = ReflectionAgent(max_iterations=1)
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t", success=True, output={"confidence": 0.1})}))
    assert r.success is True
    assert r.output["stopped_by"] == "max_iterations"


def test_reflection_agent_stop_estrategia() -> None:
    class _StopStrategy(ReflectionStrategy):
        def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
            return ReflectionDecision(action=ReflectionAction.STOP, reason="stop-now", iteration=iteration)

    a = ReflectionAgent(strategy=_StopStrategy())
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t")}))
    assert r.output["stopped_by"] == "stop"
    assert r.output["reason"] == "stop-now"


def test_reflection_agent_revise_fallido() -> None:
    class _ReviseFallo(ReflectionStrategy):
        def __init__(self) -> None:
            self.n = 0

        def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
            self.n += 1
            return ReflectionDecision(action=ReflectionAction.REVISE, reason="siempre", iteration=iteration)

    # _revise siempre devuelve resultado (nunca None): forzamos None vía monkeypatch
    a = ReflectionAgent(strategy=_ReviseFallo())
    original = a._revise
    a._revise = lambda result, decision: None
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t")}))
    assert r.output["stopped_by"] == "revise_failed"
    assert r.output["reason"] == "revise_failed_no_new_result"
    a._revise = original


def test_reflection_strategy_property_setter() -> None:
    a = ReflectionAgent()
    s2 = AlwaysRejectStrategy()
    a.strategy = s2
    assert a.strategy is s2


def test_reflection_reflect_on() -> None:
    a = ReflectionAgent()
    d = a.reflect_on(_result("t", success=True))
    assert isinstance(d, ReflectionDecision)


def test_reflection_run_excepcion() -> None:
    class _Explota(ReflectionStrategy):
        def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
            msg = "strategia-rota"
            raise RuntimeError(msg)

    a = ReflectionAgent(strategy=_Explota())
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t")}))
    assert r.success is False
    assert "strategia-rota" in r.error


def test_reflection_min_confidence_clamp() -> None:
    a = ReflectionAgent(min_confidence=5.0)
    assert a._min_confidence == 1.0
    b = ReflectionAgent(min_confidence=-5.0)
    assert b._min_confidence == 0.0
    c = ReflectionAgent(max_iterations=0)
    assert c._max_iterations == 1


def test_reflection_strategy_abstract_reflect_elipsis() -> None:
    class _ConSuperReflect(ReflectionStrategy):
        def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
            d = super().reflect(result, iteration)
            if d is None:
                return ReflectionDecision(reason="default")
            return d

    s = _ConSuperReflect()
    d = s.reflect(_result("t"), 0)
    assert d.action == ReflectionAction.ACCEPT


def test_reflection_accept_bajo_umbral_sin_stop_continua_loop() -> None:
    class _AcceptBajo(ReflectionStrategy):
        def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision:
            return ReflectionDecision(action=ReflectionAction.ACCEPT, confidence=0.1, reason="bajo", iteration=iteration)

    a = ReflectionAgent(strategy=_AcceptBajo(), min_confidence=0.9, stop_on_accept=False)
    r = a.run(AgentTask(objective="x", input_data={"initial_result": _result("t", success=True, output={"confidence": 0.1})}))
    assert r.output["stopped_by"] == "max_iterations"
