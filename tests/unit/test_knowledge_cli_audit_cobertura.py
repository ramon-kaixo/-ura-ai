"""Cobertura 100x100 de knowledge/engine/cli/audit.py (TASK-20260815-003).

Cubre las ramas de error/fail de las funciones _audit_* que el test
existente (test_knowledge_cli_audit.py) no alcanza.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.cli.audit import (
    _audit_active_version,
    _audit_backend,
    _audit_disk,
    _audit_integrity,
    _audit_orphans,
    _audit_pending_sync,
    _audit_stuck_jobs,
    _audit_wal,
    cmd_audit_db,
    cmd_vacuum,
)


class FakeRow:
    def __init__(self, val: Any) -> None:
        self._val = val

    def __getitem__(self, key: str) -> Any:
        return self._val


class FakeConn:
    def __init__(self, results: dict[str, Any]) -> None:
        self._results = results
        self.executed: list[str] = []
        self.closed = False

    def execute(self, sql: str) -> "FakeConn":
        self.executed.append(sql)
        self._current = self._results.get(sql, None)
        return self

    def fetchone(self) -> Any:
        return self._current

    def close(self) -> None:
        self.closed = True


def _report(estado: dict) -> Any:
    def report(status: str, check: str, msg: str) -> None:
        estado.append((status, check, msg))

    return report


class TestAuditIntegrity:
    def test_fail(self) -> None:
        conn = FakeConn({"PRAGMA integrity_check": FakeRow("corrupt")})
        r: list[tuple] = []
        _audit_integrity(conn, _report(r))
        assert r[0][0] == "FAIL"
        assert "corrupt" in r[0][2]


class TestAuditOrphans:
    def test_ambos_orphans(self) -> None:
        conn = FakeConn(
            {
                "SELECT COUNT(*) as c FROM kg_edges e LEFT JOIN kg_nodes n ON e.src = n.id WHERE n.id IS NULL": FakeRow(
                    3
                ),
                "SELECT COUNT(*) as c FROM kg_edges e LEFT JOIN kg_nodes n ON e.dst = n.id WHERE n.id IS NULL": FakeRow(
                    2
                ),
            }
        )
        r: list[tuple] = []
        _audit_orphans(conn, _report(r))
        assert r[0][0] == "FAIL"
        assert r[1][0] == "FAIL"


class TestAuditActiveVersion:
    def test_cero(self) -> None:
        conn = FakeConn({"SELECT COUNT(*) as c FROM kg_active_version": FakeRow(0)})
        r: list[tuple] = []
        _audit_active_version(conn, _report(r))
        assert r[0][0] == "WARN"

    def test_multiples(self) -> None:
        conn = FakeConn({"SELECT COUNT(*) as c FROM kg_active_version": FakeRow(3)})
        r: list[tuple] = []
        _audit_active_version(conn, _report(r))
        assert r[0][0] == "FAIL"


class TestAuditStuckJobs:
    def test_stuck(self) -> None:
        conn = FakeConn(
            {"SELECT COUNT(*) as c FROM op_jobs WHERE status = 'running' AND started_at < datetime('now', '-30 minutes')": FakeRow(5)}
        )
        r: list[tuple] = []
        _audit_stuck_jobs(conn, _report(r))
        assert r[0][0] == "FAIL"


class TestAuditWal:
    def test_no_wal(self, tmp_path: Path) -> None:
        conn = FakeConn({"PRAGMA journal_mode": FakeRow("delete")})
        db = tmp_path / "db.sqlite"
        r: list[tuple] = []
        _audit_wal(conn, db, _report(r))
        assert r[0][0] == "FAIL"

    def test_wal_grande(self, tmp_path: Path) -> None:
        conn = FakeConn({"PRAGMA journal_mode": FakeRow("wal")})
        db = tmp_path / "db.sqlite"
        (tmp_path / "db.sqlite-wal").write_bytes(b"x" * (200 * 1024 * 1024))
        r: list[tuple] = []
        _audit_wal(conn, db, _report(r))
        assert r[1][0] == "WARN"

    def test_wal_pequeno(self, tmp_path: Path) -> None:
        conn = FakeConn({"PRAGMA journal_mode": FakeRow("wal")})
        db = tmp_path / "db.sqlite"
        (tmp_path / "db.sqlite-wal").write_bytes(b"x" * 1024)
        r: list[tuple] = []
        _audit_wal(conn, db, _report(r))
        assert r[0][0] == "OK"


class TestAuditPendingSync:
    def test_pendientes(self) -> None:
        conn = FakeConn(
            {"SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending', 'failed')": FakeRow(4)}
        )
        r: list[tuple] = []
        _audit_pending_sync(conn, _report(r))
        assert r[0][0] == "WARN"


class TestAuditBackend:
    def test_sin_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(backend=None),
        )
        r: list[tuple] = []
        _audit_backend(_report(r))
        assert r[0][0] == "WARN"

    def test_backend_unhealthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(
                backend=SimpleNamespace(
                    health_check=lambda: SimpleNamespace(healthy=False, error="boom")
                )
            ),
        )
        r: list[tuple] = []
        _audit_backend(_report(r))
        assert r[0][0] == "FAIL"

    def test_backend_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        r: list[tuple] = []
        _audit_backend(_report(r))
        assert r[0][0] == "WARN"


class TestAuditDisk:
    def test_poco_espacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "shutil.disk_usage",
            lambda p: SimpleNamespace(free=0.5 * 1024**3),
        )
        r: list[tuple] = []
        _audit_disk(SimpleNamespace(parent="."), _report(r))
        assert r[0][0] == "FAIL"

    def test_medio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "shutil.disk_usage",
            lambda p: SimpleNamespace(free=3 * 1024**3),
        )
        r: list[tuple] = []
        _audit_disk(SimpleNamespace(parent="."), _report(r))
        assert r[0][0] == "WARN"

    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "shutil.disk_usage",
            lambda p: SimpleNamespace(free=50 * 1024**3),
        )
        r: list[tuple] = []
        _audit_disk(SimpleNamespace(parent="."), _report(r))
        assert r[0][0] == "OK"


class TestCmdAuditDb:
    def test_db_no_existe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.cli.audit._resolve_db_path",
            lambda args: SimpleNamespace(exists=lambda: False),
        )
        assert cmd_audit_db(SimpleNamespace()) == 1

    def test_audit_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({})
        monkeypatch.setattr(
            "knowledge.engine.cli.audit._resolve_db_path",
            lambda args: SimpleNamespace(exists=lambda: True),
        )
        monkeypatch.setattr("knowledge.engine.cli.audit.open_db", lambda p: conn)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_integrity", lambda c, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_orphans", lambda c, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_active_version", lambda c, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_stuck_jobs", lambda c, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_wal", lambda c, p, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_pending_sync", lambda c, r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_backend", lambda r: None)
        monkeypatch.setattr("knowledge.engine.cli.audit._audit_disk", lambda p, r: None)
        assert cmd_audit_db(SimpleNamespace()) == 0
        assert conn.closed is True


class TestCmdVacuum:
    def test_db_no_existe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.cli.audit._resolve_db_path",
            lambda args: SimpleNamespace(exists=lambda: False),
        )
        assert cmd_vacuum(SimpleNamespace()) == 1

    def test_vacuum_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({})
        monkeypatch.setattr(
            "knowledge.engine.cli.audit._resolve_db_path",
            lambda args: SimpleNamespace(
                exists=lambda: True,
                stat=lambda: SimpleNamespace(st_size=100),
            ),
        )
        monkeypatch.setattr("knowledge.engine.cli.audit.open_db", lambda p: conn)
        assert cmd_vacuum(SimpleNamespace()) == 0
        assert conn.closed is True
        assert any("VACUUM" in e for e in conn.executed)
