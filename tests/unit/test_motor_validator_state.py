"""Tests para motor/platform/validator.py, motor/core/llm/circuit_breaker.py y _state de diagnostico/scanner."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from motor.diagnostico._state import DiagnosticoState, build_diagnostico_state
from motor.platform.validator import ProtocolValidator
from motor.scanner._state import ScannerState, build_scanner_state


class TestProtocolValidator:
    def test_payload_seguro(self) -> None:
        env = SimpleNamespace(payload=b"texto normal")
        ProtocolValidator().validate(env)  # no debe lanzar

    def test_payload_script(self) -> None:
        env = SimpleNamespace(payload=b'<script>alert(1)</script>')
        with pytest.raises(ValueError, match="unsafe_payload"):
            ProtocolValidator().validate(env)

    def test_payload_javascript(self) -> None:
        env = SimpleNamespace(payload=b"javascript:alert(1)")
        with pytest.raises(ValueError, match="javascript"):
            ProtocolValidator().validate(env)

    def test_payload_onerror(self) -> None:
        env = SimpleNamespace(payload=b'<img src=x onerror="alert(1)">')
        with pytest.raises(ValueError, match="onerror"):
            ProtocolValidator().validate(env)

    def test_payload_onload(self) -> None:
        env = SimpleNamespace(payload=b'<body onload="evil()">')
        with pytest.raises(ValueError, match="onload"):
            ProtocolValidator().validate(env)

    def test_payload_no_bytes_no_valida(self) -> None:
        """Payload str no valida (solo bytes) — documentado."""
        env = SimpleNamespace(payload="texto", checksum=b"<script>x")
        ProtocolValidator().validate(env)  # no lanza con str

    def test_mayusculas_detectadas(self) -> None:
        env = SimpleNamespace(payload=b"<SCRIPT>alert(1)</SCRIPT>")
        with pytest.raises(ValueError, match="script"):
            ProtocolValidator().validate(env)


class TestCircuitBreakerCompat:
    def test_call_open_lanza(self) -> None:
        cb = CircuitBreaker("test-cb")
        with mock.patch.object(type(cb), "is_available", new_callable=mock.PropertyMock, return_value=False):
            with pytest.raises(CircuitBreakerOpenError):
                cb.call(lambda: 1)

    def test_call_disponible_delega(self) -> None:
        cb = CircuitBreaker("test-cb")
        with mock.patch.object(type(cb), "is_available", new_callable=mock.PropertyMock, return_value=True):
            called = []
            r = cb.call(lambda: called.append(1) or "ok")
        r = cb.call(lambda: called.append(1) or "ok")
        assert r == "ok"
        assert called == [1]

    def test_exports(self) -> None:
        from motor.core.llm.circuit_breaker import CircuitState

        assert CircuitState is not None


class TestDiagnosticoState:
    def test_frozen(self) -> None:
        st = DiagnosticoState(executor=object(), config=object())
        with pytest.raises(Exception):
            st.executor = object()  # type: ignore[misc]

    def test_build(self, monkeypatch) -> None:
        config = object()
        executor = mock.Mock()
        monkeypatch.setattr("motor.core.executor.SubprocessExecutor", mock.Mock(return_value=executor))
        st = build_diagnostico_state(config)
        assert st.config is config
        assert st.executor is executor

    def test_build_sin_config(self, monkeypatch) -> None:
        config = object()
        monkeypatch.setattr("motor.core.config.UraConfig", mock.Mock(load=lambda: config))
        st = build_diagnostico_state()
        assert st.config is config


class TestScannerState:
    def test_frozen(self) -> None:
        st = ScannerState(executor=object(), config=object())
        with pytest.raises(Exception):
            st.executor = object()  # type: ignore[misc]

    def test_build(self, monkeypatch) -> None:
        config = object()
        executor = mock.Mock()
        monkeypatch.setattr("motor.core.executor.SubprocessExecutor", mock.Mock(return_value=executor))
        st = build_scanner_state(config)
        assert st.config is config
        assert st.executor is executor

    def test_build_sin_config(self, monkeypatch) -> None:
        config = object()
        monkeypatch.setattr("motor.core.config.UraConfig", mock.Mock(load=lambda: config))
        st = build_scanner_state()
        assert st.config is config
