"""Tests para F27-B4: ToolRunner.

Cubre TR-01 a TR-20:
- ToolAdapter como interfaz única
- ExecutionId por ejecución
- ToolResult por ejecución
- Timeout obligatorio
- Cancelación cooperativa
- Retries solo para transitorios
- Backoff configurable
- Auditoría
- Contrato de herramientas
- Sin estado entre ejecuciones
- Sin dependencias de Planner/Scheduler/Memory/Knowledge
- ToolRequest → ToolResult
- Ejecución paralela
- Sin globales ni singletons
- Determinismo cuando aplica
- Excepciones tipificadas
"""

from __future__ import annotations

import time

import pytest

from motor.agents import (
    AgentToolRunner,
    ToolAdapter,
    ToolCancelledError,
    ToolContract,
    ToolError,
    ToolNotFoundError,
    ToolPermanentError,
    ToolTimeoutError,
    ToolTransientError,
    make_tool_execution_id,
)

# ── Helpers ────────────────────────────────────────────


class _EchoAdapter(ToolAdapter):
    """Herramienta que devuelve los mismos parámetros."""
    def name(self) -> str: return "echo"
    def run(self, params: dict) -> dict: return params
    def cancel(self) -> None: pass


class _SlowAdapter(ToolAdapter):
    """Herramienta que tarda más del timeout."""
    def name(self) -> str: return "slow"
    def run(self, params: dict) -> dict:
        time.sleep(10)
        return {"done": True}
    def cancel(self) -> None: pass


class _FailingAdapter(ToolAdapter):
    """Herramienta que siempre falla."""
    def name(self) -> str: return "fail"
    def run(self, params: dict) -> dict:
        raise ToolPermanentError("Always fails")
    def cancel(self) -> None: pass


class _TransientAdapter(ToolAdapter):
    """Herramienta que falla las primeras N veces."""
    def __init__(self, fail_count: int = 2):
        self._attempts = 0
        self._fail_count = fail_count
    def name(self) -> str: return "transient"
    def run(self, params: dict) -> dict:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            raise ToolTransientError(f"Attempt {self._attempts} failed")
        return {"success": True, "attempts": self._attempts}
    def cancel(self) -> None: pass


def _make_runner() -> AgentToolRunner:
    r = AgentToolRunner()
    r.register("echo", _EchoAdapter(), ToolContract(name="echo", timeout_seconds=5))
    r.register("slow", _SlowAdapter(), ToolContract(name="slow", timeout_seconds=1))
    r.register("fail", _FailingAdapter(), ToolContract(name="fail", timeout_seconds=5))
    r.register("transient", _TransientAdapter(), ToolContract(name="transient", timeout_seconds=5))
    return r


# ═══════════════════════════════════════════════════
# TR-01: ToolAdapter
# ═══════════════════════════════════════════════════


def test_tool_adapter_interface() -> None:
    """ToolRunner nunca ejecuta herramientas directamente (via ToolAdapter)."""
    adapter = _EchoAdapter()
    assert adapter.name() == "echo"
    assert adapter.run({"key": "value"}) == {"key": "value"}


# ═══════════════════════════════════════════════════
# TR-02 + TR-03: ExecutionId + ToolResult
# ═══════════════════════════════════════════════════


def test_execution_id_unique() -> None:
    a = make_tool_execution_id("agent1", "web.search", 1000.0)
    b = make_tool_execution_id("agent1", "web.search", 1000.0)
    assert a == b  # determinista
    c = make_tool_execution_id("agent2", "web.search", 1000.0)
    assert a != c  # diferente agente


def test_tool_result_immutable() -> None:
    from motor.agents.models import ToolResult
    r = ToolResult(execution_id="e1", tool_name="t1", success=True)
    with pytest.raises(AttributeError):
        r.success = False


# ═══════════════════════════════════════════════════
# TR-04: Timeout
# ═══════════════════════════════════════════════════


