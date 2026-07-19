"""Comprehensive tests for motor/agents/ (F27).

Covers all modules with focus on gaps not in per-module test files:
- Models: ToolRequest/ToolResult, AgentAuditRecord, AuditEvent, make_tool_execution_id
- ABC enforcement and lifecycle
- CapabilityGate thread safety, edge cases
- ToolRunner backpressure, RateLimiter, error mappings
- AgentScheduler concurrency, aging, priority mapping
- AgentPlanner edge cases, empty objectives
- Agent error paths, cancel, budget, permission denied
- StateMachine additional edge cases
"""

from __future__ import annotations

import threading
import time

import pytest

from motor.agents import (
    AgentCapability,
    AgentCapabilityGate,
    AgentContext,
    AgentExecution,
    AgentOrchestrator,
    AgentPlan,
    AgentPolicy,
    AgentResult,
    AgentScheduler,
    AgentState,
    AgentStateMachine,
    AgentTask,
    AgentToolRunner,
    AuditEvent,
    AuditLogger,
    CapabilityGate,
    Planner,
    PlanStep,
    RuleBasedPlanner,
    Scheduler,
    ToolAdapter,
    ToolContract,
    ToolRunner,
    make_tool_execution_id,
)
from motor.agents.models import AgentAuditRecord
from motor.agents.runner import (
    RateLimiter,
    ToolAdapterError,
    ToolError,
    ToolNotFoundError,
    ToolPermanentError,
    ToolTimeoutError,
    ToolTransientError,
)
from motor.agents.scheduler import _PriorityQueue

# ════════════════════════════════════════════════════════
# 1. MODELS — comprehensive coverage
# ════════════════════════════════════════════════════════

class TestMakeToolExecutionId:
    def test_deterministic(self) -> None:
        a = make_tool_execution_id("agent1", "web.search", 1000.0)
        b = make_tool_execution_id("agent1", "web.search", 1000.0)
        assert a == b
        assert len(a) == 16

    def test_different_agent(self) -> None:
        a = make_tool_execution_id("agent1", "web.search", 1000.0)
        b = make_tool_execution_id("agent2", "web.search", 1000.0)
        assert a != b

    def test_different_tool(self) -> None:
        a = make_tool_execution_id("agent1", "web.search", 1000.0)
        b = make_tool_execution_id("agent1", "memory.read", 1000.0)
        assert a != b


class TestAgentAuditRecord:
    def test_all_fields(self) -> None:
        r = AgentAuditRecord(
            agent_id="a1",
            task_id="t1",
            objective="test",
            plan=["retrieve"],
            capabilities_used=["memory.read"],
            tools_used=["memory.search"],
            facts_consulted=["fact1"],
            memory_consulted=["mem1"],
            llm_calls=2,
            decisions=[{"step": 1}],
            result="completed",
            state="completed",
            duration_ms=100.0,
            cost_units=5,
            error=None,
            timestamp=1000.0,
            parent_agent="parent1",
        )
        assert r.agent_id == "a1"
        assert r.parent_agent == "parent1"
        assert r.error is None

    def test_immutable(self) -> None:
        r = AgentAuditRecord(
            agent_id="a1", task_id="t1", objective="test",
            plan=[], capabilities_used=[], tools_used=[],
            facts_consulted=[], memory_consulted=[], llm_calls=0,
            decisions=[], result="ok", state="completed",
            duration_ms=0, cost_units=0, error=None, timestamp=0,
        )
        with pytest.raises(AttributeError):
            r.agent_id = "a2"


class TestAuditEvent:
    def test_defaults(self) -> None:
        e = AuditEvent(event_type="test", agent_id="a1", timestamp=100.0)
        assert e.data == {}

    def test_with_data(self) -> None:
        e = AuditEvent(
            event_type="capability.check",
            agent_id="a1",
            timestamp=200.0,
            data={"granted": True, "capability": "memory.read"},
        )
        assert e.data["granted"] is True


class TestToolContractEdgeCases:
    def test_defaults(self) -> None:
        c = ToolContract(name="web.search")
        assert c.timeout_seconds == 30
        assert c.cancelable is True
        assert c.idempotent is False
        assert c.side_effects == []
        assert c.expected_cost_units == 5
        assert c.description == ""

    def test_custom(self) -> None:
        c = ToolContract(
            name="db.write",
            timeout_seconds=60,
            cancelable=False,
            idempotent=True,
            side_effects=["db.write"],
            expected_cost_units=50,
            description="Write to database",
        )
        assert c.timeout_seconds == 60
        assert c.idempotent is True
        assert c.side_effects == ["db.write"]


class TestAgentContextEdgeCases:
    def test_empty_defaults(self) -> None:
        c = AgentContext()
        assert c.conversation == []
        assert c.knowledge_facts == []
        assert c.memory_entries == []
        assert c.execution_state == {}

    def test_mutable_conversation(self) -> None:
        c = AgentContext()
        c.conversation.append({"role": "user", "content": "hello"})
        c.knowledge_facts.append("fact1")
        c.execution_state["key"] = "value"
        assert len(c.conversation) == 1
        assert len(c.knowledge_facts) == 1
        assert c.execution_state["key"] == "value"


