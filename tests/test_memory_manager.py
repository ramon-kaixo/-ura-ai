"""Tests for core/memory_manager.py — RAM management module."""


class TestMemoryManagerImports:
    """Verify module imports cleanly and exposes expected API."""

    def test_module_imports_without_error(self):
        import core.memory_manager

        assert core.memory_manager is not None

    def test_memory_manager_class_exists(self):
        from core.memory_manager import MemoryManager

        assert MemoryManager is not None

    def test_process_config_dataclass_exists(self):
        from core.memory_manager import ProcessConfig

        assert ProcessConfig is not None

    def test_process_state_dataclass_exists(self):
        from core.memory_manager import ProcessState

        assert ProcessState is not None

    def test_memory_manager_instantiates(self):
        from core.memory_manager import MemoryManager

        mm = MemoryManager()
        assert hasattr(mm, "configs")
        assert hasattr(mm, "state")
        assert hasattr(mm, "historial_memoria")

    def test_memory_manager_has_key_methods(self):
        from core.memory_manager import MemoryManager

        mm = MemoryManager()
        for method in (
            "ejecutar_ciclo",
            "congelar_proceso",
            "optimizar_memoria",
            "limpiar_procesos_zombi",
            "obtener_memoria_total",
        ):
            assert hasattr(mm, method), f"Missing method: {method}"
            assert callable(getattr(mm, method)), f"Not callable: {method}"

    def test_process_config_fields(self):
        from core.memory_manager import ProcessConfig

        cfg = ProcessConfig(
            name="test",
            pattern="test",
            max_inactive_minutes=5,
            min_memory_mb=50,
            priority=3,
        )
        assert cfg.name == "test"
        assert cfg.pattern == "test"
        assert cfg.priority == 3

    def test_module_level_constants(self):
        import core.memory_manager as mm
        from pathlib import Path

        assert isinstance(mm.PROJECT_ROOT, Path)
        assert isinstance(mm.CONFIG_FILE, Path)
        assert isinstance(mm.LOG_FILE, Path)
