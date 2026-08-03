"""Tests para knowledge/engine/connection_pool.py — ReadConnectionPool."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.connection_pool import ReadConnectionPool


@pytest.fixture
def db_path(tmp_path) -> Path:
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    return db


class TestReadConnectionPool:
    def test_acquire_release(self, db_path) -> None:
        pool = ReadConnectionPool(db_path, max_connections=2)
        conn = pool.acquire()
        assert pool.active_count == 1
        assert pool.idle_count == 0
        row = conn.execute("SELECT COUNT(*) as c FROM t").fetchone()
        assert row["c"] == 1
        pool.release(conn)
        assert pool.active_count == 0
        assert pool.idle_count == 1

    def test_reutiliza_conexion(self, db_path) -> None:
        pool = ReadConnectionPool(db_path, max_connections=2)
        c1 = pool.acquire()
        pool.release(c1)
        c2 = pool.acquire()
        assert c1 is c2  # reutilizada

    def test_max_conexiones(self, db_path) -> None:
        pool = ReadConnectionPool(db_path, max_connections=2)
        c1 = pool.acquire()
        pool.acquire()
        assert pool.active_count == 2
        assert pool._active == 2
        # tercera acquire bloquea hasta release
        resultado: list = []

        def adquirir():
            c3 = pool.acquire()
            resultado.append(c3)
            pool.release(c3)

        t = threading.Thread(target=adquirir)
        t.start()
        time.sleep(0.1)
        assert not resultado  # bloqueado
        pool.release(c1)
        t.join(timeout=2)
        assert len(resultado) == 1

    def test_close_all(self, db_path) -> None:
        pool = ReadConnectionPool(db_path, max_connections=2)
        c1 = pool.acquire()
        c2 = pool.acquire()
        pool.release(c1)
        pool.release(c2)
        pool.close_all()
        assert pool.active_count == 0
        assert pool.idle_count == 0

    def test_propiedades(self, db_path) -> None:
        pool = ReadConnectionPool(db_path, max_connections=2)
        assert pool.active_count == 0
        assert pool.idle_count == 0
        conn = pool.acquire()
        assert pool.active_count == 1
        pool.release(conn)
        assert pool.idle_count == 1

    def test_new_connection_usa_open_db(self, db_path, monkeypatch) -> None:
        fake = mock.Mock(return_value="conn-fake")
        monkeypatch.setattr("knowledge.engine.connection.open_db", fake)
        pool = ReadConnectionPool(db_path, max_connections=1)
        conn = pool.acquire()
        assert conn == "conn-fake"
        fake.assert_called_once_with(db_path)