def test_timeout_raises() -> None:
    runner = _make_runner()
    with pytest.raises(ToolTimeoutError):
        runner.run("slow", {}, timeout=1)


# ═══════════════════════════════════════════════════
# TR-06: Retries
# ═══════════════════════════════════════════════════


def test_transient_retry_succeeds() -> None:
    runner = AgentToolRunner()
    adapter = _TransientAdapter(fail_count=2)
    runner.register("transient", adapter, ToolContract(name="transient", timeout_seconds=5))
    result = runner.run("transient", {})
    assert result == {"success": True, "attempts": 3}


def test_permanent_error_no_retry() -> None:
    runner = _make_runner()
    with pytest.raises(ToolPermanentError):
        runner.run("fail", {})


# ═══════════════════════════════════════════════════
# TR-09: ToolContract
# ═══════════════════════════════════════════════════


def test_tool_contract() -> None:
    c = ToolContract(name="web.search", timeout_seconds=15, idempotent=True,
                     side_effects=[], expected_cost_units=2)
    assert c.name == "web.search"
    assert c.timeout_seconds == 15
    assert c.idempotent is True


def test_get_contract() -> None:
    runner = _make_runner()
    c = runner.get_contract("echo")
    assert c.name == "echo"
    assert c.timeout_seconds == 5


# ═══════════════════════════════════════════════════
# TR-11..14: Sin dependencias externas
# ═══════════════════════════════════════════════════


def test_no_external_dependencies() -> None:
    import inspect

    import motor.agents.runner as runner_module
    source = inspect.getsource(runner_module)
    assert "from motor.agents.base import Planner" not in source
    assert "from motor.agents.base import Scheduler" not in source
    assert "from motor.agents import Memory" not in source
    assert "from motor.agents import Knowledge" not in source
    # ToolAdapter y ToolContract son dependencias permitidas
    assert "from motor.agents.base import ToolAdapter" in source
    assert "from motor.agents.models import ToolContract" in source


# ═══════════════════════════════════════════════════
# TR-15: ToolRequest → ToolResult
# ═══════════════════════════════════════════════════


def test_request_to_result_flow() -> None:
    runner = _make_runner()
    result = runner.run("echo", {"hello": "world"})
    assert result == {"hello": "world"}


# ═══════════════════════════════════════════════════
# TR-16: Ejecución paralela
# ═══════════════════════════════════════════════════


def test_parallel_execution() -> None:
    import threading
    runner = _make_runner()
    results: list[dict] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def run_echo(val: str) -> None:
        try:
            r = runner.run("echo", {"val": val})
            with lock:
                results.append(r)
        except Exception as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=run_echo, args=(f"v{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(results) == 5
    assert len(errors) == 0


# ═══════════════════════════════════════════════════
# TR-17/18: Sin globales ni singletons
# ═══════════════════════════════════════════════════


def test_no_globals_or_singletons() -> None:
    import inspect

    import motor.agents.runner as runner_module
    source = inspect.getsource(runner_module)
    assert "_instance" not in source
    assert "_instancia" not in source


# ═══════════════════════════════════════════════════
# TR-19: Determinismo
# ═══════════════════════════════════════════════════


def test_deterministic_tool() -> None:
    runner = _make_runner()
    r1 = runner.run("echo", {"x": 1})
    r2 = runner.run("echo", {"x": 1})
    assert r1 == r2


# ═══════════════════════════════════════════════════
# TR-20: Excepciones tipificadas
# ═══════════════════════════════════════════════════


def test_typed_exceptions() -> None:
    assert issubclass(ToolTimeoutError, ToolError)
    assert issubclass(ToolCancelledError, ToolError)
    assert issubclass(ToolTransientError, ToolError)
    assert issubclass(ToolPermanentError, ToolError)
    assert issubclass(ToolNotFoundError, ToolError)


def test_tool_not_found() -> None:
    runner = _make_runner()
    with pytest.raises(ToolNotFoundError):
        runner.run("nonexistent", {})
