"""Tests para knowledge/engine/audit/ — NDJSON y SQLite backends."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest import mock

from knowledge.engine.audit.ndjson_backend import NDJSONAuditBackend
from knowledge.engine.audit.sqlite_backend import SQLiteAuditBackend


class FakeEvent:
    def __init__(self, action="read", actor="user", entity_type="doc", entity_id="d1", result="ok", correlation_id="cid", timestamp="2026-01-01", metadata=None):
        self.action = action
        self.actor = actor
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.result = result
        self.correlation_id = correlation_id
        self.timestamp = timestamp
        self.metadata = metadata or {"k": "v"}


class TestNDJSONAuditBackend:
    def test_init_crea_dir(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        assert (tmp_path / "audit" / "audit.ndjson").exists()
        b.close()

    def test_write_y_leer(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent())
        b.close()
        lines = (tmp_path / "audit" / "audit.ndjson").read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["action"] == "read"
        assert data["correlation_id"] == "cid"

    def test_close_idempotente_no_rompe_escritura_anterior(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="status"))
        b.close()
        b.close()  # atexit registra close: debe ser idempotente (supress OSError)
        data = json.loads((tmp_path / "audit" / "audit.ndjson").read_text())
        assert data["action"] == "status"

    def test_write_sin_lock_fallback(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        monkeypatch.setattr(b, "_acquire_flock", mock.Mock(return_value=False))
        b.write(FakeEvent(action="write"))
        assert b._events_written == 1
        b.close()

    def test_write_oserror(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        monkeypatch.setattr(b, "_acquire_flock", mock.Mock(return_value=True))
        monkeypatch.setattr(b, "_release_flock", mock.Mock())
        monkeypatch.setattr(b._handle, "write", mock.Mock(side_effect=OSError("disk full")))
        b.write(FakeEvent())
        assert b._last_error == "disk full"
        b.close()

    def test_flush_noop(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.flush()  # no-op
        b.close()

    def test_health_ok(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        h = b.health_check()
        assert h.healthy is True
        b.close()

    def test_health_error(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        monkeypatch.setattr("knowledge.engine.audit.ndjson_backend.os.access", mock.Mock(return_value=False))
        h = b.health_check()
        assert h.healthy is False
        b.close()

    def test_read_lines(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.write(FakeEvent(action="b"))
        b.close()
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        events = b2.read_lines()
        assert len(events) == 2
        assert events[0].action == "a"
        b2.close()

    def test_close(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent())
        b.close()
        assert b._handle.closed


class TestSQLiteAuditBackend:
    def test_init(self, tmp_path) -> None:
        b = SQLiteAuditBackend(tmp_path / "db.sqlite")
        assert b._events_written == 0

    def test_write_ok(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "db.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE op_audit (action TEXT, actor TEXT, entity_type TEXT, entity_id TEXT, result TEXT, correlation_id TEXT, timestamp TEXT, metadata TEXT)")
        conn.close()

        real_conn = mock.Mock()
        real_conn.execute.return_value = None
        real_conn.commit.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=real_conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        b = SQLiteAuditBackend(db)
        b.write(FakeEvent())
        assert b._events_written == 1
        real_conn.execute.assert_called_once()
        real_conn.commit.assert_called_once()

    def test_write_error(self, tmp_path, monkeypatch) -> None:
        b = SQLiteAuditBackend(tmp_path / "db.sqlite")
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(side_effect=OSError("no db")))
        b.write(FakeEvent())
        assert b._last_error == "no db"
        assert b._events_written == 0

    def test_flush_noop(self, tmp_path) -> None:
        b = SQLiteAuditBackend(tmp_path / "x.sqlite")
        b.flush()

    def test_health(self, tmp_path) -> None:
        b = SQLiteAuditBackend(tmp_path / "x.sqlite")
        b._events_written = 5
        h = b.health_check()
        assert h.healthy is True
        assert h.events_written == 5


class TestNDJSONRotacion:
    def test_no_rota_si_pequeno(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b._bytes_written = 100
        b.MAX_BYTES = 1000
        b._maybe_rotate()
        assert b._bytes_written == 100
        b.close()

    def test_rota_al_superar(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.MAX_BYTES = 10
        b._bytes_written = 50
        b._handle.write("x" * 50)  # archivo real grande
        b._handle.flush()
        b._maybe_rotate()
        # archivo original recreado + segmento .1
        assert b._file.exists()
        assert b._file.with_suffix(".ndjson.1").exists()
        assert b._bytes_written == 0
        b.close()

    def test_rota_con_segmentos(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.MAX_BYTES = 10
        b._bytes_written = 50
        b._handle.write("x" * 50)
        b._handle.flush()
        # crear segmentos previos
        b._file.with_suffix(".ndjson.1").write_text("x")
        b._file.with_suffix(".ndjson.2").write_text("y")
        b._maybe_rotate()
        assert b._file.with_suffix(".ndjson.1").exists()  # rotado
        b.close()

    def test_rotacion_error(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.MAX_BYTES = 10
        b._bytes_written = 50
        with mock.patch.object(Path, "rename", side_effect=OSError("ro")):
            b._maybe_rotate()
        assert b._bytes_written == 0  # reabierto
        b.close()


class TestNDJSONIngest:
    def test_ingest_vacio(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        assert b.ingest_into_sqlite(tmp_path / "db.sqlite") == 0
        b.close()

    def test_ingest_ok(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="read"))
        b.write(FakeEvent(action="write"))
        b.close()

        conn = mock.Mock()
        conn.execute.return_value = None
        conn.commit.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        n = b2.ingest_into_sqlite(tmp_path / "db.sqlite")
        assert n == 2
        assert conn.commit.call_count >= 1
        b2.close()

    def test_ingest_linea_corrupta(self, tmp_path, monkeypatch) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        # corromper una linea
        with (tmp_path / "audit" / "audit.ndjson").open("a") as f:
            f.write("no es json\n")
        conn = mock.Mock()
        conn.execute.return_value = None
        conn.commit.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        n = b2.ingest_into_sqlite(tmp_path / "db.sqlite")
        assert n == 1  # solo la valida
        b2.close()

    def test_read_segment(self, tmp_path) -> None:
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        # segmento .1 con otro evento
        seg = tmp_path / "audit" / "audit.ndjson.1"
        seg.write_text(json.dumps({"action": "old", "actor": "u", "entity_type": "d", "entity_id": "x", "result": "ok", "correlation_id": "c", "timestamp": "t", "metadata": {}}) + "\n")
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        seg_events = b2.read_lines(segment=1)
        assert len(seg_events) == 1
        assert seg_events[0].action == "old"
        assert b2.read_lines(segment=5) == []  # segmento inexistente
        b2.close()
