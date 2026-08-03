"""Tests para motor/scanner/diff_detector.py y motor/diagnostico/circuit_breaker.py."""
from __future__ import annotations

from unittest import mock

from motor.diagnostico.circuit_breaker import CircuitBreaker
from motor.scanner.diff_detector import _es_critico, compute_diff


class TestComputeDiff:
    def test_sin_cambios(self) -> None:
        snap = {"servicios": {"a": "active"}, "recursos": {"ram_pct": 50}}
        count, anomalias = compute_diff(snap, snap)
        assert count == 0
        assert anomalias == []

    def test_cambio_normal(self) -> None:
        prev = {"servicios": {"a": "active"}}
        actual = {"servicios": {"a": "active", "b": "active"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1  # b nuevo
        assert anomalias == []

    def test_servicio_caido_critico(self) -> None:
        prev = {"servicios": {"ollama": "active"}}
        actual = {"servicios": {"ollama": "inactive"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1
        assert len(anomalias) == 1
        assert "ollama" in anomalias[0]

    def test_ram_alta_critica(self) -> None:
        prev = {"recursos": {"ram_pct": 50}}
        actual = {"recursos": {"ram_pct": 95}}
        _count, anomalias = compute_diff(actual, prev)
        assert len(anomalias) == 1

    def test_zombies_critico(self) -> None:
        prev = {"recursos": {"zombies": 0}}
        actual = {"recursos": {"zombies": 2}}
        _count, anomalias = compute_diff(actual, prev)
        assert len(anomalias) == 1

    def test_hw_fail_critico(self) -> None:
        prev = {"hw_health": {"ok": True}}
        actual = {"hw_health": {"ok": False}}
        _count, anomalias = compute_diff(actual, prev)
        assert len(anomalias) == 1

    def test_key_no_en_actual(self) -> None:
        prev = {"solo_prev": {"a": 1}}
        actual = {"otra": {}}
        count, _anomalias = compute_diff(actual, prev)
        assert count == 0

    def test_valores_anidados_iguales(self) -> None:
        prev = {"servicios": {"a": "active", "x": {"deep": 1}}}
        actual = {"servicios": {"a": "active", "x": {"deep": 1}}}
        count, _anomalias = compute_diff(actual, prev)
        assert count == 0


class TestEsCritico:
    def test_servicio_caido(self) -> None:
        assert _es_critico("servicios", "ollama", "active", "inactive") is True
        assert _es_critico("servicios", "ollama", "active", "failed") is True
        assert _es_critico("servicios", "ollama", "active", "active") is False

    def test_recursos(self) -> None:
        assert _es_critico("recursos", "ram_pct", 50, 95) is True
        assert _es_critico("recursos", "ram_pct", 50, 80) is False
        assert _es_critico("recursos", "zombies", 0, 1) is True
        assert _es_critico("recursos", "cpu", 10, 50) is False

    def test_hw(self) -> None:
        assert _es_critico("hw_health", "ok", True, False) is True
        assert _es_critico("hw_health", "ok", False, True) is False


class TestCircuitBreaker:
    def test_ok_resetea_fallos(self) -> None:
        qdrant = mock.Mock()
        qdrant.health.return_value = True
        cb = CircuitBreaker(qdrant)
        cb._fallos = 2
        assert cb.operacional() is True
        assert cb._fallos == 0

    def test_fallos_acumulan(self) -> None:
        qdrant = mock.Mock()
        qdrant.health.return_value = False
        cb = CircuitBreaker(qdrant)
        assert cb.operacional() is False
        assert cb._fallos == 1
        assert cb._abierto is False

    def test_abre_tras_3_fallos(self) -> None:
        qdrant = mock.Mock()
        qdrant.health.return_value = False
        cb = CircuitBreaker(qdrant)
        for _ in range(3):
            cb.operacional()
        assert cb._abierto is True

    def test_abierto_no_consulta(self) -> None:
        qdrant = mock.Mock()
        qdrant.health.return_value = False
        cb = CircuitBreaker(qdrant)
        for _ in range(3):
            cb.operacional()
        qdrant.health.reset_mock()
        assert cb.operacional() is False
        qdrant.health.assert_not_called()

    def test_reset(self) -> None:
        qdrant = mock.Mock()
        cb = CircuitBreaker(qdrant)
        cb._abierto = True
        cb._fallos = 3
        cb.reset()
        assert cb._abierto is False
        assert cb._fallos == 0

    def test_constantes(self) -> None:
        assert CircuitBreaker.FALLOS_MAX == 3
        assert CircuitBreaker.VENTANA_SEG == 300
