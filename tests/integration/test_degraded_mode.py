from __future__ import annotations

import threading

from motor.core.state import DegradedMode


class TestDegradedModeSingleton:
    def test_instancia_returns_same_object(self):
        d1 = DegradedMode.instancia()
        d2 = DegradedMode.instancia()
        assert d1 is d2

    def test_new_instance_not_singleton(self):
        d1 = DegradedMode.instancia()
        d2 = DegradedMode()
        assert d1 is not d2
        assert isinstance(d2, DegradedMode)


class TestDegradedModeInitial:
    def test_status_empty(self):
        dm = DegradedMode()
        s = dm.status()
        assert s["global"] is False
        assert s["degraded"] == []
        assert s["healthy"] is True
        assert s["since"] == {}

    def test_not_degraded_initially(self):
        dm = DegradedMode()
        assert dm.is_degraded("anything") is False


class TestDegradedModeDegradation:
    def test_mark_degraded_first_time_returns_false(self):
        dm = DegradedMode()
        assert dm.mark_degraded("sys_a") is False

    def test_mark_degraded_second_time_returns_true(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_a")
        assert dm.mark_degraded("sys_a") is True

    def test_is_degraded_after_mark(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_b")
        assert dm.is_degraded("sys_b") is True

    def test_multiple_subsystems_independent(self):
        dm = DegradedMode()
        dm.mark_degraded("a")
        dm.mark_degraded("b")
        assert dm.is_degraded("a") is True
        assert dm.is_degraded("b") is True
        assert dm.is_degraded("c") is False

    def test_status_reflects_degraded_subsystems(self):
        dm = DegradedMode()
        dm.mark_degraded("qdrant")
        s = dm.status()
        assert s["global"] is True
        assert "qdrant" in s["degraded"]
        assert "qdrant" in s["since"]
        assert s["healthy"] is False

    def test_status_sorted(self):
        dm = DegradedMode()
        dm.mark_degraded("z")
        dm.mark_degraded("a")
        assert dm.status()["degraded"] == ["a", "z"]


class TestDegradedModeRecovery:
    def test_mark_healthy_first_time_returns_false(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_c")
        assert dm.mark_healthy("sys_c") is False

    def test_mark_healthy_after_healthy_returns_true(self):
        dm = DegradedMode()
        assert dm.mark_healthy("never_degraded") is True

    def test_is_not_degraded_after_recovery(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_d")
        dm.mark_healthy("sys_d")
        assert dm.is_degraded("sys_d") is False

    def test_status_global_recovers(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_e")
        dm.mark_healthy("sys_e")
        s = dm.status()
        assert s["global"] is False
        assert s["healthy"] is True
        assert s["degraded"] == []

    def test_recovery_then_redegrade(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_f")
        dm.mark_healthy("sys_f")
        assert dm.is_degraded("sys_f") is False
        dm.mark_degraded("sys_f")
        assert dm.is_degraded("sys_f") is True

    def test_partial_recovery(self):
        dm = DegradedMode()
        dm.mark_degraded("x")
        dm.mark_degraded("y")
        dm.mark_healthy("x")
        s = dm.status()
        assert s["global"] is True
        assert s["degraded"] == ["y"]

    def test_idempotent_mark_healthy(self):
        dm = DegradedMode()
        dm.mark_degraded("sys_g")
        dm.mark_healthy("sys_g")
        assert dm.mark_healthy("sys_g") is True


class TestDegradedModeThreadSafety:
    def test_concurrent_degrade_and_recover(self):
        dm = DegradedMode()
        n = 100
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker(i: int) -> None:
            name = f"concurrent_{i}"
            try:
                dm.mark_degraded(name)
                assert dm.is_degraded(name)
                dm.mark_healthy(name)
                assert not dm.is_degraded(name)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0


class TestDegradedModeInvalidStates:
    def test_mark_healthy_nonexistent(self):
        dm = DegradedMode()
        assert dm.mark_healthy("nonexistent") is True
