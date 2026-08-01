"""Tests for core/agents/constants.py."""

from core.agents.constants import MAX_CICLO_S, MODELOS, RUFF, URA_ROOT


class TestConstants:
    def test_max_ciclo_positive(self):
        assert isinstance(MAX_CICLO_S, int)
        assert MAX_CICLO_S > 0

    def test_modelos_not_empty(self):
        assert isinstance(MODELOS, dict)
        assert len(MODELOS) > 0
        for k, v in MODELOS.items():
            assert isinstance(k, str)
            assert isinstance(v, str)
            assert v.strip()

    def test_ruff_is_path(self):
        assert isinstance(RUFF, str)
        assert RUFF.endswith("ruff")

    def test_ura_root_exists(self):
        assert URA_ROOT.exists()
        assert URA_ROOT.is_dir()
