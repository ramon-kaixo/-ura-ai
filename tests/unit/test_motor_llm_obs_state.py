"""Tests para motor/core/llm/observability.py, detector.py y _state.py."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.core.llm._state import LLMState, _get_optional_providers
from motor.core.llm.detector import HotspotDetector, HotspotRecord
from motor.core.llm.observability import LLMMetrics, metrics


class TestLLMMetrics:
    def test_record_success(self) -> None:
        m = LLMMetrics()
        m.record("ollama", "generate", 10.0, success=True, tokens=100)
        stats = m.get_stats("ollama", "generate")
        key = "ollama.generate"
        assert stats[key]["llamadas_totales"] == 1
        assert stats[key]["tokens_medios_por_call"] == 100.0
        assert stats[key]["errores"] == {}

    def test_record_error_con_detalle(self) -> None:
        m = LLMMetrics()
        m.record("ollama", "generate", 5.0, success=False, error="timeout")
        stats = m.get_stats("ollama", "generate")
        assert stats["ollama.generate"]["errores"] == {"timeout": 1}

    def test_sin_datos(self) -> None:
        m = LLMMetrics()
        assert m.get_stats() == {"error": "no data"}

    def test_filtro_provider(self) -> None:
        m = LLMMetrics()
        m.record("a", "generate", 1.0, success=True)
        m.record("b", "generate", 1.0, success=True)
        stats = m.get_stats(provider="a")
        assert "a.generate" in stats
        assert "b.generate" not in stats

    def test_filtro_operation(self) -> None:
        m = LLMMetrics()
        m.record("a", "generate", 1.0, success=True)
        m.record("a", "embed", 1.0, success=True)
        stats = m.get_stats(operation="embed")
        assert "a.embed" in stats
        assert "a.generate" not in stats

    def test_summary(self) -> None:
        m = LLMMetrics()
        m.record("a", "generate", 1.0, success=True)
        m.record("a", "generate", 1.0, success=False, error="e")
        m.record("b", "embed", 1.0, success=True)
        s = m.summary()
        assert s["a"] == {"total": 2, "ok": 1, "fail": 1}
        assert s["b"] == {"total": 1, "ok": 1, "fail": 0}

    def test_max_records_limita(self) -> None:
        from motor.core.llm.observability import MAX_RECORDS

        m = LLMMetrics()
        for i in range(MAX_RECORDS + 50):
            m.record("a", "g", float(i), success=True)
        stats = m.get_stats("a", "g")
        assert stats["a.g"]["llamadas_totales"] <= MAX_RECORDS

    def test_reset(self) -> None:
        m = LLMMetrics()
        m.record("a", "g", 1.0, success=True)
        m.reset()
        assert m.get_stats() == {"error": "no data"}

    def test_singleton(self) -> None:
        assert isinstance(metrics, LLMMetrics)


class TestHotspotRecord:
    def test_to_dict(self) -> None:
        r = HotspotRecord("provider", "op", 100.0, 10.0, peak_memory_bytes=2048, allocations_count=3)
        d = r.to_dict()
        assert d["provider"] == "provider"
        assert d["operation"] == "op"
        assert d["wall_time_ms"] == 100.0
        assert d["cpu_time_ms"] == 10.0
        assert d["peak_memory_kb"] == 2.0
        assert d["allocations"] == 3

    def test_repr(self) -> None:
        r = HotspotRecord("p", "o", 10.0, 1.0)
        assert "p" in repr(r)


class TestHotspotDetector:
    def test_threshold_property(self) -> None:
        d = HotspotDetector(threshold_ms=500.0)
        assert d.threshold_ms == 500.0
        d.threshold_ms = 200.0
        assert d.threshold_ms == 200.0

    def test_evaluate_deteccion(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        record = d.evaluate("ollama", "generate", 500.0, cpu_time_ms=50.0)
        assert record is not None
        assert record.provider == "ollama"
        assert record.wall_time_ms == 500.0

    def test_evaluate_normal(self) -> None:
        d = HotspotDetector(threshold_ms=1000.0)
        record = d.evaluate("ollama", "generate", 50.0)
        assert record is None

    def test_get_hotspots(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        d.evaluate("a", "g", 500.0)
        d.evaluate("b", "g", 10.0)
        hotspots = d.get_hotspots()
        assert len(hotspots) == 1
        assert hotspots[0]["provider"] == "a"

    def test_evaluate_from_profile(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        profile = mock.Mock()
        profile.wall_time_ms = 500.0
        profile.operation = "generate"
        record = d.evaluate_from_profile(profile)
        assert record is not None

    def test_get_stats_y_reset(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        d.evaluate("a", "g", 500.0)
        stats = d.get_stats()
        assert stats is not None
        d.reset()
        assert d.get_hotspots() == []


class TestLLMState:
    def test_frozen(self) -> None:
        st = LLMState(registry=object(), default_provider=object(), generate=lambda: None, embed=lambda: None, embed_async=lambda: None, health=lambda: None)
        with pytest.raises(Exception):
            st.registry = object()  # type: ignore[misc]

    def test_optional_providers_disponibles(self) -> None:
        provs = _get_optional_providers()
        [n for _, n in provs]
        # ollama no esta en opcionales; los demas segun instalados
        assert isinstance(provs, list)

    def test_build_llm_state_default(self, monkeypatch) -> None:
        config = mock.Mock()
        config.llm_provider = "ollama"
        reg = mock.Mock()
        monkeypatch.setattr("motor.core.llm.registry.registry", reg)
        provider = mock.Mock()
        monkeypatch.setattr("motor.core.llm.ollama.OllamaProvider", mock.Mock(return_value=provider))
        from motor.core.llm._state import build_llm_state

        st = build_llm_state(config)
        assert isinstance(st, LLMState)