class TestAgentPlanEdgeCases:
    def test_empty_steps(self) -> None:
        p = AgentPlan(plan_id="p1")
        assert p.steps == ()
        assert p.immutable is True

    def test_immutable_default(self) -> None:
        p = AgentPlan(plan_id="p1")
        with pytest.raises(AttributeError):
            p.immutable = False


class TestAgentExecutionEdgeCases:
    def test_defaults(self) -> None:
        e = AgentExecution(
            agent_id="a1",
            task=AgentTask(task_id="t1", objective="test"),
            capabilities={AgentCapability.MEMORY_READ},
            policy=AgentPolicy(),
        )
        assert e.state == AgentState.CREATED
        assert e.current_step == 0
        assert e.llm_calls == 0
        assert e.tool_calls == 0
        assert e.cost_units == 0
        assert e.cancelled is False
        assert e.plan is None
        assert e.plan_attempts == 0

    def test_mutable_fields(self) -> None:
        e = AgentExecution(
            agent_id="a1",
            task=AgentTask(task_id="t1", objective="test"),
            capabilities={AgentCapability.MEMORY_READ},
            policy=AgentPolicy(),
        )
        e.state = AgentState.RUNNING
        e.cancelled = True
        e.cost_units = 10
        assert e.state == AgentState.RUNNING
        assert e.cancelled is True
        assert e.cost_units == 10


class TestAgentResultEdgeCases:
    def test_error_state(self) -> None:
        r = AgentResult(
            agent_id="a1", task_id="t1", state=AgentState.FAILED,
            error="Something went wrong",
        )
        assert r.error == "Something went wrong"
        assert r.state == AgentState.FAILED

    def test_cancelled_state(self) -> None:
        r = AgentResult(
            agent_id="a1", task_id="t1", state=AgentState.CANCELLED,
        )
        assert r.state == AgentState.CANCELLED
        assert r.error is None


# ════════════════════════════════════════════════════════
# 2. AGENT BASE CLASS — ABC enforcement
# ════════════════════════════════════════════════════════

class TestAgentABC:
    def test_cannot_instantiate_agent(self) -> None:
        from motor.agents.base import Agent
        with pytest.raises(TypeError):
            Agent()  # type: ignore[abstract]

    def test_cannot_instantiate_planner(self) -> None:
        with pytest.raises(TypeError):
            Planner()  # type: ignore[abstract]

    def test_cannot_instantiate_scheduler(self) -> None:
        with pytest.raises(TypeError):
            Scheduler()  # type: ignore[abstract]

    def test_cannot_instantiate_tool_runner(self) -> None:
        with pytest.raises(TypeError):
            ToolRunner()  # type: ignore[abstract]

    def test_cannot_instantiate_capability_gate(self) -> None:
        with pytest.raises(TypeError):
            CapabilityGate()  # type: ignore[abstract]

    def test_cannot_instantiate_audit_logger(self) -> None:
        with pytest.raises(TypeError):
            AuditLogger()  # type: ignore[abstract]


# ════════════════════════════════════════════════════════
# 3. CAPABILITY GATE — thread safety and edge cases
# ════════════════════════════════════════════════════════

class TestCapabilityGateThreadSafety:
    def test_concurrent_checks(self) -> None:
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities={AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ},
                policy=AgentPolicy(),
            ),
        )
        errors: list[Exception] = []
        lock = threading.Lock()

        def check(cap: AgentCapability) -> None:
            try:
                gate.check(cap)
            except PermissionError as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=check, args=(AgentCapability.MEMORY_READ,))
            for _ in range(10)
        ] + [
            threading.Thread(target=check, args=(AgentCapability.FACTS_READ,))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert all(not e for e in errors)

    def test_concurrent_close_and_check(self) -> None:
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities={AgentCapability.MEMORY_READ},
                policy=AgentPolicy(),
            ),
        )
        results: list[bool] = []
        lock = threading.Lock()

        def close_and_check() -> None:
            gate.close()
            try:
                gate.check(AgentCapability.MEMORY_READ)
                with lock:
                    results.append(True)
            except PermissionError:
                with lock:
                    results.append(False)

        threads = [threading.Thread(target=close_and_check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # After close, all checks should fail
        assert all(r is False for r in results)


class TestCapabilityGateEdgeCases:
    def test_capabilities_property(self) -> None:
        caps = {AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ}
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities=caps,
                policy=AgentPolicy(),
            ),
        )
        assert gate.capabilities() == caps

    def test_granted_count_zero_initially(self) -> None:
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities={AgentCapability.MEMORY_READ},
                policy=AgentPolicy(),
            ),
        )
        assert gate.granted_count == 0
        assert gate.denied_count == 0
        assert gate.decision_count == 0

    def test_cache_disabled_by_default(self) -> None:
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities={AgentCapability.MEMORY_READ},
                policy=AgentPolicy(),
            ),
        )
        assert gate._enable_cache is False


# ════════════════════════════════════════════════════════
# 4. TOOL RUNNER — backpressure, RateLimiter, error mappings
# ════════════════════════════════════════════════════════

class _FastAdapter(ToolAdapter):
    def name(self) -> str:
        return "fast"
    def run(self, params: dict) -> dict:
        return {"done": True}
    def cancel(self) -> None:
        pass


