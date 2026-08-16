"""Tests de cobertura P2 para knowledge/engine/audit/ — service, backend, ndjson.

Cubre las sentencias restantes de audit/service.py (log_* con backend None,
setter, ingest/close por tipo, get_audit doble-check y degradado), backend.py
(record_metric con métricas no disponibles) y ndjson_backend.py (flock
bloqueado, health error por OSError, líneas vacías/corruptas en lectura e
ingesta, ingest sin archivo, fallo SQLite y métricas no disponibles).
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import threading
import types
from pathlib import Path
from unittest import mock

from knowledge.engine.audit import service as audit_service
from knowledge.engine.audit.backend import record_metric
from knowledge.engine.audit.ndjson_backend import NDJSONAuditBackend


class FakeEvent:
    """Evento mínimo para ejercitar los backends (mismo shape que AuditEvent)."""

    def __init__(self, action: str = "read") -> None:
        self.action = action
        self.actor = "user"
        self.entity_type = "doc"
        self.entity_id = "d1"
        self.result = "ok"
        self.correlation_id = "cid"
        self.timestamp = "2026-01-01"
        self.metadata = {"k": "v"}


class TestAuditServiceFacade:
    def test_logs_sin_backend_son_noop(self) -> None:
        """Las 4 fachadas con backend None no hacen nada (líneas 50-52, 71-73, 93-95, 118-120)."""
        s = audit_service.AuditService()
        s.log_read(query="q", docs=1)
        s.log_compile()
        s.log_archive()
        s.log("a", "b", "c", "d")

    def test_logs_con_backend_escriben(self, tmp_path) -> None:
        """Las 4 fachadas con backend real escriben un evento (write cubierto)."""
        backend = NDJSONAuditBackend(tmp_path / "audit")
        s = audit_service.AuditService(backend=backend)
        s.log_read(query="q", docs=1, extra="x")
        s.log_compile(result="fail")
        s.log_archive(kind="source", result="ok")
        s.log("custom", "actor", "type", "id", result="ok", extra=1)
        s.close()
        lines = (tmp_path / "audit" / "audit.ndjson").read_text().strip().splitlines()
        assert len(lines) == 4
        actions = [json.loads(l)["action"] for l in lines]
        assert actions == ["search", "compile", "archive", "custom"]

    def test_backend_setter(self) -> None:
        """Setter del backend (línea 41)."""
        s = audit_service.AuditService()
        backend = mock.Mock()
        s.backend = backend
        assert s.backend is backend

    def test_ingest_no_ndjson_returns_zero(self) -> None:
        """ingest() con backend que no es NDJSON → 0 (líneas 139-140)."""
        s = audit_service.AuditService(backend=mock.Mock())
        assert s.ingest(Path("/tmp/x.sqlite")) == 0

    def test_close_no_ndjson_noop(self) -> None:
        """close() con backend no-NDJSON no llama al backend (líneas 143-145)."""
        backend = mock.Mock()
        s = audit_service.AuditService(backend=backend)
        s.close()
        backend.close.assert_not_called()

    def test_close_ndjson_cierra_backend(self, tmp_path) -> None:
        """close() con backend NDJSON delega en el backend (líneas 144-145)."""
        backend = NDJSONAuditBackend(tmp_path / "audit")
        s = audit_service.AuditService(backend=backend)
        s.close()
        assert backend._handle.closed

    def test_ingest_ndjson_delega(self, tmp_path, monkeypatch) -> None:
        """ingest() con backend NDJSON delega en ingest_into_sqlite (línea 141)."""
        backend = NDJSONAuditBackend(tmp_path / "audit")
        backend.write(FakeEvent(action="a"))
        backend.close()
        conn = mock.Mock()
        conn.commit.return_value = None
        conn.close.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        s = audit_service.AuditService(backend=backend)
        assert s.ingest(tmp_path / "db.sqlite") == 1


class TestGetAuditSingleton:
    def setup_method(self) -> None:
        self._orig = audit_service._AUDIT_INSTANCE
        audit_service._AUDIT_INSTANCE = None

    def teardown_method(self) -> None:
        audit_service._AUDIT_INSTANCE = self._orig

    def test_doble_check_concurrencia(self) -> None:
        """Segundo check dentro del lock con otro thread esperando (líneas 164-165)."""
        dummy = audit_service.AuditService()
        audit_service._AUDIT_LOCK.acquire()
        results: list = []
        entered = threading.Event()
        finished = threading.Event()

        def worker() -> None:
            entered.set()
            results.append(audit_service.get_audit())
            finished.set()

        t = threading.Thread(target=worker)
        t.start()
        assert entered.wait(5)
        audit_service._AUDIT_INSTANCE = dummy
        audit_service._AUDIT_LOCK.release()
        assert finished.wait(5)
        t.join(timeout=5)
        assert results == [dummy]

    def test_creacion_exitosa(self) -> None:
        """get_audit() crea la instancia con backend (línea 169)."""
        with mock.patch.object(audit_service, "NDJSONAuditBackend", return_value=mock.Mock()):
            s = audit_service.get_audit()
        assert s.backend is not None

    def test_degradado_sin_backend(self) -> None:
        """Fallo al crear el backend → AuditService no-op con warning (líneas 170-172)."""
        with (
            mock.patch.object(audit_service, "NDJSONAuditBackend", side_effect=OSError("ro")),
            mock.patch.object(audit_service.log, "warning") as warn,
        ):
            s = audit_service.get_audit()
        assert s.backend is None
        warn.assert_called_once()

    def test_set_audit_y_early_return(self) -> None:
        """set_audit + get_audit con instancia ya creada (líneas 161-162, 179)."""
        s = audit_service.AuditService()
        audit_service.set_audit(s)
        assert audit_service.get_audit() is s


class TestRecordMetricSinMetrics:
    def test_record_metric_import_fail(self) -> None:
        """record_metric sin knowledge.engine.metrics disponible → noop (líneas 50-51)."""
        fake = types.ModuleType("knowledge.engine.metrics")
        with mock.patch.dict(sys.modules, {"knowledge.engine.metrics": fake}):
            record_metric()

    def test_record_metric_ok(self) -> None:
        """record_metric con métricas disponibles incrementa el contador (línea 50)."""
        fake = types.ModuleType("knowledge.engine.metrics")
        inc = mock.Mock()
        fake.audit_write_failures = mock.Mock()
        fake.audit_write_failures.inc = inc
        with mock.patch.dict(sys.modules, {"knowledge.engine.metrics": fake}):
            record_metric()
        inc.assert_called_once()


class TestNDJSONCobertura:
    def test_acquire_flock_bloqueado(self, tmp_path) -> None:
        """flock no disponible (otro fd retiene LOCK_EX) → False (líneas 70-75)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        fd = os.open(str(b._lock_file), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            assert b._acquire_flock() is False
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        b.close()

    def test_health_check_oserror(self, tmp_path, monkeypatch) -> None:
        """health_check con OSError → AuditHealth no healthy (líneas 138-139)."""

        def boom(*args, **kwargs):
            raise OSError("x")

        b = NDJSONAuditBackend(tmp_path / "audit")
        monkeypatch.setattr("knowledge.engine.audit.ndjson_backend.os.access", boom)
        h = b.health_check()
        assert h.healthy is False
        b.close()

    def test_read_lines_linea_vacia(self, tmp_path) -> None:
        """read_lines con línea vacía → saltada (línea 191)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        with (tmp_path / "audit" / "audit.ndjson").open("a") as f:
            f.write("\n")
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        assert len(b2.read_lines()) == 1
        b2.close()

    def test_read_lines_linea_corrupta(self, tmp_path) -> None:
        """read_lines con línea no-JSON → saltada con warning (líneas 195-197)."""
        (tmp_path / "audit").mkdir(parents=True)
        (tmp_path / "audit" / "audit.ndjson").write_text("not json\n")
        b = NDJSONAuditBackend(tmp_path / "audit")
        assert b.read_lines() == []
        b.close()

    def test_rotacion_error_oserror(self, tmp_path) -> None:
        """Fallo en rename durante la rotación → reabre y resetea (líneas 167-172)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.MAX_BYTES = 10
        b._bytes_written = 50
        b._handle.write("x" * 50)
        b._handle.flush()
        with mock.patch.object(Path, "rename", side_effect=OSError("ro")):
            b._maybe_rotate()
        assert b._bytes_written == 0
        assert b._handle.writable()
        b.close()

    def test_ingest_linea_vacia(self, tmp_path, monkeypatch) -> None:
        """_ingest_events con línea vacía → continue (línea 209)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        with (tmp_path / "audit" / "audit.ndjson").open("a") as f:
            f.write("\n")
        conn = mock.Mock()
        conn.commit.return_value = None
        conn.close.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        assert b2.ingest_into_sqlite(tmp_path / "db.sqlite") == 1
        b2.close()

    def test_ingest_sin_archivo(self, tmp_path) -> None:
        """ingest sin archivo NDJSON → FileNotFoundError → 0 (líneas 247-248)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.close()
        (tmp_path / "audit" / "audit.ndjson").unlink()
        assert b.ingest_into_sqlite(tmp_path / "db.sqlite") == 0
        b.close()

    def test_ingest_db_fallo(self, tmp_path, monkeypatch) -> None:
        """Fallo al abrir SQLite → warning y retorno parcial (líneas 267-269)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(side_effect=OSError("no db")))
        b2 = NDJSONAuditBackend(tmp_path / "audit")
        assert b2.ingest_into_sqlite(tmp_path / "db.sqlite") == 0
        b2.close()

    def test_ingest_metrics_no_disponibles(self, tmp_path, monkeypatch) -> None:
        """Ingesta completa pero métricas no disponibles → noop (líneas 276-277)."""
        b = NDJSONAuditBackend(tmp_path / "audit")
        b.write(FakeEvent(action="a"))
        b.close()
        conn = mock.Mock()
        conn.commit.return_value = None
        conn.close.return_value = None
        monkeypatch.setattr("knowledge.engine.connection.open_db", mock.Mock(return_value=conn))
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", mock.Mock())
        fake = types.ModuleType("knowledge.engine.metrics")
        with mock.patch.dict(sys.modules, {"knowledge.engine.metrics": fake}):
            b2 = NDJSONAuditBackend(tmp_path / "audit")
            assert b2.ingest_into_sqlite(tmp_path / "db.sqlite") == 1
        b2.close()
