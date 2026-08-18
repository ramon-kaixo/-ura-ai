"""Tests de cobertura de knowledge/engine/connection.py.

open_db (PRAGMAs), begin_immediate (éxito, SQLITE_BUSY con reintento,
timeout, error no-BUSY) y _inc_busy_retry (con/sin métricas).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from unittest import mock

import pytest

from knowledge.engine.connection import _inc_busy_retry, begin_immediate, open_db


class TestOpenDb:
    def test_pragmas_y_row_factory(self, tmp_path) -> None:
        db = tmp_path / "k.db"
        conn = open_db(db)
        try:
            assert conn.row_factory is sqlite3.Row
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        finally:
            conn.close()

    def test_acepta_str(self, tmp_path) -> None:
        conn = open_db(str(tmp_path / "s.db"))
        conn.close()


class TestBeginImmediate:
    def test_ok(self, tmp_path) -> None:
        conn = open_db(tmp_path / "b.db")
        try:
            begin_immediate(conn)
            conn.rollback()
        finally:
            conn.close()

    def test_error_no_busy_relanza(self, tmp_path) -> None:
        conn = open_db(tmp_path / "c.db")
        try:
            with pytest.raises(sqlite3.OperationalError):
                begin_immediate(conn, timeout=0.2)
                begin_immediate(conn, timeout=0.2)  # segundo BEGIN sin ROLLBACK -> no-BUSY
        finally:
            conn.close()

    def test_retry_hasta_liberar(self, tmp_path) -> None:
        db = tmp_path / "r.db"
        # Uso multi-hilo legitimo: la conexion del "otro escritor" se crea con
        # check_same_thread=False (si no, sqlite3 prohibe usarla en el hilo).
        a = sqlite3.connect(db, check_same_thread=False)
        a.row_factory = sqlite3.Row
        a.execute("PRAGMA journal_mode=WAL")
        a.execute("PRAGMA busy_timeout=5000")
        b = open_db(db)
        try:
            begin_immediate(a)
            b.execute("PRAGMA busy_timeout=150")  # reintento interno corto -> el loop de begin_immediate actua
            stop = threading.Event()

            def _releaser() -> None:
                time.sleep(0.3)
                a.rollback()
                stop.set()

            t = threading.Thread(target=_releaser, daemon=True)
            t.start()
            begin_immediate(b, timeout=5.0)
            b.rollback()
            assert stop.wait(2.0)
        finally:
            a.close()
            b.close()

    def test_timeout(self, tmp_path) -> None:
        db = tmp_path / "t.db"
        a = open_db(db)
        b = open_db(db)
        try:
            begin_immediate(a)
            with pytest.raises(sqlite3.OperationalError) as e:
                begin_immediate(b, timeout=0.15)
            assert "Could not acquire BEGIN IMMEDIATE" in str(e.value)
        finally:
            a.close()
            b.close()


class TestIncBusyRetry:
    def test_con_metricas(self, monkeypatch) -> None:
        metrics = mock.Mock()
        metrics.sqlite_busy_retries_total = mock.Mock()
        monkeypatch.setattr("knowledge.engine.metrics.sqlite_busy_retries_total", metrics.sqlite_busy_retries_total)
        _inc_busy_retry()
        metrics.sqlite_busy_retries_total.inc.assert_called_once()

    def test_sin_metricas(self, monkeypatch) -> None:
        def _boom():
            raise RuntimeError("metrics no disponible")

        monkeypatch.setattr("knowledge.engine.metrics.sqlite_busy_retries_total", mock.Mock(side_effect=_boom))
        _inc_busy_retry()  # no debe lanzar

    def test_import_falla(self, monkeypatch) -> None:
        import sys

        with (
            mock.patch.dict(sys.modules, {"knowledge.engine.metrics": None}),
            mock.patch("builtins.__import__", side_effect=ImportError("no metrics")),
        ):
            _inc_busy_retry()  # no debe lanzar