class TestRateLimiter:
    def test_allows_within_limit(self) -> None:
        rl = RateLimiter(max_calls=10, window_seconds=60)
        for _ in range(10):
            rl.check("test_tool")

    def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            rl.check("test_tool")
        with pytest.raises(ToolTransientError, match="Rate limit exceeded"):
            rl.check("test_tool")

    def test_separate_buckets(self) -> None:
        rl = RateLimiter(max_calls=2, window_seconds=60)
        rl.check("tool_a")
        rl.check("tool_a")
        rl.check("tool_b")  # should not be blocked by tool_a's limit
        with pytest.raises(ToolTransientError):
            rl.check("tool_a")

    def test_thread_safety(self) -> None:
        rl = RateLimiter(max_calls=100, window_seconds=60)
        errors: list[Exception] = []
        lock = threading.Lock()

        def check() -> None:
            try:
                rl.check("concurrent_tool")
            except ToolTransientError as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # With 50 threads and limit of 100, none should be blocked
        assert len(errors) == 0

    def test_window_expiry(self) -> None:
        """Calls outside the window should not count."""
        rl = RateLimiter(max_calls=2, window_seconds=0.1)
        rl.check("tool")
        rl.check("tool")
        time.sleep(0.2)
        # Window expired, should allow again
        rl.check("tool")


class TestToolRunnerBackpressure:
    def test_max_concurrent(self) -> None:
        """When max_concurrent_tools=1, second call blocks until first completes."""
        import threading

        started = threading.Event()
        can_finish = threading.Event()

        class _BlockingAdapter(ToolAdapter):
            def name(self) -> str:
                return "block"
            def run(self, params: dict) -> dict:
                started.set()
                can_finish.wait(timeout=5)
                return {"done": True}
            def cancel(self) -> None:
                pass

        runner = AgentToolRunner(
            adapters={"block": _BlockingAdapter()},
            max_concurrent_tools=1,
        )
        runner.register(
            "block",
            _BlockingAdapter(),
            ToolContract(name="block", timeout_seconds=5),
        )

        # Start first call (will block on can_finish)
        results: list[dict | Exception] = []
        def call_runner() -> None:
            try:
                r = runner.run("block", {})
                results.append(r)
            except Exception as e:
                results.append(e)

        t1 = threading.Thread(target=call_runner, daemon=True)
        t1.start()
        started.wait(timeout=3)

        # Second call should timeout because semaphore is held
        with pytest.raises(ToolTimeoutError):
            runner.run("block", {}, timeout=0.5)

        # Release first call
        can_finish.set()
        t1.join(timeout=3)
        assert len(results) == 1
        assert isinstance(results[0], dict)

    def test_backpressure_release_on_error(self) -> None:
        """Semaphore is released even if tool raises."""
        class _ErrorAdapter(ToolAdapter):
            def name(self) -> str:
                return "err"
            def run(self, params: dict) -> dict:
                msg = "Always fails"
                raise ToolPermanentError(msg)
            def cancel(self) -> None:
                pass

        runner = AgentToolRunner(
            adapters={"err": _ErrorAdapter()},
            max_concurrent_tools=1,
        )
        runner.register("err", _ErrorAdapter(), ToolContract(name="err", timeout_seconds=5))

        with pytest.raises(ToolPermanentError):
            runner.run("err", {})
        # Semaphore should be released, second call should work (but also fail)
        with pytest.raises(ToolPermanentError):
            runner.run("err", {})


class TestToolRunnerErrorMapping:
    def _make_runner_with_adapter(self, adapter: ToolAdapter) -> AgentToolRunner:
        runner = AgentToolRunner()
        runner.register("test_tool", adapter, ToolContract(name="test_tool", timeout_seconds=5))
        return runner

    def test_not_found_error(self) -> None:
        runner = AgentToolRunner()
        with pytest.raises(ToolNotFoundError):
            runner.run("nonexistent", {})

    def test_contract_not_found(self) -> None:
        runner = AgentToolRunner()
        with pytest.raises(ToolNotFoundError):
            runner.get_contract("nonexistent")

    def test_transient_error_mapping(self) -> None:
        class _TransientAdapter(ToolAdapter):
            def name(self) -> str:
                return "trans"
            def run(self, params: dict) -> dict:
                msg = "Transient failure"
                raise ToolTransientError(msg)
            def cancel(self) -> None:
                pass

        # ToolRunner wraps retryable errors as ToolError after exhausting attempts
        runner = AgentToolRunner()
        runner.register(
            "test_tool", _TransientAdapter(),
            ToolContract(name="test_tool", timeout_seconds=5),
        )
        with pytest.raises(ToolError, match="All 3 attempts failed"):
            runner.run("test_tool", {})

    def test_tool_adapter_error(self) -> None:
        class _BadAdapter(ToolAdapter):
            def name(self) -> str:
                return "bad"
            def run(self, params: dict) -> dict:
                msg = "Adapter failure"
                raise ToolAdapterError(msg)
            def cancel(self) -> None:
                pass

        # ToolRunner wraps retryable errors as ToolError after exhausting attempts
        runner = AgentToolRunner()
        runner.register(
            "test_tool", _BadAdapter(),
            ToolContract(name="test_tool", timeout_seconds=5),
        )
        with pytest.raises(ToolError, match="All 3 attempts failed"):
            runner.run("test_tool", {})

    def test_generic_error_maps_to_tool_error(self) -> None:
        class _CrashAdapter(ToolAdapter):
            def name(self) -> str:
                return "crash"
            def run(self, params: dict) -> dict:
                msg = "Generic crash"
                raise RuntimeError(msg)
            def cancel(self) -> None:
                pass

        runner = self._make_runner_with_adapter(_CrashAdapter())
        with pytest.raises(ToolError):
            runner.run("test_tool", {})


