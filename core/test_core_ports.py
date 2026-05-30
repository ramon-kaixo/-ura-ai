"""Tests for core: port_manager, port_registry, port_assigner, port_proxy, port_conflict_monitor."""

import logging


logging.disable(logging.CRITICAL)


class TestPortManager:
    def test_imports(self):
        from core.port_manager import get_port_manager

        assert callable(get_port_manager)

    def test_singleton(self):
        from core.port_manager import get_port_manager

        pm = get_port_manager()
        assert pm is not None


class TestPortRegistry:
    def test_imports(self):
        from core.port_registry import PortRegistry

        assert PortRegistry is not None


class TestPortAssigner:
    def test_imports(self):
        from core.port_assigner import PortAssigner

        assert PortAssigner is not None


class TestPortProxy:
    def test_imports(self):
        from core.port_proxy import PortProxy

        assert PortProxy is not None


class TestPortConflictMonitor:
    def test_imports(self):
        from core.port_conflict_monitor import get_conflict_monitor

        assert callable(get_conflict_monitor)
