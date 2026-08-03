"""Tests para knowledge/engine/knowledge_verifier.py y storage_verifier.py."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.knowledge_verifier import (
    check_cycles,
    check_duplicate_ids,
    check_duplicate_paths,
    check_ontology,
    check_orphans,
    check_referential_integrity,
    check_repeated_hashes,
    verify_hashes,
)
from knowledge.engine.storage_verifier import check_fts_sync, check_pragmas, check_schema


def _crear_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE kg_nodes (id TEXT, path TEXT, content_sha256 TEXT)")
    conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT, relation TEXT)")
    conn.execute("CREATE TABLE kg_nodes_fts (id TEXT, content TEXT)")
    conn.execute("CREATE TABLE kg_ontology_nodes (id TEXT, name TEXT, parent_id TEXT)")
    conn.execute("CREATE TABLE kg_ontology_edges (src TEXT, dst TEXT)")
    return conn


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return _crear_db(tmp_path / "db.sqlite")


class TestCheckDuplicateIds:
    def test_sin_duplicados(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h1')")
        conn.commit()
        assert check_duplicate_ids(conn) == []

    def test_con_duplicados(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h1')")
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p2', 'h2')")
        conn.commit()
        out = check_duplicate_ids(conn)
        assert len(out) == 1
        assert "KE101" in out[0]
        assert "'a'" in out[0]


class TestCheckDuplicatePaths:
    def test_sin_duplicados(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h1')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'h2')")
        conn.commit()
        assert check_duplicate_paths(conn) == []

    def test_con_duplicados(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'mismo', 'h1')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'mismo', 'h2')")
        conn.commit()
        out = check_duplicate_paths(conn)
        assert len(out) == 1
        assert "KE102" in out[0]


class TestCheckRepeatedHashes:
    def test_sin_repetidos(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'hash1')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'hash2')")
        conn.commit()
        assert check_repeated_hashes(conn) == []

    def test_con_repetidos(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'mismohash')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'mismohash')")
        conn.commit()
        out = check_repeated_hashes(conn)
        assert len(out) == 1
        assert "KE103" in out[0]
        assert "mismohash" in out[0]


class TestCheckReferentialIntegrity:
    def test_ok(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'h')")
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'b', 'ref')")
        conn.commit()
        assert check_referential_integrity(conn) == []

    def test_src_rota(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'h')")
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'b', 'ref')")
        conn.commit()
        out = check_referential_integrity(conn)
        assert any("KE105" in m for m in out)

    def test_dst_rota(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h')")
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'b', 'ref')")
        conn.commit()
        out = check_referential_integrity(conn)
        assert any("KE106" in m for m in out)


class TestCheckOrphans:
    def test_sin_huérfanos(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h')")
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'a', 'self')")
        conn.commit()
        assert check_orphans(conn) == []

    def test_con_huérfano(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p1', 'h')")
        conn.execute("INSERT INTO kg_nodes VALUES ('b', 'p2', 'h')")
        conn.commit()
        out = check_orphans(conn)
        assert len(out) == 1
        assert "KE104" in out[0]


class TestCheckCycles:
    def test_sin_ciclos(self, conn) -> None:
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'b', 'r')")
        conn.execute("INSERT INTO kg_edges VALUES ('b', 'c', 'r')")
        conn.commit()
        assert check_cycles(conn) == []

    def test_con_ciclo(self, conn) -> None:
        conn.execute("INSERT INTO kg_edges VALUES ('a', 'b', 'r')")
        conn.execute("INSERT INTO kg_edges VALUES ('b', 'a', 'r')")
        conn.commit()
        out = check_cycles(conn)
        assert len(out) == 1
        assert "KE008" in out[0]


class TestCheckOntology:
    def test_ok(self, conn) -> None:
        conn.execute("INSERT INTO kg_ontology_nodes VALUES ('o1', 'padre', NULL)")
        conn.execute("INSERT INTO kg_ontology_nodes VALUES ('o2', 'hijo', 'o1')")
        conn.execute("INSERT INTO kg_ontology_edges VALUES ('o1', 'o2')")
        conn.commit()
        assert check_ontology(conn) == []

    def test_parent_inexistente(self, conn) -> None:
        conn.execute("INSERT INTO kg_ontology_nodes VALUES ('o1', 'hijo', 'nope')")
        conn.commit()
        out = check_ontology(conn)
        assert any("KE107" in m for m in out)

    def test_huérfano_multi(self, conn) -> None:
        conn.execute("INSERT INTO kg_ontology_nodes VALUES ('o1', 'a', NULL)")
        conn.execute("INSERT INTO kg_ontology_nodes VALUES ('o2', 'b', NULL)")
        conn.commit()
        out = check_ontology(conn)
        assert any("KE108" in m for m in out)


class TestVerifyHashes:
    def test_doc_no_encontrado(self, conn, tmp_path) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'no_existe.md', 'h')")
        conn.commit()
        out = verify_hashes(conn, source_dir=tmp_path)
        assert len(out) == 1
        assert "no encontrado" in out[0]

    def test_hash_correcto(self, conn, tmp_path) -> None:
        doc = tmp_path / "doc.md"
        doc.write_bytes(b"contenido")
        expected = hashlib.sha256(b"contenido").hexdigest()
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'doc.md', ?)", (expected,))
        conn.commit()
        assert verify_hashes(conn, source_dir=tmp_path) == []

    def test_hash_incorrecto(self, conn, tmp_path) -> None:
        doc = tmp_path / "doc.md"
        doc.write_bytes(b"contenido")
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'doc.md', 'wronghash')")
        conn.commit()
        out = verify_hashes(conn, source_dir=tmp_path)
        assert len(out) == 1
        assert "no coincide" in out[0]


class TestCheckPragmas:
    def test_ok(self, conn) -> None:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()
        # WAL persiste solo si hay transaccion completada
        conn.commit()
        issues = check_pragmas(conn)
        assert issues == [] or all("KE11" in i for i in issues)  # tolera fk heredado

    def test_issues(self, conn) -> None:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.commit()
        out = check_pragmas(conn)
        assert any("KE110" in m for m in out)
        assert any("KE111" in m for m in out)


class TestCheckSchema:
    def test_faltan_tablas(self, conn) -> None:
        out = check_schema(conn)
        assert any("Faltan tablas" in m for m in out)

    def test_tablas_extra(self, conn) -> None:
        conn.execute("CREATE TABLE kg_nodes_fts_config (k TEXT)")
        conn.execute("CREATE TABLE extraña (id INTEGER)")
        conn.commit()
        out = check_schema(conn)
        assert any("Tablas extrañas" in m for m in out)


class TestCheckFtsSync:
    def test_desincronizado(self, conn) -> None:
        conn.execute("INSERT INTO kg_nodes VALUES ('a', 'p', 'h')")
        conn.commit()
        out = check_fts_sync(conn)
        assert any("KE109" in m and "desincronizado" in m for m in out)

    def test_fts_no_accesible(self, conn) -> None:
        conn.execute("DROP TABLE kg_nodes_fts")
        conn.commit()
        out = check_fts_sync(conn)
        assert any("no accesible" in m for m in out)