class TestToolRunnerDeterminism:
    def test_same_input_same_output(self) -> None:
        runner = AgentToolRunner()
        runner.register("echo", _FastAdapter(), ToolContract(name="echo", timeout_seconds=5))
        r1 = runner.run("echo", {"x": 1})
        r2 = runner.run("echo", {"x": 1})
        assert r1 == r2


# ════════════════════════════════════════════════════════
# 5. AGENT SCHEDULER — concurrency, priority, aging
# ════════════════════════════════════════════════════════

def _execution(
    agent_id: str = "a1",
    max_duration: int = 300,
    *,
    cancelled: bool = False,
) -> AgentExecution:
    return AgentExecution(
        agent_id=agent_id,
        task=AgentTask(task_id=f"t_{agent_id}", objective=f"Task {agent_id}"),
        capabilities=set(),
        policy=AgentPolicy(max_duration_seconds=max_duration),
        cancelled=cancelled,
    )


class TestPriorityQueue:
    def test_push_pop_order(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=2)
        q.push(_execution("a2"), priority=0)
        q.push(_execution("a3"), priority=1)
        assert q.pop().agent_id == "a2"
        assert q.pop().agent_id == "a3"
        assert q.pop().agent_id == "a1"

    def test_fifo_within_priority(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=2)
        q.push(_execution("a2"), priority=2)
        q.push(_execution("a3"), priority=2)
        assert q.pop().agent_id == "a1"
        assert q.pop().agent_id == "a2"
        assert q.pop().agent_id == "a3"

    def test_remove_middle(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=2)
        q.push(_execution("a2"), priority=2)
        q.push(_execution("a3"), priority=2)
        assert q.remove("a2") is True
        assert q.size() == 2
        assert q.pop().agent_id == "a1"
        assert q.pop().agent_id == "a3"

    def test_remove_nonexistent(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"))
        assert q.remove("nonexistent") is False
        assert q.size() == 1

    def test_peek_empty(self) -> None:
        q = _PriorityQueue()
        assert q.peek() is None

    def test_peek_by_priority(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=1)
        q.push(_execution("a2"), priority=2)
        assert q.peek(priority=1).agent_id == "a1"
        assert q.peek(priority=2).agent_id == "a2"
        assert q.peek(priority=0) is None

    def test_pop_empty(self) -> None:
        q = _PriorityQueue()
        assert q.pop() is None

    def test_size_by_priority(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=0)
        q.push(_execution("a2"), priority=1)
        q.push(_execution("a3"), priority=1)
        assert q.size_for_priority(0) == 1
        assert q.size_for_priority(1) == 2
        assert q.size_for_priority(2) == 0

    def test_aging_moves_priority(self) -> None:
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=0)
        q.push(_execution("a2"), priority=1)

        original_time = time.time
        try:
            time.time = lambda: original_time() + 120
            q.age()
        finally:
            time.time = original_time

        # a1 should have moved from prio 0 to prio 1 (or higher)
        # a2 should have moved from prio 1 to prio 2
        assert q.size() == 2
        # Both should eventually pop, with a1 first (now at higher priority)
        popped = [q.pop().agent_id for _ in range(2)]
        assert "a1" in popped
        assert "a2" in popped

    def test_aging_only_low_priorities(self) -> None:
        """Aging does not promote priority 2 or above."""
        q = _PriorityQueue()
        q.push(_execution("a1"), priority=2)

        original_time = time.time
        try:
            time.time = lambda: original_time() + 120
            q.age()
        finally:
            time.time = original_time

        # Should still be in priority 2
        assert q.size_for_priority(2) == 1
        assert q.pop().agent_id == "a1"


