#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/constants.py."""

import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.constants import (
    MAX_CICLO_S,
    MODELOS,
    NERVIOSO,
    RUFF,
    SCRIPTS,
    URA_ROOT,
)


class TestConstants:
    """Tests para constantes compartidas."""

    @pytest.mark.unit
    def test_max_ciclo_s(self):
        assert MAX_CICLO_S == 300
        assert isinstance(MAX_CICLO_S, int)

    @pytest.mark.unit
    def test_modelos_estructura(self):
        assert isinstance(MODELOS, dict)
        assert "orquestador" in MODELOS
        assert "ejecutor" in MODELOS
        assert "reparador_rapido" in MODELOS
        assert "reparador_potente" in MODELOS
        assert "revisor" in MODELOS

    @pytest.mark.unit
    def test_modelos_valores_no_vacios(self):
        for key, value in MODELOS.items():
            assert isinstance(value, str)
            assert len(value) > 0

    @pytest.mark.unit
    def test_nervioso_path(self):
        assert isinstance(NERVIOSO, Path)
        assert "nervioso" in str(NERVIOSO)

    @pytest.mark.unit
    def test_ruff_path(self):
        assert isinstance(RUFF, str)
        assert "ruff" in RUFF.lower()

    @pytest.mark.unit
    def test_scripts_path(self):
        assert isinstance(SCRIPTS, Path)
        assert "scripts" in str(SCRIPTS).lower()

    @pytest.mark.unit
    def test_ura_root_path(self):
        assert isinstance(URA_ROOT, Path)
        assert URA_ROOT.exists()


class TestAllExported:
    """Verifica que __all__ incluye todas las constantes."""

    @pytest.mark.unit
    def test_all_incluye_todas(self):
        from motor.core.agents.constants import __all__
        
        expected = {
            "MAX_CICLO_S",
            "MODELOS",
            "NERVIOSO",
            "RUFF",
            "SCRIPTS",
            "URA_ROOT",
        }
        assert set(__all__) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
