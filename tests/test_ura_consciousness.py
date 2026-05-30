#!/usr/bin/env python3
"""
Pruebas unitarias para módulos de conciencia de URA
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))


class TestURAMetrics:
    """Pruebas para el sistema de métricas."""

    def test_record_usage(self):
        """Prueba registrar uso de un nivel."""
        from ura_metrics import get_ura_metrics

        metrics = get_ura_metrics()

        initial_count = metrics.metrics["emotions"].usage_count
        initial_rt = metrics.metrics["emotions"].response_time_ms
        initial_impact = metrics.metrics["emotions"].impact_score

        metrics.record_usage("emotions", 15.5, 0.8)

        assert metrics.metrics["emotions"].usage_count == initial_count + 1
        # Moving average calculation
        expected_rt = (initial_rt * initial_count + 15.5) / (initial_count + 1)
        expected_impact = (initial_impact * initial_count + 0.8) / (initial_count + 1)
        assert metrics.metrics["emotions"].response_time_ms == expected_rt
        assert metrics.metrics["emotions"].impact_score == expected_impact

    def test_get_top_levels_by_impact(self):
        """Prueba obtener niveles con mayor impacto."""
        from ura_metrics import get_ura_metrics

        metrics = get_ura_metrics()

        # Registrar algunos usos
        metrics.record_usage("emotions", 10.0, 0.9)
        metrics.record_usage("theory_of_mind", 15.0, 0.7)

        top_levels = metrics.get_top_levels_by_impact(3)
        assert len(top_levels) <= 3
        assert "emotions" in top_levels


class TestURADynamicConfig:
    """Pruebas para la configuración dinámica."""

    def test_get_current_profile(self):
        """Prueba obtener perfil actual."""
        from ura_dynamic_config import get_ura_dynamic_config

        config = get_ura_dynamic_config()

        profile = config.get_current_profile()
        assert profile.profile_name == "balanced"
        assert len(profile.active_levels) > 0

    def test_set_profile(self):
        """Prueba establecer perfil."""
        from ura_dynamic_config import get_ura_dynamic_config

        config = get_ura_dynamic_config()

        assert config.set_profile("minimal")
        assert config.current_profile == "minimal"

        # Restaurar perfil original
        config.set_profile("balanced")

    def test_auto_select_profile(self):
        """Prueba selección automática de perfil."""
        from ura_dynamic_config import get_ura_dynamic_config

        config = get_ura_dynamic_config()

        profile = config.auto_select_profile(0.9)
        assert profile == "minimal"

        profile = config.auto_select_profile(0.6)
        assert profile == "balanced"

        profile = config.auto_select_profile(0.3)
        assert profile == "performance"


class TestURARollback:
    """Pruebas para el sistema de rollback."""

    def test_create_snapshot(self):
        """Prueba crear snapshot."""
        from ura_rollback import get_ura_rollback

        rollback = get_ura_rollback()

        # Crear archivo de prueba
        test_file = Path.home() / ".ura" / "test.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"test": "data"}')

        snapshot_id = rollback.create_snapshot("test", test_file)
        assert snapshot_id.startswith("snapshot_")

        # Limpiar
        test_file.unlink()
        if test_file.exists():
            test_file.unlink()

    def test_get_latest_snapshot(self):
        """Prueba obtener snapshot más reciente."""
        from ura_rollback import get_ura_rollback

        rollback = get_ura_rollback()

        # Crear archivo de prueba
        test_file = Path.home() / ".ura" / "test.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('{"test": "data"}')

        rollback.create_snapshot("test", test_file)
        snapshot = rollback.get_latest_snapshot("test")

        assert snapshot is not None
        assert snapshot.level_name == "test"

        # Limpiar
        test_file.unlink()


class TestURAAutoPruning:
    """Pruebas para el auto-pruning."""

    def test_prune_level(self):
        """Prueba prune de un nivel."""
        from ura_auto_pruning import get_ura_auto_pruning

        pruning = get_ura_auto_pruning()

        # Crear archivo de prueba con datos antiguos
        test_file = Path.home() / ".ura" / "emotions.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)

        old_data = [{"timestamp": "2020-01-01T00:00:00", "emotion": "test"}]
        test_file.write_text(json.dumps(old_data))

        # Prune
        pruning.prune_level("emotions")

        # Verificar que se eliminó el dato antiguo
        with open(test_file) as f:
            data = json.load(f)

        assert len(data) == 0 or len(data) < len(old_data)

        # Limpiar
        test_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
