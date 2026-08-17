"""Cobertura para core/logs/guardian_logger.py (TASK-20260818-009, A6)."""
from __future__ import annotations

import json
from unittest import mock

import pytest

import core.logs.guardian_logger as gl


@pytest.fixture(autouse=True)
def _log_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "GUARDIAN_LOG", str(tmp_path / "guardian.jsonl"))
    yield


def test_ensure_log_dir_crea_directorio(tmp_path, monkeypatch):
    destino = tmp_path / "sub" / "nested" / "guardian.jsonl"
    monkeypatch.setattr(gl, "GUARDIAN_LOG", str(destino))
    gl._ensure_log_dir()
    assert destino.parent.exists()


def test_ensure_log_dir_sin_directorio(monkeypatch):
    monkeypatch.setattr(gl, "GUARDIAN_LOG", "solo_archivo.json")
    gl._ensure_log_dir()  # no debe lanzar


def test_publish_evento(mock_publish):
    gl._publish_to_event_bus({"event": "e1", "reason": "r" * 250, "result_type": "failure"})
    args = mock_publish.call_args
    assert args[0][0] == "alert"
    assert args[0][1]["source"] == "guardian"
    assert len(args[0][1]["reason"]) == 200


def test_publish_fallo_ignorado(mock_publish):
    mock_publish.side_effect = RuntimeError("bus caido")
    gl._publish_to_event_bus({"event": "e1"})  # no debe lanzar


def test_save_qdrant_disponible_guarda_incidente():
    fake = mock.Mock()
    fake.disponible = True
    fake.guardar_incidente = mock.Mock()
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia", return_value=fake) as inst:
        gl._save_to_qdrant(
            {"event": "service_down", "reason": "causa", "attempts": 3, "complexity": 2,
             "timestamp": "2026-08-18T00:00:00Z"},
            config=mock.Mock(),
        )
    inst.assert_called_once()
    payload = fake.guardar_incidente.call_args[0][0]
    assert payload["subtipo"] == "ServiceDown"
    assert payload["resumen"].startswith("service_down:")
    assert payload["pre_state"] == {"attempts": 3, "complexity": 2}
    assert payload["exit_code"] == -1


def test_save_qdrant_no_disponible_no_guarda():
    fake = mock.Mock()
    fake.disponible = False
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia", return_value=fake) as inst:
        gl._save_to_qdrant({"event": "x"}, config=mock.Mock())
    inst.assert_called_once()
    fake.guardar_incidente.assert_not_called()


def test_save_qdrant_excepcion_ignorada(mock_publish):
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia", side_effect=RuntimeError("qdrant down")):
        gl._save_to_qdrant({"event": "x"}, config=mock.Mock())
    mock_publish.assert_called_once()


def test_log_event_escribe_archivo(tmp_path):
    gl.log_event("ok_event", model="m", file="f.py", reason="razon", attempts=1)
    lineas = (tmp_path / "guardian.jsonl").read_text().splitlines()
    assert len(lineas) == 1
    rec = json.loads(lineas[0])
    assert rec["event"] == "ok_event"
    assert rec["penalty"] == ""


def test_log_event_penalty_truncado(tmp_path):
    gl.log_event("p", penalty="x" * 200)
    rec = json.loads((tmp_path / "guardian.jsonl").read_text().splitlines()[0])
    assert len(rec["penalty"]) == 120


def test_log_event_error_escritura_loguea(tmp_path, monkeypatch):
    monkeypatch.setattr(gl, "GUARDIAN_LOG", str(tmp_path / "no-existe" / "g.jsonl"))
    gl.log_event("x")  # OSError capturado


def test_log_event_failure_publica_y_guarda(mock_publish):
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia", return_value=mock.Mock(disponible=True)) as inst:
        gl.log_event("fallo", result_type="failure", attempts=1)
    # El publish se emite 2 veces en el flujo failure: directo (log_event) y
    # al final de _save_to_qdrant (fix C2) — redundancia documentada.
    assert mock_publish.call_count == 2
    inst.assert_called_once()


def test_log_event_warning_solo_publica(mock_publish):
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia") as inst:
        gl.log_event("aviso", result_type="warning")
    mock_publish.assert_called_once()
    inst.assert_not_called()


def test_log_event_attempts_alto_publica_sin_failure(mock_publish):
    with mock.patch("motor.core.qdrant_client.QdrantClient.instancia") as inst:
        gl.log_event("e", attempts=3)
    mock_publish.assert_called_once()
    inst.assert_not_called()


@pytest.fixture
def mock_publish():
    with mock.patch("core.event_bus.publish") as mp:
        yield mp