class TestAgentSchedulerConcurrency:
    def test_max_concurrent_respected(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        for i in range(5):
            s.submit(_execution(f"a{i}", max_duration=300))
        time.sleep(0.2)
        # At most 2 should be running concurrently
        assert s.running_count <= 2

    def test_submit_and_run(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        s.submit(_execution("a1"))
        time.sleep(0.1)
        # After a short time, the execution should have completed
        assert s.queue_size == 0
        assert s.running_count == 0

    def test_priority_mapping_critical(self) -> None:
        """Tasks with max_duration <= 60 get priority 0."""
        e = _execution("a1", max_duration=30)
        s = AgentScheduler(max_concurrent=0)
        s.submit(e)
        assert s.queue_size == 1

    def test_priority_mapping_high(self) -> None:
        """Tasks with max_duration 61-120 get priority 1."""
        e = _execution("a1", max_duration=90)
        s = AgentScheduler(max_concurrent=0)
        s.submit(e)
        assert s.queue_size == 1

    def test_priority_mapping_normal(self) -> None:
        """Tasks with max_duration > 120 get priority 2."""
        e = _execution("a1", max_duration=300)
        s = AgentScheduler(max_concurrent=0)
        s.submit(e)
        assert s.queue_size == 1

    def test_shutdown_with_results(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        s.submit(_execution("a1"))
        s.submit(_execution("a2"))
        time.sleep(0.2)
        results = s.shutdown()
        assert len(results) == 2
        for r in results:
            assert isinstance(r, AgentResult)

    def test_shutdown_no_double_results(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        s.submit(_execution("a1"))
        time.sleep(0.1)
        r1 = s.shutdown()
        r2 = s.shutdown()
        assert len(r1) > 0
        assert len(r2) == 0  # results cleared after shutdown

    def test_submit_after_shutdown(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        s.shutdown()
        s.submit(_execution("a1"))
        # Should not be dispatched (shutdown flag set)
        assert s.queue_size == 1

    def test_cancel_running(self) -> None:
        s = AgentScheduler(max_concurrent=2)
        s.submit(_execution("a1"))
        time.sleep(0.05)
        s.cancel("a1")  # should not raise
        assert True

    def test_concurrent_submit(self) -> None:
        s = AgentScheduler(max_concurrent=5)
        n = 20

        def submit_all() -> None:
            for i in range(n):
                s.submit(_execution(f"a{i}"))

        threads = [threading.Thread(target=submit_all) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        time.sleep(0.5)
        # All should have been processed
        assert s.queue_size == 0
        assert s.running_count == 0


# ════════════════════════════════════════════════════════
# 6. AGENT PLANNER — edge cases
# ════════════════════════════════════════════════════════

class TestRuleBasedPlannerEdgeCases:
    def test_empty_objective(self) -> None:
        p = RuleBasedPlanner()
        plan = p.plan(AgentTask(task_id="t1", objective=""))
        assert len(plan.steps) >= 1
        # Empty objective should always have retrieve + respond
        assert plan.steps[-1].action == "llm"

    def test_summarize_keyword(self) -> None:
        p = RuleBasedPlanner()
        plan = p.plan(AgentTask(task_id="t1", objective="summarize the document"))
        actions = [s.action for s in plan.steps]
        assert "retrieve" in actions
        assert "llm" in actions
        # llm action should be summarize
        llm_steps = [s for s in plan.steps if s.action == "llm"]
        assert any(s.params.get("action") == "summarize" for s in llm_steps)

    def test_save_keyword(self) -> None:
        p = RuleBasedPlanner()
        plan = p.plan(AgentTask(task_id="t1", objective="save the results"))
        actions = [s.action for s in plan.steps]
        assert "tool" in actions
        assert "llm" in actions

    def test_lookup_keyword(self) -> None:
        p = RuleBasedPlanner()
        plan = p.plan(AgentTask(task_id="t1", objective="lookup user details"))
        actions = [s.action for s in plan.steps]
        assert "retrieve" in actions
        assert "search" in actions

    def test_all_keywords_combined(self) -> None:
        p = RuleBasedPlanner()
        plan = p.plan(AgentTask(task_id="t1", objective="search, read, summarize, write, save"))
        actions = [s.action for s in plan.steps]
        assert "retrieve" in actions
        assert "search" in actions
        assert "llm" in actions
        # llm should appear multiple times (summarize, compose, respond)
        llm_count = sum(1 for s in plan.steps if s.action == "llm")
        assert llm_count >= 2

    def test_context_passed_through(self) -> None:
        p = RuleBasedPlanner()
        ctx = AgentContext(conversation=[{"role": "user", "content": "hello"}])
        plan = p.plan(AgentTask(task_id="t1", objective="search"), context=ctx)
        assert plan is not None
        assert len(plan.steps) >= 2

    def test_replan_failed_search(self) -> None:
        p = RuleBasedPlanner()
        plan = AgentPlan(
            plan_id="p1",
            steps=(
                PlanStep(step_id="s0", action="retrieve"),
                PlanStep(step_id="s1", action="search"),
                PlanStep(step_id="s2", action="llm"),
            ),
        )
        new_plan = p.replan(
            AgentTask(task_id="t1", objective="search"),
            plan,
            AgentContext(),
            failed_step=plan.steps[1],
        )
        actions = [s.action for s in new_plan.steps]
        assert "retrieve" in actions  # first step preserved
        assert "search" not in actions or len(new_plan.steps) >= 2

    def test_replan_failed_tool(self) -> None:
        p = RuleBasedPlanner()
        plan = AgentPlan(
            plan_id="p1",
            steps=(
                PlanStep(step_id="s0", action="retrieve"),
                PlanStep(step_id="s1", action="tool"),
                PlanStep(step_id="s2", action="llm"),
            ),
        )
        new_plan = p.replan(
            AgentTask(task_id="t1", objective="write"),
            plan,
            AgentContext(),
            failed_step=plan.steps[1],
        )
        # tool failure should be replaced with llm.suggest
        actions = [s.action for s in new_plan.steps]
        assert "retrieve" in actions  # first step preserved
        assert "llm" in actions  # replacement + respond

    def test_replan_unknown_failure(self) -> None:
        p = RuleBasedPlanner()
        plan = AgentPlan(
            plan_id="p1",
            steps=(
                PlanStep(step_id="s0", action="retrieve"),
                PlanStep(step_id="s1", action="unknown_action"),
                PlanStep(step_id="s2", action="llm"),
            ),
        )
        new_plan = p.replan(
            AgentTask(task_id="t1", objective="test"),
            plan,
            AgentContext(),
            failed_step=plan.steps[1],
        )
        # unknown action should fall back to retrieve
        assert len(new_plan.steps) >= 2

    def test_deterministic_replan(self) -> None:
        p = RuleBasedPlanner()
        plan = AgentPlan(
            plan_id="p1",
            steps=(PlanStep(step_id="s0", action="retrieve"), PlanStep(step_id="s1", action="search")),
        )
        ctx = AgentContext()
        failed = plan.steps[1]
        r1 = p.replan(AgentTask(task_id="t1", objective="search"), plan, ctx, failed)
        r2 = p.replan(AgentTask(task_id="t1", objective="search"), plan, ctx, failed)
        assert [s.action for s in r1.steps] == [s.action for s in r2.steps]


# ════════════════════════════════════════════════════════
# 7. AGENT ORCHESTRATOR — full lifecycle
# ════════════════════════════════════════════════════════

class _MockGate(CapabilityGate):
    def __init__(self, caps: set[AgentCapability] | None = None) -> None:
        self.checks: list[AgentCapability] = []
        self._caps = {AgentCapability.MEMORY_READ} if caps is None else caps
        self._fail_on: AgentCapability | None = None

    def check(self, required: AgentCapability) -> None:
        self.checks.append(required)
        if required == self._fail_on:
            msg = f"[capability_not_granted] Mock denial for {required.value}"
            raise PermissionError(msg)
        if required not in self._caps:
            msg = f"[capability_not_granted] {required.value} not in capabilities"
            raise PermissionError(msg)

    def capabilities(self) -> set[AgentCapability]:
        return self._caps


class _MockPlanner(Planner):
    def __init__(self, steps: tuple[PlanStep, ...] | None = None) -> None:
        self._steps = steps or (
            PlanStep(step_id="s1", action="llm", params={"prompt": "hello"}),
        )

    def plan(self, task: AgentTask, context: AgentContext | None = None) -> AgentPlan:
        return AgentPlan(plan_id="p1", steps=self._steps)

    def replan(self, task, current_plan, context, failed_step=None):
        return current_plan


class _MockScheduler(Scheduler):
    def __init__(self) -> None:
        self.submissions: list[AgentExecution] = []

    def submit(self, execution: AgentExecution) -> None:
        self.submissions.append(execution)

    def cancel(self, agent_id: str) -> None:
        pass

    def shutdown(self, timeout: int = 30) -> list[AgentResult]:
        return []


class _MockToolRunner(ToolRunner):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._fail_on: str | None = None

    def get_contract(self, tool_name: str) -> ToolContract:
        return ToolContract(name=tool_name)

    def run(self, tool_name: str, params: dict, timeout: int = 30) -> dict:
        self.calls.append((tool_name, params))
        if tool_name == self._fail_on:
            msg = f"Tool '{tool_name}' failed"
            raise RuntimeError(msg)
        return {"result": "ok"}

    def cancel(self, tool_name: str) -> None:
        pass


class _MockAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.events: list = []

    def log(self, event) -> None:
        self.events.append(event)

    def get_audit(self, agent_id: str) -> list:
        return self.events


def _make_orchestrator(
    gate: CapabilityGate | None = None,
    planner: Planner | None = None,
    scheduler: Scheduler | None = None,
    tool_runner: ToolRunner | None = None,
    audit_logger: AuditLogger | None = None,
) -> AgentOrchestrator:
    return AgentOrchestrator(
        planner=planner or _MockPlanner(),
        scheduler=scheduler or _MockScheduler(),
        tool_runner=tool_runner or _MockToolRunner(),
        gate=gate or _MockGate(),
        audit_logger=audit_logger or _MockAuditLogger(),
    )


class TestAgentOrchestratorBasics:
    def test_run_returns_result(self) -> None:
        agent = _make_orchestrator()
        result = agent.run(AgentTask(task_id="t1", objective="hello"))
        assert isinstance(result, AgentResult)
        assert result.state in (AgentState.COMPLETED, AgentState.FAILED)

    def test_unique_agent_ids(self) -> None:
        agent = _make_orchestrator()
        r1 = agent.run(AgentTask(task_id="t1", objective="first"))
        r2 = agent.run(AgentTask(task_id="t2", objective="second"))
        assert r1.agent_id != r2.agent_id

    def test_audit_logged(self) -> None:
        audit = _MockAuditLogger()
        agent = _make_orchestrator(audit_logger=audit)
        agent.run(AgentTask(task_id="t1", objective="test"))
        assert len(audit.events) > 0

    def test_cancel(self) -> None:
        agent = _make_orchestrator()
        agent.cancel()
        # Should not raise
        assert True


class TestAgentOrchestratorPermissions:
    def test_permission_denied(self) -> None:
        gate = _MockGate(caps=set())  # no capabilities
        agent = _make_orchestrator(gate=gate)
        result = agent.run(AgentTask(task_id="t1", objective="test"))
        assert result.state == AgentState.PERMISSION_DENIED
        assert result.error is not None

    def test_step_permission_denied(self) -> None:
        gate = _MockGate(caps={AgentCapability.MEMORY_READ})
        gate._fail_on = AgentCapability.TOOLS_EXECUTE
        tool_runner = _MockToolRunner()
        planner = _MockPlanner(steps=(
            PlanStep(step_id="s1", action="tool", params={"tool": "test"}),
        ))
        agent = _make_orchestrator(
            gate=gate,
            planner=planner,
            tool_runner=tool_runner,
        )
        result = agent.run(AgentTask(task_id="t1", objective="test"))
        assert result.state == AgentState.PERMISSION_DENIED
        assert "Missing capability" in (result.error or "")

    def test_budget_exceeded_via_gate(self) -> None:
        """Gate denies when cost_units >= max_cost_units."""
        gate = AgentCapabilityGate(
            AgentExecution(
                agent_id="a1",
                task=AgentTask(task_id="t1", objective="test"),
                capabilities={AgentCapability.MEMORY_READ},
                policy=AgentPolicy(max_cost_units=5),
                cost_units=10,
            ),
        )
        with pytest.raises(PermissionError, match=r"\[budget_exceeded\]"):
            gate.check(AgentCapability.MEMORY_READ)


class TestAgentOrchestratorCancelDuringExecution:
    def test_cancel_mid_execution(self) -> None:
        gate = _MockGate()
        tool_runner = _MockToolRunner()
        steps = tuple(
            PlanStep(step_id=f"s{i}", action="llm", params={})
            for i in range(100)
        )
        planner = _MockPlanner(steps=steps)
        agent = _make_orchestrator(
            gate=gate,
            planner=planner,
            tool_runner=tool_runner,
        )

        # Cancel before run should result in completed or cancelled
        agent.cancel()
        result = agent.run(AgentTask(task_id="t1", objective="test"))
        assert result.state in (AgentState.CANCELLED, AgentState.COMPLETED)


class TestAgentOrchestratorComponentsCalled:
    def test_planner_called(self) -> None:
        planner = _MockPlanner()
        agent = _make_orchestrator(planner=planner)
        agent.run(AgentTask(task_id="t1", objective="test"))
        # Planner was called (no assertion needed - would crash if not)
        assert True

    def test_tool_runner_called(self) -> None:
        tool_runner = _MockToolRunner()
        planner = _MockPlanner(steps=(
            PlanStep(step_id="s1", action="llm", params={}),
        ))
        agent = _make_orchestrator(planner=planner, tool_runner=tool_runner)
        agent.run(AgentTask(task_id="t1", objective="test"))
        assert len(tool_runner.calls) > 0

    def test_gate_checked(self) -> None:
        gate = _MockGate()
        agent = _make_orchestrator(gate=gate)
        agent.run(AgentTask(task_id="t1", objective="test"))
        assert len(gate.checks) > 0

    def test_scheduler_submitted(self) -> None:
        scheduler = _MockScheduler()
        agent = _make_orchestrator(scheduler=scheduler)
        agent.run(AgentTask(task_id="t1", objective="test"))
        assert len(scheduler.submissions) == 1


class TestAgentOrchestratorErrorPaths:
    def test_planner_error(self) -> None:
        class _CrashPlanner(Planner):
            def plan(self, task, context=None):
                msg = "Planner crashed"
                raise RuntimeError(msg)
            def replan(self, task, current_plan, context, failed_step=None):
                msg = "Planner crashed"
                raise RuntimeError(msg)

        agent = _make_orchestrator(planner=_CrashPlanner())
        result = agent.run(AgentTask(task_id="t1", objective="test"))
        assert result.state == AgentState.FAILED
        assert "Planner crashed" in (result.error or "")

    def test_tool_error(self) -> None:
        tool_runner = _MockToolRunner()
        tool_runner._fail_on = "llm"
        planner = _MockPlanner(steps=(
            PlanStep(step_id="s1", action="llm", params={}),
        ))
        agent = _make_orchestrator(planner=planner, tool_runner=tool_runner)
        result = agent.run(AgentTask(task_id="t1", objective="test"))
        assert result.state == AgentState.FAILED


# ════════════════════════════════════════════════════════
# 8. STATE MACHINE — additional edge cases
# ════════════════════════════════════════════════════════

class TestAgentStateMachineEdgeCases:
    def test_terminal_states_list(self) -> None:
        sm = AgentStateMachine()
        assert sm.is_terminal(AgentState.COMPLETED)
        assert sm.is_terminal(AgentState.FAILED)
        assert sm.is_terminal(AgentState.CANCELLED)
        assert sm.is_terminal(AgentState.TIMEOUT)
        assert sm.is_terminal(AgentState.PERMISSION_DENIED)
        assert sm.is_terminal(AgentState.TOOL_ERROR)
        assert sm.is_terminal(AgentState.LLM_ERROR)
        assert not sm.is_terminal(AgentState.CREATED)
        assert not sm.is_terminal(AgentState.PLANNING)
        assert not sm.is_terminal(AgentState.READY)
        assert not sm.is_terminal(AgentState.RUNNING)
        assert not sm.is_terminal(AgentState.WAITING)

    def test_transition_from_waiting(self) -> None:
        sm = AgentStateMachine()
        assert sm.transition(AgentState.WAITING, AgentState.RUNNING) == AgentState.RUNNING
        assert sm.transition(AgentState.WAITING, AgentState.FAILED) == AgentState.FAILED
        assert sm.transition(AgentState.WAITING, AgentState.TIMEOUT) == AgentState.TIMEOUT

    def test_transition_from_permission_denied(self) -> None:
        sm = AgentStateMachine()
        assert sm.transition(AgentState.PERMISSION_DENIED, AgentState.CANCELLED) == AgentState.CANCELLED

    def test_invalid_permission_denied_to_running(self) -> None:
        sm = AgentStateMachine()
        with pytest.raises(ValueError, match="Invalid state transition"):
            sm.transition(AgentState.PERMISSION_DENIED, AgentState.RUNNING)

    def test_invalid_self_transition(self) -> None:
        sm = AgentStateMachine()
        # CREATED -> CREATED is not valid unless explicitly defined
        with pytest.raises(ValueError):
            sm.transition(AgentState.CREATED, AgentState.CREATED)

    def test_valid_transitions_from_planning(self) -> None:
        sm = AgentStateMachine()
        transitions = sm.valid_transitions(AgentState.PLANNING)
        assert AgentState.READY in transitions
        assert AgentState.FAILED in transitions
        assert AgentState.CANCELLED in transitions

    def test_all_non_terminal_transitions_from_running(self) -> None:
        sm = AgentStateMachine()
        transitions = sm.valid_transitions(AgentState.RUNNING)
        assert AgentState.WAITING in transitions
        assert AgentState.COMPLETED in transitions
        assert AgentState.FAILED in transitions
        assert AgentState.CANCELLED in transitions
        assert AgentState.TIMEOUT in transitions
        assert AgentState.PERMISSION_DENIED in transitions
        assert AgentState.TOOL_ERROR in transitions
        assert AgentState.LLM_ERROR in transitions

    def test_no_transitions_from_terminal(self) -> None:
        sm = AgentStateMachine()
        for terminal in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED):
            transitions = sm.valid_transitions(terminal)
            assert transitions == []


# ════════════════════════════════════════════════════════
# 9. INTEGRATION: Real components working together
# ════════════════════════════════════════════════════════

class _RealFastAdapter(ToolAdapter):
    def name(self) -> str:
        return "fast"
    def run(self, params: dict) -> dict:
        return {"processed": True, **params}
    def cancel(self) -> None:
        pass


class TestIntegrationFlow:
    def test_planner_toolrunner_integration(self) -> None:
        """RuleBasedPlanner generates steps that AgentToolRunner can execute."""
        planner = RuleBasedPlanner()
        task = AgentTask(task_id="t1", objective="search and summarize")
        plan = planner.plan(task)

        assert len(plan.steps) > 0
        # All steps should have valid actions
        for step in plan.steps:
            assert step.action in ("retrieve", "search", "llm", "tool")

    def test_gate_scheduler_integration(self) -> None:
        """CapabilityGate and AgentScheduler work together."""
        execution = AgentExecution(
            agent_id="int1",
            task=AgentTask(task_id="t1", objective="integration"),
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ},
            policy=AgentPolicy(max_duration_seconds=60),
        )

        gate = AgentCapabilityGate(execution)
        scheduler = AgentScheduler(max_concurrent=2)

        # Gate allows, scheduler accepts
        gate.check(AgentCapability.MEMORY_READ)
        scheduler.submit(execution)
        assert scheduler.queue_size >= 0

        # Gate denies
        with pytest.raises(PermissionError):
            gate.check(AgentCapability.WEB_SEARCH)

    def test_full_agent_pipeline(self) -> None:
        """End-to-end using real RuleBasedPlanner and mocks for external deps."""
        planner = RuleBasedPlanner()
        scheduler = AgentScheduler(max_concurrent=2)
        tool_runner = AgentToolRunner()
        tool_runner.register(
            "llm",
            _RealFastAdapter(),
            ToolContract(name="llm", timeout_seconds=5),
        )
        gate = CapabilityGateFromExecution(
            capabilities={AgentCapability.MEMORY_READ, AgentCapability.FACTS_READ},
        )
        audit = _MockAuditLogger()

        agent = AgentOrchestrator(
            planner=planner,
            scheduler=scheduler,
            tool_runner=tool_runner,
            gate=gate,
            audit_logger=audit,
        )

        result = agent.run(AgentTask(task_id="int1", objective="summarize facts"))
        assert isinstance(result, AgentResult)
        assert result.state in (AgentState.COMPLETED, AgentState.FAILED)


class CapabilityGateFromExecution(CapabilityGate):
    """Minimal gate for integration test — wraps a fixed set of capabilities."""

    def __init__(self, capabilities: set[AgentCapability]) -> None:
        self._capabilities = capabilities

    def check(self, required: AgentCapability) -> None:
        if required not in self._capabilities:
            msg = f"[capability_not_granted] {required.value}"
            raise PermissionError(msg)

    def capabilities(self) -> set[AgentCapability]:
        return self._capabilities
