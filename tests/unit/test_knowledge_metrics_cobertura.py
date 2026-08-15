"""Cobertura 100x100 de knowledge/engine/metrics.py (TASK-20260815-003).

Cubre record_* (en memoria), _set_db_gauges (SQLite derivado), export_metrics
y _reset_for_testing con mocks simples (FakeConn/FakeRow).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from knowledge.engine.metrics import (
    _reset_for_testing,
    _set_db_gauges,
    export_metrics,
    record_archive,
    record_compile,
    record_error,
    record_fusion,
    record_qdrant_sync,
    record_search,
)


class FakeRow:
    """Row de sqlite3 con acceso por nombre ("c") o por índice."""

    def __init__(self, val: Any) -> None:
        self._val = val

    def __getitem__(self, key: Any) -> Any:
        if key == "c":
            return self._val
        return self._val[key]


class FakeConn:
    def __init__(self, results: dict[str, Any]) -> None:
        self._results = results
        self.executed: list[str] = []
        self.closed = False
        self._current: Any = None

    def execute(self, sql: str) -> FakeConn:
        self.executed.append(sql)
        self._current = self._results.get(sql, None)
        return self

    def fetchone(self) -> Any:
        return self._current

    def close(self) -> None:
        self.closed = True


class TestRecordCompile:
    def test_default(self) -> None:
        record_compile()
        text = export_metrics().decode()
        assert 'ke_compile_requests_total{source="orchestrator"} 1.0' in text

    def test_custom_source(self) -> None:
        record_compile(source="scheduler")
        text = export_metrics().decode()
        assert 'ke_compile_requests_total{source="scheduler"} 1.0' in text


class TestRecordSearch:
    def test_con_duracion(self) -> None:
        record_search(mode="hybrid", duration=0.3)
        text = export_metrics().decode()
        assert 'ke_search_requests_total{mode="hybrid"} 1.0' in text
        assert "ke_search_duration_seconds_bucket" in text

    def test_sin_duracion(self) -> None:
        record_search(mode="lexical", duration=0.0)
        text = export_metrics().decode()
        assert 'ke_search_requests_total{mode="lexical"} 1.0' in text
        assert 'ke_search_duration_seconds_count{mode="lexical"}' not in text


class TestRecordQdrantSync:
    def test_default(self) -> None:
        record_qdrant_sync()
        text = export_metrics().decode()
        assert 'ke_qdrant_sync_ops_total{operation="upsert",status="done"} 1.0' in text

    def test_custom(self) -> None:
        record_qdrant_sync(operation="delete", status="failed")
        text = export_metrics().decode()
        assert 'ke_qdrant_sync_ops_total{operation="delete",status="failed"} 1.0' in text


class TestRecordFusion:
    def test_con_duracion(self) -> None:
        record_fusion(claims=2, facts=3, duration=1.5, status="ok")
        text = export_metrics().decode()
        assert 'ke_fusion_requests_total{status="ok"} 1.0' in text
        assert "ke_fusion_facts_total 3.0" in text
        assert "ke_fusion_duration_seconds_bucket" in text

    def test_sin_duracion(self) -> None:
        record_fusion(claims=0, facts=0, duration=0.0, status="failed")
        text = export_metrics().decode()
        assert 'ke_fusion_requests_total{status="failed"} 1.0' in text
        assert "ke_fusion_facts_total" in text
        assert 'ke_fusion_duration_seconds_count{status="failed"}' not in text


class TestRecordArchive:
    def test_default(self) -> None:
        record_archive()
        text = export_metrics().decode()
        assert 'ke_archive_ops_total{kind="source",status="completed"} 1.0' in text

    def test_custom(self) -> None:
        record_archive(kind="compiler", status="failed")
        text = export_metrics().decode()
        assert 'ke_archive_ops_total{kind="compiler",status="failed"} 1.0' in text


class TestRecordError:
    def test_codigo(self) -> None:
        record_error("E-42")
        text = export_metrics().decode()
        assert 'ke_errors_total{code="E-42"} 1.0' in text


class TestSetDbGauges:
    def test_db_path_none(self) -> None:
        _set_db_gauges(None)

    def test_db_no_existe(self) -> None:
        _set_db_gauges(Path("/tmp/no-existe-ura-metrics.db"))

    def test_gauges_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        results = {
            "SELECT COUNT(*) as c FROM kg_nodes": FakeRow(42),
            "SELECT COUNT(*) as c FROM kg_edges": FakeRow(7),
            "SELECT COUNT(*) as c FROM op_compiler_runs": FakeRow(3),
            "SELECT COUNT(*) as c FROM op_compile_errors WHERE severity='ERROR'": FakeRow(1),
            "SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending', 'failed')": FakeRow(5),
            "PRAGMA user_version": FakeRow((9,)),
            "SELECT COUNT(*) as c FROM op_jobs WHERE job_type = 'compile' AND status IN ('pending', 'running')": FakeRow(
                2
            ),
            "SELECT COUNT(*) as c FROM op_jobs WHERE job_type = 'archive_source' AND status IN ('pending', 'running')": FakeRow(
                4
            ),
        }
        conn = FakeConn(results)
        monkeypatch.setattr("knowledge.engine.metrics.open_db", lambda p: conn)
        text = export_metrics(db_path=Path(__file__)).decode()
        assert conn.closed is True
        assert "ke_db_nodes_total 42.0" in text
        assert "ke_db_edges_total 7.0" in text
        assert "ke_db_compile_runs_total 3.0" in text
        assert "ke_db_compile_errors_total 1.0" in text
        assert "ke_db_pending_sync 5.0" in text
        assert "ke_db_schema_version 9.0" in text
        assert "ke_compile_queue_length 2.0" in text
        assert "ke_archive_queue_length 4.0" in text
        assert len(conn.executed) == 8

    def test_gauges_sin_filas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({})
        monkeypatch.setattr("knowledge.engine.metrics.open_db", lambda p: conn)
        text = export_metrics(db_path=Path(__file__)).decode()
        assert "ke_db_nodes_total 0.0" in text
        assert "ke_db_edges_total 0.0" in text
        assert "ke_db_compile_runs_total 0.0" in text
        assert "ke_db_compile_errors_total 0.0" in text
        assert "ke_db_pending_sync 0.0" in text
        assert "ke_db_schema_version 0.0" in text
        assert "ke_compile_queue_length 0.0" in text
        assert "ke_archive_queue_length 0.0" in text

    def test_error_bd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(_path: Path) -> Any:
            raise RuntimeError("disk full")

        monkeypatch.setattr("knowledge.engine.metrics.open_db", boom)
        _set_db_gauges(Path(__file__))


class TestExportMetrics:
    def test_sin_db(self) -> None:
        data = export_metrics()
        assert isinstance(data, bytes)
        assert b"ke_search_requests_total" in data

    def test_con_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.metrics.open_db",
            lambda p: FakeConn({"PRAGMA user_version": FakeRow((1,))}),
        )
        data = export_metrics(db_path=Path(__file__))
        assert b"ke_db_schema_version 1.0" in data


class TestResetForTesting:
    def test_reset_y_registro(self) -> None:
        _reset_for_testing()
        text = export_metrics().decode()
        assert "ke_search_requests_total" in text
        assert "ke_db_nodes_total" in text
        assert "ke_fusion_requests_total" in text
        record_compile(source="post-reset")
        assert 'ke_compile_requests_total{source="post-reset"} 1.0' in export_metrics().decode()

    def test_reset_idempotente(self) -> None:
        _reset_for_testing()
        _reset_for_testing()
        assert b"ke_db_edges_total" in export_metrics()
