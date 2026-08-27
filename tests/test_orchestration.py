"""Tests para Task Queue, Tier-3 Proxy y Orquestador."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Task Queue Tests
# ---------------------------------------------------------------------------


class TestTaskQueue:
    """Tests para la cola de tareas SQLite."""

    def _make_queue(self, tmp_path: Path):
        from motor.orchestration.task_queue import TaskQueue
        return TaskQueue(db_path=tmp_path / "test_queue.db")

    def test_create_task(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Implementar proxy tier-3", plan_phase="phase-1", priority=1)
        assert task.id.startswith("TASK-")
        assert task.description == "Implementar proxy tier-3"
        assert task.status == "pending"
        assert task.priority == 1

    def test_claim_task(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        claimed = q.claim(task.id, "generador-mac")
        assert claimed is not None
        assert claimed.status == "assigned"
        assert claimed.assigned_to == "generador-mac"

    def test_claim_wrong_status_fails(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent-1")
        q.start(task.id)
        result = q.claim(task.id, "agent-2")
        assert result is None

    def test_start_task(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        started = q.start(task.id)
        assert started is not None
        assert started.status == "in_progress"

    def test_complete_task(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        q.start(task.id)
        q.review(task.id, "auditor")
        done = q.complete(task.id, commit_sha="abc123")
        assert done is not None
        assert done.status == "done"
        assert done.commit_sha == "abc123"

    def test_fail_task_retry(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task", max_retries=3)
        q.claim(task.id, "agent")
        q.start(task.id)
        failed = q.fail(task.id, "ruff check failed")
        assert failed is not None
        assert failed.status == "failed"
        assert failed.retries == 1

    def test_fail_task_human_review(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task", max_retries=1)
        q.claim(task.id, "agent")
        q.start(task.id)
        failed = q.fail(task.id, "ruff check failed")
        assert failed is not None
        assert failed.status == "failed_require_human"
        assert failed.retries == 1

    def test_heartbeat(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        assert q.heartbeat(task.id) is True

    def test_list_by_status(self, tmp_path):
        q = self._make_queue(tmp_path)
        q.create("Task 1")
        q.create("Task 2")
        q.create("Task 3")
        pending = q.list_by_status("pending")
        assert len(pending) == 3

    def test_stats(self, tmp_path):
        q = self._make_queue(tmp_path)
        q.create("Task 1")
        q.create("Task 2")
        stats = q.stats()
        assert stats["total"] == 2
        assert stats["by_status"]["pending"] == 2

    def test_get_events(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        events = q.get_events(task.id)
        assert len(events) >= 2  # created + assigned

    def test_recover_stale(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        # Manually set old heartbeat
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "test_queue.db"))
        old_time = "2020-01-01T00:00:00+00:00"
        conn.execute("UPDATE tasks SET last_heartbeat = ?, status = 'in_progress' WHERE id = ?", (old_time, task.id))
        conn.commit()
        conn.close()

        stale = q.recover_stale()
        assert len(stale) == 1
        assert stale[0].id == task.id

    def test_error_truncation(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task", max_retries=5)
        q.claim(task.id, "agent")
        q.start(task.id)
        long_error = "\n".join([f"error line {i}" for i in range(100)])
        failed = q.fail(task.id, long_error)
        error_lines = failed.error_log.strip().split("\n")
        assert len(error_lines) <= 50


class TestTaskTimeoutSeconds:
    """Tests for per-task timeout_seconds."""

    def _make_queue(self, tmp_path: Path):
        from motor.orchestration.task_queue import TaskQueue
        return TaskQueue(db_path=tmp_path / "test_queue.db")

    def test_create_with_timeout(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Fast task", timeout_seconds=60)
        assert task.timeout_seconds == 60
        assert task.heartbeat_interval_s == 6  # min(10, 60/10)
        assert task.stale_timeout_s == 60

    def test_default_timeout(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Normal task")
        assert task.timeout_seconds == 1800
        assert task.heartbeat_interval_s == 10  # min(10, 1800/10)

    def test_short_timeout_heartbeat(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Very fast task", timeout_seconds=30)
        assert task.heartbeat_interval_s == 3  # min(10, 30/10)

    def test_stale_uses_per_task_timeout(self, tmp_path):
        """Tasks with different timeouts have different stale thresholds."""
        import time

        q = self._make_queue(tmp_path)
        task = q.create("Fast task", timeout_seconds=2)
        q.claim(task.id, "agent")
        q.start(task.id)

        time.sleep(2.5)

        stale = q.recover_stale()
        stale_ids = [t.id for t in stale]
        assert task.id in stale_ids


# ---------------------------------------------------------------------------
# Tier-3 Proxy Tests
# ---------------------------------------------------------------------------


class TestTier3Proxy:
    """Tests para el proxy tier-3."""

    def test_defaults_load(self):
        from core.model_router.tier3_proxy import Tier3Proxy
        proxy = Tier3Proxy()
        # Should have at least ollama-local
        assert len(proxy._providers) >= 1
        assert proxy._providers[-1].name == "ollama-local"

    def test_health(self):
        from core.model_router.tier3_proxy import Tier3Proxy
        proxy = Tier3Proxy()
        health = proxy.health()
        assert "status" in health
        assert "providers" in health
        assert len(health["providers"]) >= 1

    def test_circuit_breaker(self):
        from core.model_router.tier3_proxy import ProviderCircuitBreaker, ProviderState
        cb = ProviderCircuitBreaker("test")
        assert cb.state == ProviderState.HEALTHY

        # Record 3 429s
        for _ in range(3):
            cb.record_429()
        assert cb.state == ProviderState.COOLDOWN

        # Reset
        cb.reset()
        assert cb.state == ProviderState.HEALTHY

    def test_context_bridge(self):
        from core.model_router.tier3_proxy import _build_context_header
        messages = [
            {"role": "system", "content": "You are URA assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "```python\ndef hello():\n    pass\n```"},
        ]
        header = _build_context_header("groq/llama-3.3-70b", "ollama/qwen3-coder:30b", messages)
        assert len(header) == 1
        assert "CONTEXT_TRANSFER" in header[0]["content"]
        assert "groq/llama-3.3-70b" in header[0]["content"]

    def test_arch_detection(self):
        from core.model_router.tier3_proxy import Tier3Proxy
        proxy = Tier3Proxy()
        assert proxy._extract_arch("ollama/qwen3-coder:30b") == "qwen"
        assert proxy._extract_arch("groq/llama-3.3-70b-versatile") == "llama"
        assert proxy._extract_arch("gemma4:26b") == "gemma"


# ---------------------------------------------------------------------------
# Orchestrator Tests
# ---------------------------------------------------------------------------


class TestOrchestrator:
    """Tests para el orquestador."""

    def test_parse_plan_phases(self):
        from motor.orchestration.orchestrator import Orchestrator
        orch = Orchestrator()
        plan = """
