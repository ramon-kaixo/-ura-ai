"""Tests para motor/core/llm/circuit_breaker.py y _state de diagnostico/scanner."""
from __future__ import annotations

import pytest
from unittest import mock

import pytest

from motor.core.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from motor.diagnostico._state import DiagnosticoState, build_diagnostico_state
from motor.scanner._state import ScannerState, build_scanner_state


class TestCircuitBreakerCompat:
    @pytest.mark.unit
    def test_call_open_lanza(self) -> None:
        cb = CircuitBreaker("test-cb")
        with mock.patch.object(type(cb), "is_available", new_callable=mock.PropertyMock, return_value=False):
            with pytest.raises(CircuitBreakerOpenError):
                cb.call(lambda: 1)

    @pytest.mark.unit
    def test_call_disponible_delega(self) -> None:
        cb = CircuitBreaker("test-cb")
        with mock.patch.object(type(cb), "is_available", new_callable=mock.PropertyMock, return_value=True):
            called = []
            r = cb.call(lambda: called.append(1) or "ok")
        r = cb.call(lambda: called.append(1) or "ok")
        assert r == "ok"
        assert called == [1, 1]  # super().call invoca fn (success + verify)

    @pytest.mark.unit
    def test_exports(self) -> None:
        from motor.core.llm.circuit_breaker import CircuitState

        assert CircuitState is not None


class TestDiagnosticoState:
    @pytest.mark.unit
    def test_frozen(self) -> None:
        st = DiagnosticoState(executor=object(), config=object())
        with pytest.raises(Exception):
            st.executor = object()  # type: ignore[misc]

    @pytest.mark.unit
    def test_build(self, monkeypatch) -> None:
        config = object()
        executor = mock.Mock()
        monkeypatch.setattr("motor.core.executor.SubprocessExecutor", mock.Mock(return_value=executor))
        st = build_diagnostico_state(config)
        assert st.config is config
        assert st.executor is executor

    @pytest.mark.unit
    def test_build_sin_config(self, monkeypatch) -> None:
        config = object()
        monkeypatch.setattr("motor.core.config.UraConfig", mock.Mock(load=lambda: config))
        st = build_diagnostico_state()
        assert st.config is config


class TestScannerState:
    @pytest.mark.unit
    def test_frozen(self) -> None:
        st = ScannerState(executor=object(), config=object())
        with pytest.raises(Exception):
            st.executor = object()  # type: ignore[misc]

    @pytest.mark.unit
    def test_build(self, monkeypatch) -> None:
        config = object()
        executor = mock.Mock()
        monkeypatch.setattr("motor.core.executor.SubprocessExecutor", mock.Mock(return_value=executor))
        st = build_scanner_state(config)
        assert st.config is config
        assert st.executor is executor

    @pytest.mark.unit
    def test_build_sin_config(self, monkeypatch) -> None:
        config = object()
        monkeypatch.setattr("motor.core.config.UraConfig", mock.Mock(load=lambda: config))
        st = build_scanner_state()
        assert st.config is config
