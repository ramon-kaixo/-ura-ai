"""Tests for core/consensus_system.py — tripartite consensus protocol."""

import logging
from unittest.mock import MagicMock, patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def mock_init_files():
    """Prevent file I/O during ConsensusSystem init."""
    with (
        patch("pathlib.Path.mkdir"),
        patch("builtins.open", MagicMock()),
        patch("core.consensus_system.ConsensusSystem.init_consensus_log"),
    ):
        yield


class TestInstantiation:
    """ConsensusSystem instancia sin errores."""

    def test_imports_without_error(self):
        from core.consensus_system import ConsensusSystem

        assert ConsensusSystem is not None

    def test_instantiates_without_error(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            assert cs is not None


class TestEvaluateConsensus:
    """Evaluacion de consenso — minimo 2 de 3 para aprobar."""

    def test_majority_reaches_consensus(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            responses = {"gpt-4": "r1", "claude-3-opus": "r2", "gemini-pro": "r3"}
            reached, result = cs.evaluate_consensus(responses)
            assert reached is True
            assert len(result) > 0

    def test_two_out_of_three_is_consensus(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            responses = {"gpt-4": "r1", "claude-3-opus": "r2"}
            reached, result = cs.evaluate_consensus(responses)
            assert reached is True

    def test_single_response_no_consensus(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            responses = {"gpt-4": "r1"}
            reached, _result = cs.evaluate_consensus(responses)
            assert reached is False

    def test_empty_responses_no_consensus(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            reached, _result = cs.evaluate_consensus({})
            assert reached is False

    def test_zero_agents_no_exception(self):
        with (
            patch.object(open, "__call__", return_value=MagicMock()),
            patch("json.load", return_value={}),
        ):
            from core.consensus_system import ConsensusSystem

            cs = ConsensusSystem()
            reached, _result = cs.evaluate_consensus({})
            assert reached is False