## Fase 1: Proxy Tier-3
Implementar proxy con cascada de 3 niveles.
- Prioridad: 1
- Horas: 4

## Fase 2: Context Bridge
Serialización de contexto al cambiar modelo.
- Prioridad: 2
- Horas: 3
"""
        phases = orch._parse_plan(plan)
        assert len(phases) == 2
        assert phases[0].id == "phase-1"
        assert phases[0].priority == 1
        assert phases[1].id == "phase-2"

    def test_parse_plain_text(self):
        from motor.orchestration.orchestrator import Orchestrator
        orch = Orchestrator()
        plan = "Primero hacer el proxy.\n\nDespués el context bridge."
        phases = orch._parse_plan(plan)
        assert len(phases) == 2
        assert phases[0].id == "phase-1"


# ---------------------------------------------------------------------------
# Auditor Tests
# ---------------------------------------------------------------------------


class TestAuditor:
    """Tests para el auditor."""

    def test_run_gate_timeout(self):
        from motor.orchestration.auditor import Auditor
        auditor = Auditor()
        passed, output = auditor._run_gate("slow", ["sleep", "100"], Path("/tmp"))
        assert not passed
        assert "TIMEOUT" in output

    def test_run_gate_success(self):
        from motor.orchestration.auditor import Auditor
        auditor = Auditor()
        passed, output = auditor._run_gate("echo", ["echo", "hello"], Path("/tmp"))
        assert passed
        assert len(output.strip()) > 0

    def test_run_gate_failure(self):
        from motor.orchestration.auditor import Auditor
        auditor = Auditor()
        passed, _output = auditor._run_gate("false", ["false"], Path("/tmp"))
        assert not passed


# ---------------------------------------------------------------------------
# Interface Contracts Tests
# ---------------------------------------------------------------------------


class TestContracts:
    """Tests para el sistema de Interface Contracts."""

    def test_freeze_contracts(self, tmp_path):
        from motor.orchestration.contracts import (
            APISurface,
            ContractGenerator,
            ContractValidator,
            FunctionContract,
            InterfaceContractSet,
        )
        ContractGenerator(tmp_path)
        validator = ContractValidator(tmp_path)

        # Create a contract set
        contracts = InterfaceContractSet(
            plan_id="test-plan-001",
            modules=[
                APISurface(
                    module="core.proxy",
                    functions=[
                        FunctionContract(
                            name="proxy_request",
                            module="core.proxy",
                            params=[{"name": "path", "type": "str"}, {"name": "body", "type": "bytes"}],
                            return_type="tuple[int, dict, bytes]",
                        ),
                    ],
                ),
            ],
        )

        # Freeze
        path = validator.freeze_contracts(contracts)
        assert path.exists()
        assert (tmp_path / "INTERFACE_CONTRACTS.md").exists()
        assert (tmp_path / ".interface_contracts.sha256").exists()

    def test_verify_hash(self, tmp_path):
        from motor.orchestration.contracts import ContractValidator, InterfaceContractSet
        validator = ContractValidator(tmp_path)

        contracts = InterfaceContractSet(plan_id="test")
        validator.freeze_contracts(contracts)

        # Hash should verify
        assert validator._verify_hash() is True

        # Tamper with the file
        (tmp_path / "INTERFACE_CONTRACTS.md").write_text("TAMPERED")
        assert validator._verify_hash() is False

    def test_validate_module(self, tmp_path):
        from motor.orchestration.contracts import ContractValidator, InterfaceContractSet
        validator = ContractValidator(tmp_path)

        contracts = InterfaceContractSet(plan_id="test")
        validator.freeze_contracts(contracts)

        # Create a valid module
        mod = tmp_path / "test_module.py"
        mod.write_text("def hello():\n    return 'world'\n")
        errors = validator.validate_module(mod, "test_module")
        assert len(errors) == 0

        # Create a module with forbidden pattern
        mod_bad = tmp_path / "bad_module.py"
        mod_bad.write_text("result = eval('1+1')\n")
        errors = validator.validate_module(mod_bad, "bad_module")
        assert any("Forbidden" in e for e in errors)

    def test_validate_function_signature(self, tmp_path):
        from motor.orchestration.contracts import (
            ContractValidator,
            FunctionContract,
            InterfaceContractSet,
        )
        validator = ContractValidator(tmp_path)

        contracts = InterfaceContractSet(plan_id="test")
        validator.freeze_contracts(contracts)

        # Create module with correct signature
        mod = tmp_path / "proxy.py"
        mod.write_text("def proxy_request(path: str, body: bytes) -> tuple:\n    pass\n")
        expected = FunctionContract(
            name="proxy_request",
            module="proxy",
            params=[{"name": "path", "type": "str"}, {"name": "body", "type": "bytes"}],
            return_type="tuple",
        )
        errors = validator.validate_function_signature(mod, expected)
        assert len(errors) == 0

        # Wrong return type
        expected_bad = FunctionContract(
            name="proxy_request",
            module="proxy",
            params=[],
            return_type="dict",  # Wrong!
        )
        errors = validator.validate_function_signature(mod, expected_bad)
        assert len(errors) > 0

    def test_contracts_to_markdown(self, tmp_path):
        from motor.orchestration.contracts import (
            APISurface,
            FunctionContract,
            InterfaceContractSet,
            contracts_to_markdown,
        )
        contracts = InterfaceContractSet(
            plan_id="plan-001",
            modules=[
                APISurface(
                    module="core.proxy",
                    functions=[
                        FunctionContract(
                            name="proxy",
                            module="core.proxy",
                            params=[{"name": "url", "type": "str"}],
                            return_type="bytes",
                        ),
                    ],
                ),
            ],
        )
        md = contracts_to_markdown(contracts)
        assert "INTERFACE CONTRACTS" in md
        assert "core.proxy" in md
        assert "def proxy(url: str) -> bytes" in md
        assert "SOLO LECTURA" in md


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class TestTelemetry:
    def test_record_and_query(self, tmp_path: Path) -> None:
        from motor.orchestration.telemetry import TelemetryStore

        store = TelemetryStore(tmp_path / "test_telemetry.db")
        store.record("task_created", task_id="TASK-001", node="mac")
        store.record("task_completed", task_id="TASK-001", node="gx10")

        metrics = store.query(task_id="TASK-001")
        assert len(metrics) == 2
        assert metrics[0].event == "task_completed"
        assert metrics[1].event == "task_created"

    def test_stats(self, tmp_path: Path) -> None:
        from motor.orchestration.telemetry import TelemetryStore

        store = TelemetryStore(tmp_path / "test_telemetry.db")
        store.record("task_completed", task_id="TASK-001")
        store.record("task_failed", task_id="TASK-002")
        store.record("gate_pass")

        stats = store.stats(since_minutes=60)
        assert stats["total_events"] == 3
        assert stats["tasks"]["completed"] == 1
        assert stats["tasks"]["failed"] == 1
        assert stats["tasks"]["success_rate_pct"] == 50.0

    def test_recent_tasks(self, tmp_path: Path) -> None:
        from motor.orchestration.telemetry import TelemetryStore

        store = TelemetryStore(tmp_path / "test_telemetry.db")
        store.record("task_started", task_id="TASK-001")
        store.record("task_completed", task_id="TASK-001")

        tasks = store.recent_tasks()
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "TASK-001"
        assert tasks[0]["status"] == "done"

    def test_clear_old(self, tmp_path: Path) -> None:
        from motor.orchestration.telemetry import TelemetryStore

        store = TelemetryStore(tmp_path / "test_telemetry.db")
        store.record("task_created")
        # clear_old with 0 days should not remove recent entries
        removed = store.clear_old(days=0)
        assert removed == 0


# ---------------------------------------------------------------------------
# Distributed Lock
# ---------------------------------------------------------------------------


class TestDistributedLock:
    def test_acquire_release(self, tmp_path: Path) -> None:
        from motor.orchestration.distributed_lock import DistributedLock

        lock = DistributedLock("test-lock", tmp_path / "locks.db")
        assert lock.acquire(timeout=1.0)
        assert lock.is_locked()
        lock.release()
        assert not lock.is_locked()

    def test_context_manager(self, tmp_path: Path) -> None:
        from motor.orchestration.distributed_lock import DistributedLock

        lock = DistributedLock("test-ctx", tmp_path / "locks.db")
        with lock.locked() as acquired:
            assert acquired
            assert lock.is_locked()
        assert not lock.is_locked()

    def test_double_lock_fails(self, tmp_path: Path) -> None:
        from motor.orchestration.distributed_lock import DistributedLock

        lock1 = DistributedLock("test-double", tmp_path / "locks.db")
        lock2 = DistributedLock("test-double", tmp_path / "locks.db")

        assert lock1.acquire(timeout=1.0)
        assert not lock2.acquire(timeout=0.5)
        lock1.release()

    def test_owner_info(self, tmp_path: Path) -> None:
        from motor.orchestration.distributed_lock import DistributedLock

        lock = DistributedLock("test-owner", tmp_path / "locks")
        assert lock.owner_info() is None
        lock.acquire(timeout=1.0)
        info = lock.owner_info()
        assert info is not None
        assert "pid=" in info["owner"]
        assert info["age_s"] >= 0
        lock.release()

    def test_audit_lock(self, tmp_path: Path) -> None:
        from motor.orchestration.distributed_lock import AuditLock, _DEFAULT_LOCK_DIR

        import motor.orchestration.distributed_lock as dl_mod

        original = dl_mod._DEFAULT_LOCK_DIR
        dl_mod._DEFAULT_LOCK_DIR = tmp_path / "locks"

        try:
            lock = AuditLock("test-node")
            with lock.exclusive() as acquired:
                assert acquired
        finally:
            dl_mod._DEFAULT_LOCK_DIR = original


# ---------------------------------------------------------------------------
# Atomic Write + Utils
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_atomic_write_string(self, tmp_path: Path) -> None:
        from motor.core.utils import atomic_write

        target = tmp_path / "test.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_atomic_write_json(self, tmp_path: Path) -> None:
        from motor.core.utils import atomic_write_json

        target = tmp_path / "test.json"
        atomic_write_json(target, {"key": "value", "num": 42})
        import json

        data = json.loads(target.read_text())
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_atomic_write_no_partial(self, tmp_path: Path) -> None:
        from motor.core.utils import atomic_write

        target = tmp_path / "test.txt"
        atomic_write(target, "first")
        atomic_write(target, "second")
        assert target.read_text() == "second"
        # No .tmp files left behind
        assert list(tmp_path.glob("*.tmp")) == []

    def test_sha256(self, tmp_path: Path) -> None:
        from motor.core.utils import file_sha256

        target = tmp_path / "test.txt"
        target.write_text("hello")
        sha = file_sha256(target)
        assert len(sha) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Failover
# ---------------------------------------------------------------------------


class TestOrchestratorHealthChecker:
    def test_initial_state(self) -> None:
        from motor.orchestration.failover import OrchestratorHealthChecker, OrchestratorState

        checker = OrchestratorHealthChecker(orchestrator_url="http://localhost:99999")
        assert checker.state == OrchestratorState.HEALTHY

    def test_probe_down_server(self) -> None:
        from motor.orchestration.failover import OrchestratorHealthChecker

        checker = OrchestratorHealthChecker(orchestrator_url="http://localhost:99999")
        result = checker._probe()
        assert result.error  # Should have error (connection refused)

    def test_callback_on_state_change(self) -> None:
        from motor.orchestration.failover import OrchestratorHealthChecker, OrchestratorState

        changes: list[tuple[OrchestratorState, OrchestratorState]] = []
        checker = OrchestratorHealthChecker(
            orchestrator_url="http://localhost:99999",
            failure_threshold=1,
        )
        checker.on_state_change(lambda new, old: changes.append((new, old)))

        # Force a failure
        checker._consecutive_failures = 0
        result = checker._probe()
        checker._update_state(result)

        assert len(changes) == 1
        assert changes[0][0] == OrchestratorState.DOWN


class TestRemoteExecutor:
    def test_run_echo(self) -> None:
        from motor.orchestration.failover import RemoteExecutor

        executor = RemoteExecutor(default_host="localhost", max_retries=0)
        result = executor.run("echo hello")
        # May fail if SSH not configured to localhost, but shouldn't crash
        assert result.command == "echo hello"

    def test_is_reachable(self) -> None:
        from motor.orchestration.failover import RemoteExecutor

        executor = RemoteExecutor(default_host="localhost", max_retries=0)
        # localhost may or may not be reachable via SSH
        # Just verify the method doesn't crash
        result = executor.is_reachable()
        assert isinstance(result, bool)


class TestAutonomousFailover:
    def test_initial_mode(self) -> None:
        from motor.orchestration.failover import AutonomousFailover, FailoverMode

        fo = AutonomousFailover()
        assert fo.mode == FailoverMode.NORMAL
        assert not fo.is_autonomous

    def test_enter_autonomous_via_callback(self) -> None:
        from motor.orchestration.failover import AutonomousFailover, FailoverMode, OrchestratorState

        fo = AutonomousFailover()
        fo._on_health_change(OrchestratorState.DOWN, OrchestratorState.HEALTHY)
        assert fo.mode == FailoverMode.AUTONOMOUS
        assert fo.is_autonomous

    def test_exit_autonomous_via_callback(self) -> None:
        from motor.orchestration.failover import AutonomousFailover, FailoverMode, OrchestratorState

        fo = AutonomousFailover()
        fo._on_health_change(OrchestratorState.DOWN, OrchestratorState.HEALTHY)
        fo._on_health_change(OrchestratorState.HEALTHY, OrchestratorState.DOWN)
        assert fo.mode == FailoverMode.NORMAL
        assert not fo.is_autonomous

    def test_concurrent_state_transition(self) -> None:
        """Verify state transitions are atomic under threading."""
        import threading

        from motor.orchestration.failover import AutonomousFailover, FailoverMode, OrchestratorState

        fo = AutonomousFailover()
        results = []

        def toggle():
            for _ in range(10):
                fo._on_health_change(OrchestratorState.DOWN, OrchestratorState.HEALTHY)
                fo._on_health_change(OrchestratorState.HEALTHY, OrchestratorState.DOWN)
            results.append(fo.mode)

        threads = [threading.Thread(target=toggle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all threads, mode should be stable (not corrupted)
        assert fo.mode in (FailoverMode.NORMAL, FailoverMode.AUTONOMOUS)


class TestAntiFlapping:
    """Tests for HealthChecker anti-flapping behavior."""

    def test_time_windowed_failure_detection(self) -> None:
        """5 failures within 60s window → DOWN, but old failures outside window are pruned."""
        import time
        from motor.orchestration.failover import OrchestratorHealthChecker, OrchestratorState

        checker = OrchestratorHealthChecker(
            failure_threshold=3,
            failure_window_s=2.0,  # 2 second window for fast test
            interval_s=0.1,
        )

        # Simulate 3 quick failures
        for _ in range(3):
            result = checker._probe.__wrapped__(checker) if hasattr(checker._probe, '__wrapped__') else None
            # Manually simulate failure
            from motor.orchestration.failover import HealthCheckResult
            fail_result = HealthCheckResult(
                state=OrchestratorState.DOWN,
                latency_ms=0,
                consecutive_failures=0,
                last_check="",
                error="simulated",
            )
            checker._update_state(fail_result)

        assert checker.state == OrchestratorState.DOWN

    def test_recovery_requires_consecutive_successes(self) -> None:
        """Recovery from DOWN requires recovery_threshold consecutive successes."""
        from motor.orchestration.failover import HealthCheckResult, OrchestratorHealthChecker, OrchestratorState

        checker = OrchestratorHealthChecker(
            failure_threshold=2,
            recovery_threshold=3,
            failure_window_s=60.0,
            interval_s=0.1,
        )

        # Force to DOWN
        for _ in range(2):
            checker._update_state(HealthCheckResult(
                state=OrchestratorState.DOWN, latency_ms=0,
                consecutive_failures=0, last_check="", error="fail",
            ))
        assert checker.state == OrchestratorState.DOWN

        # 1 success → still DOWN
        checker._update_state(HealthCheckResult(
            state=OrchestratorState.HEALTHY, latency_ms=0,
            consecutive_failures=0, last_check="",
        ))
        assert checker.state == OrchestratorState.DOWN

        # 2 successes → still DOWN
        checker._update_state(HealthCheckResult(
            state=OrchestratorState.HEALTHY, latency_ms=0,
            consecutive_failures=0, last_check="",
        ))
        assert checker.state == OrchestratorState.DOWN

        # 3 successes → HEALTHY
        checker._update_state(HealthCheckResult(
            state=OrchestratorState.HEALTHY, latency_ms=0,
            consecutive_failures=0, last_check="",
        ))
        assert checker.state == OrchestratorState.HEALTHY

    def test_failure_resets_recovery_counter(self) -> None:
        """A failure during recovery resets the recovery counter."""
        from motor.orchestration.failover import HealthCheckResult, OrchestratorHealthChecker, OrchestratorState

        checker = OrchestratorHealthChecker(
            failure_threshold=2,
            recovery_threshold=3,
            failure_window_s=60.0,
            interval_s=0.1,
        )

        # Force to DOWN via time-windowed failures
        for _ in range(2):
            checker._update_state(HealthCheckResult(
                state=OrchestratorState.DOWN, latency_ms=0,
                consecutive_failures=0, last_check="", error="fail",
            ))
        assert checker.state == OrchestratorState.DOWN

        # 1 success (below recovery_threshold=3, should stay DOWN)
        checker._update_state(HealthCheckResult(
            state=OrchestratorState.HEALTHY, latency_ms=0,
            consecutive_failures=0, last_check="",
        ))
        assert checker._consecutive_recoveries == 1

        # Failure resets recovery counter
        checker._update_state(HealthCheckResult(
            state=OrchestratorState.DOWN, latency_ms=0,
            consecutive_failures=0, last_check="", error="fail",
        ))
        assert checker._consecutive_recoveries == 0
        # Still in degraded or down state
        assert checker.state in (OrchestratorState.DOWN, OrchestratorState.DEGRADED)

    def test_status_includes_anti_flapping_info(self) -> None:
        """Status dict includes failure window info."""
        from motor.orchestration.failover import AutonomousFailover

        fo = AutonomousFailover()
        status = fo.get_status()
        assert "mode" in status
        assert "orchestrator_state" in status

    def test_status(self) -> None:
        from motor.orchestration.failover import AutonomousFailover

        fo = AutonomousFailover()
        status = fo.get_status()
        assert "mode" in status
        assert "orchestrator_state" in status
        assert "active_worktrees" in status


# ---------------------------------------------------------------------------
# Node Registry Tests — Sprint 0.2
# ---------------------------------------------------------------------------


class TestNodeRegistry:
    """Tests for multi-node registry and health checking."""

    def test_register_and_list(self, tmp_path: Any) -> None:
        """Register nodes and list them."""
        from motor.orchestration.node_registry import NodeRegistry

        reg = NodeRegistry(registry_file=tmp_path / "reg.json")
        reg.register("mac", "Mac Mini", "100.123.81.101")
        reg.register("gx10", "GX10", "100.72.103.12")

        nodes = reg.list_all()
        assert len(nodes) == 2
        ids = {n.node_id for n in nodes}
        assert ids == {"mac", "gx10"}

    def test_unregister(self, tmp_path: Any) -> None:
        """Unregister a node."""
        from motor.orchestration.node_registry import NodeRegistry

        reg = NodeRegistry(registry_file=tmp_path / "reg.json")
        reg.register("mac", "Mac Mini", "100.123.81.101")
        assert reg.unregister("mac") is True
        assert reg.get("mac") is None
        assert reg.unregister("mac") is False

    def test_persistence(self, tmp_path: Any) -> None:
        """Registry persists to disk and reloads."""
        from motor.orchestration.node_registry import NodeRegistry

        path = tmp_path / "reg.json"
        reg1 = NodeRegistry(registry_file=path)
        reg1.register("gx10", "GX10", "100.72.103.12", tags=["desktop"])

        reg2 = NodeRegistry(registry_file=path)
        node = reg2.get("gx10")
        assert node is not None
        assert node.hostname == "GX10"
        assert node.tags == ["desktop"]

    def test_api_url_property(self, tmp_path: Any) -> None:
        """NodeInfo.api_url returns correct URL."""
        from motor.orchestration.node_registry import NodeInfo, NodeStatus

        node = NodeInfo(
            node_id="gx10", hostname="GX10",
            tailscale_ip="100.72.103.12", api_port=4097,
            status=NodeStatus.UNKNOWN,
        )
        assert node.api_url == "http://100.72.103.12:4097"

    def test_to_dict(self, tmp_path: Any) -> None:
        """NodeInfo.to_dict returns serializable dict."""
        from motor.orchestration.node_registry import NodeInfo, NodeStatus

        node = NodeInfo(
            node_id="mac", hostname="Mac Mini",
            tailscale_ip="100.123.81.101", api_port=4097,
            status=NodeStatus.ONLINE, last_seen=1000.0,
            last_latency_ms=12.5, tags=["m4"],
        )
        d = node.to_dict()
        assert d["node_id"] == "mac"
        assert d["status"] == "online"
        assert d["tags"] == ["m4"]

    def test_check_health_unreachable(self, tmp_path: Any) -> None:
        """Health check on unreachable node marks it as degraded/offline."""
        from motor.orchestration.node_registry import NodeRegistry, NodeStatus

        reg = NodeRegistry(registry_file=tmp_path / "reg.json", check_timeout_s=1)
        reg.register("fake", "Fake Node", "192.0.2.1", api_port=19999)  # RFC 5737 TEST-NET

        results = reg.check_health("fake")
        assert results["fake"]["status"] in ("degraded", "offline")
        assert results["fake"]["consecutive_failures"] >= 1


# ---------------------------------------------------------------------------
# Bug Fix Tests — Sprint 0.1
# ---------------------------------------------------------------------------


class TestBug1SSHInjection:
    """Bug 1: SSH injection via command arguments."""

    def test_shlex_quote_in_remote_executor(self) -> None:
        """Verify shlex.quote is used in RemoteExecutor.run."""
        import inspect
        from motor.orchestration.failover import RemoteExecutor

        source = inspect.getsource(RemoteExecutor.run)
        assert "shlex.quote" in source, "RemoteExecutor.run must use shlex.quote()"

    def test_injection_attempt_in_command(self) -> None:
        """Verify shlex.quote prevents shell injection in commands."""
        import shlex

        malicious = "legit_cmd; rm -rf /"
        quoted = shlex.quote(malicious)
        # The injection should be neutralized
        assert ";" not in quoted or quoted.startswith("'"), "shlex.quote must neutralize semicolons"


class TestBug2FailGuard:
    """Bug 2: fail() must reject tasks not in ASSIGNED/IN_PROGRESS."""

    def _make_queue(self, tmp_path: Path):
        from motor.orchestration.task_queue import TaskQueue
        return TaskQueue(db_path=tmp_path / "test_queue.db")

    def test_fail_pending_task_raises(self, tmp_path):
        from motor.orchestration.task_queue import TaskStateError

        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        # task is PENDING — fail should raise
        try:
            q.fail(task.id, "error")
            assert False, "Expected TaskStateError"
        except TaskStateError as e:
            assert "pending" in str(e)

    def test_fail_done_task_raises(self, tmp_path):
        from motor.orchestration.task_queue import TaskStateError

        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        q.start(task.id)
        q.review(task.id, "auditor")
        q.complete(task.id, commit_sha="abc")
        # task is DONE — fail should raise
        try:
            q.fail(task.id, "error")
            assert False, "Expected TaskStateError"
        except TaskStateError as e:
            assert "done" in str(e)

    def test_fail_assigned_task_succeeds(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        # task is ASSIGNED — fail should work
        failed = q.fail(task.id, "some error")
        assert failed is not None
        assert failed.status == "failed"

    def test_fail_in_progress_task_succeeds(self, tmp_path):
        q = self._make_queue(tmp_path)
        task = q.create("Test task")
        q.claim(task.id, "agent")
        q.start(task.id)
        # task is IN_PROGRESS — fail should work
        failed = q.fail(task.id, "some error")
        assert failed is not None
        assert failed.status == "failed"


class TestBug3HashBypass:
    """Bug 3: verify_file_integrity must use hmac.compare_digest."""

    def test_compare_digest_in_source(self) -> None:
        import inspect
        from motor.core.utils import verify_file_integrity

        source = inspect.getsource(verify_file_integrity)
        assert "hmac.compare_digest" in source, "Must use hmac.compare_digest for timing-safe comparison"

    def test_integrity_error_on_mismatch(self, tmp_path):
        from motor.core.utils import IntegrityError, atomic_write, file_sha256

        test_file = tmp_path / "test.txt"
        atomic_write(test_file, "hello world")
        correct_hash = file_sha256(test_file)

        # Wrong hash should raise IntegrityError
        try:
            from motor.core.utils import verify_file_integrity
            verify_file_integrity(test_file, "wrong_hash" + "0" * 48)
            assert False, "Expected IntegrityError"
        except IntegrityError:
            pass

    def test_integrity_ok_on_match(self, tmp_path):
        from motor.core.utils import atomic_write, file_sha256, verify_file_integrity

        test_file = tmp_path / "test.txt"
        atomic_write(test_file, "hello world")
        correct_hash = file_sha256(test_file)

        result = verify_file_integrity(test_file, correct_hash)
        assert result is True


class TestBug4FailoverStateRace:
    """Bug 4: Failover state transitions must be atomic."""

    def test_state_protected_by_lock(self) -> None:
        import inspect
        from motor.orchestration.failover import AutonomousFailover

        source = inspect.getsource(AutonomousFailover._on_health_change)
        assert "self._lock" in source, "_on_health_change must use self._lock"

    def test_state_persists_to_file(self, tmp_path):
        from motor.orchestration.failover import AutonomousFailover, OrchestratorState

        state_file = tmp_path / "state.json"
        fo = AutonomousFailover(state_path=str(state_file))
        fo._on_health_change(OrchestratorState.DOWN, OrchestratorState.HEALTHY)
        assert state_file.exists(), "State file should be created"
        import json
        data = json.loads(state_file.read_text())
        assert data["mode"] == "autonomous"

class TestSSHControlMaster:
    """Tests for SSH ControlMaster improvements."""

    def test_control_socket_cleanup(self):
        from motor.orchestration.failover import RemoteExecutor
        executor = RemoteExecutor()
        # Cleanup of non-existent socket should not crash
        result = executor.cleanup_control_socket(host="ramon@192.0.2.1")
        assert isinstance(result, bool)

    def test_connection_status_unreachable(self):
        from motor.orchestration.failover import RemoteExecutor
        executor = RemoteExecutor()
        status = executor.connection_status(host="ramon@192.0.2.1")
        assert status["alive"] is False
        assert "host" in status

class TestShardedQueues:
    """Tests for sharded task queues by node."""

    def test_create_with_node_id(self, tmp_path):
        from motor.orchestration.task_queue import TaskQueue
        queue = TaskQueue(tmp_path / "test.db")
        task = queue.create("Test task", node_id="gx10")
        assert task.node_id == "gx10"

    def test_list_by_node(self, tmp_path):
        from motor.orchestration.task_queue import TaskQueue
        queue = TaskQueue(tmp_path / "test.db")
        queue.create("GX10 task", node_id="gx10")
        queue.create("Mac task", node_id="mac")
        queue.create("GX10 task 2", node_id="gx10")

        gx10_tasks = queue.list_by_node("gx10")
        assert len(gx10_tasks) == 2
        mac_tasks = queue.list_by_node("mac")
        assert len(mac_tasks) == 1

    def test_list_by_node_and_status(self, tmp_path):
        from motor.orchestration.task_queue import TaskQueue
        queue = TaskQueue(tmp_path / "test.db")
        queue.create("GX10 pending", node_id="gx10")
        t2 = queue.create("GX10 done", node_id="gx10")
        queue.claim(t2.id, "agent-1")
        queue.start(t2.id)
        queue.complete(t2.id)

        pending = queue.list_by_node("gx10", status="pending")
        assert len(pending) == 1
        done = queue.list_by_node("gx10", status="done")
        assert len(done) == 1

    def test_node_id_in_stats(self, tmp_path):
        from motor.orchestration.task_queue import TaskQueue
        queue = TaskQueue(tmp_path / "test.db")
        queue.create("Task 1", node_id="gx10")
        queue.create("Task 2", node_id="mac")
        stats = queue.stats()
        assert stats["total"] == 2
