"""Tests de cobertura para motor/core/llm/_logging.py (gate 90%)."""

from __future__ import annotations

from motor.core.llm._logging import log_call, percentile


class TestPercentile:
    def test_vacio(self) -> None:
        assert percentile([], 90) == 0.0

    def test_p0(self) -> None:
        assert percentile([10, 20, 30], 0) == 10

    def test_p100(self) -> None:
        assert percentile([10, 20, 30], 100) == 30

    def test_p50(self) -> None:
        assert percentile([10, 20, 30], 50) == 20

    def test_p90_rounding(self) -> None:
        assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 10

    def test_p50_desordenado_ordena(self) -> None:
        assert percentile([30, 10, 20], 50) == 20

    def test_p_over_100(self) -> None:
        assert percentile([5, 6], 150) == 6

    def test_p_negativo(self) -> None:
        assert percentile([5, 6], -10) == 5


class TestLogCall:
    def test_sin_error_info(self, caplog) -> None:
        import logging

        with caplog.at_level(logging.INFO):
            log_call("ollama", "llama3", 12.5)
        assert any("llm_call" in r.message and "provider=ollama" in r.message for r in caplog.records)

    def test_con_error_warning(self, caplog) -> None:
        import logging

        with caplog.at_level(logging.WARNING):
            log_call("openai", "gpt4", 99.9, error="timeout", retries=3)
        assert any(
            r.levelno == logging.WARNING and "error=timeout" in r.message and "retries=3" in r.message
            for r in caplog.records
        )
