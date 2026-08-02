"""Tests for core/mochila/circuit_breaker.py."""

from unittest.mock import patch

import pytest

from core.mochila.circuit_breaker import CircuitBreaker, CircuitState


@pytest.fixture
def cb(tmp_path):
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60.0,
        half_open_max_requests=2,
        health_file=tmp_path / "health.json",
    )


class TestInit:
    def test_valores_por_defecto(self, tmp_path):
        breaker = CircuitBreaker(health_file=tmp_path / "h.json")
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 30.0
        assert breaker.half_open_max_requests == 2

    def test_carga_estado_persistido(self, tmp_path):
        hfile = tmp_path / "health.json"
        hfile.write_text('{"ollama": {"state": "open", "failure_count": 4, "consecutive_failures": 4}}')
        breaker = CircuitBreaker(health_file=hfile)
        h = breaker._health["ollama"]
        assert h.state == CircuitState.OPEN
        assert h.failure_count == 4

    def test_ignora_estado_invalido(self, tmp_path):
        hfile = tmp_path / "health.json"
        hfile.write_text('{"ollama": {"state": "unknown"}}')
        breaker = CircuitBreaker(health_file=hfile)
        assert "ollama" not in breaker._health

    def test_json_roto_no_rompe(self, tmp_path):
        hfile = tmp_path / "health.json"
        hfile.write_text("{roto")
        breaker = CircuitBreaker(health_file=hfile)
        assert breaker._health == {}


class TestPuedePasar:
    def test_closed_siempre_pasa(self, cb):
        assert cb.puede_pasar("ollama") is True

    def test_open_bloquea(self, cb):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.OPEN
        cb._health["ollama"].last_failure_time = 1000.0
        with patch("core.mochila.circuit_breaker.time.time", return_value=1020.0):
            # recovery_timeout=60 → aún no recuperado (1020-1000=20)
            assert cb.puede_pasar("ollama") is False

    def test_open_recupera_a_half_open(self, cb, tmp_path):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.OPEN
        cb._health["ollama"].last_failure_time = 1000.0
        with patch("core.mochila.circuit_breaker.time.time", return_value=1100.0):
            assert cb.puede_pasar("ollama") is True
        assert cb._health["ollama"].state == CircuitState.HALF_OPEN

    def test_half_open_limita_requests(self, cb):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.HALF_OPEN
        cb._health["ollama"].success_count = 1
        cb._health["ollama"].failure_count = 1
        assert cb.puede_pasar("ollama") is False

    def test_half_open_con_cupo(self, cb):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.HALF_OPEN
        assert cb.puede_pasar("ollama") is True


class TestRegistrarExito:
    def test_incrementa_y_reset_consecutivos(self, cb):
        cb.registrar_exito("ollama")
        h = cb._health["ollama"]
        assert h.success_count == 1
        assert h.consecutive_failures == 0

    def test_half_open_exito_cierra(self, cb):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.HALF_OPEN
        cb._health["ollama"].failure_count = 2
        cb.registrar_exito("ollama")
        h = cb._health["ollama"]
        assert h.state == CircuitState.CLOSED
        assert h.failure_count == 0


class TestRegistrarFallo:
    def test_incrementa_fallos(self, cb):
        cb.registrar_fallo("ollama")
        h = cb._health["ollama"]
        assert h.failure_count == 1
        assert h.consecutive_failures == 1

    def test_abre_tras_umbral(self, cb):
        for _ in range(3):
            cb.registrar_fallo("ollama")
        assert cb._health["ollama"].state == CircuitState.OPEN

    def test_no_abre_bajo_umbral(self, cb):
        cb.registrar_fallo("ollama")
        cb.registrar_fallo("ollama")
        assert cb._health["ollama"].state == CircuitState.CLOSED

    def test_half_open_fallo_reabre(self, cb):
        cb.puede_pasar("ollama")
        cb._health["ollama"].state = CircuitState.HALF_OPEN
        cb.registrar_fallo("ollama")
        assert cb._health["ollama"].state == CircuitState.OPEN

    def test_exitos_rompen_racha(self, cb):
        cb.registrar_fallo("ollama")
        cb.registrar_fallo("ollama")
        cb.registrar_exito("ollama")
        cb.registrar_fallo("ollama")
        assert cb._health["ollama"].state == CircuitState.CLOSED


class TestEstadoYReset:
    def test_estructura_estado(self, cb):
        st = cb.estado("ollama")
        assert set(st) == {
            "state",
            "failure_count",
            "success_count",
            "consecutive_failures",
            "last_failure_time",
            "last_success_time",
        }
        assert st["state"] == "closed"

    def test_reset_elimina(self, cb):
        cb.registrar_fallo("ollama")
        cb.reset("ollama")
        assert "ollama" not in cb._health

    def test_persistencia_tras_registro(self, cb, tmp_path):
        cb.registrar_fallo("ollama")
        saved = (tmp_path / "health.json").read_text()
        assert '"ollama"' in saved

    def test_persistencia_atomica(self, cb, tmp_path):
        cb.registrar_exito("ollama")
        assert not (tmp_path / "health.tmp").exists()
        assert (tmp_path / "health.json").exists()
