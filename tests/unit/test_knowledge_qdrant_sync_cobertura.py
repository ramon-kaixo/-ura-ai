"""Cobertura 100x100 de knowledge/engine/qdrant_sync.py (TASK-20260815-003).

Cubre la sincronización con Qdrant: _get_qdrant, tracking SQLite
(op_vector_sync), upsert/delete de documentos, retry_failed,
pending deletes y búsqueda semántica — incluidas todas las ramas
de fallo y degradación (graceful degradation).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.models import MAX_SYNC_ATTEMPTS, Chunk, Document, Frontmatter
from knowledge.engine.qdrant_sync import (
    _chunk_version,
    _get_qdrant,
    _sync_delete,
    _sync_upsert,
    _track_conn,
    _track_operation,
    get_pending_delete_ids,
    retry_failed,
    search_semantic,
    sync_documents,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS op_vector_sync (
    doc_id      TEXT NOT NULL,
    operation   TEXT NOT NULL,
    run_id      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',
    last_error  TEXT NOT NULL DEFAULT '',
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (doc_id, operation, run_id)
);
"""


def _make_doc(
    doc_id: str = "doc-1",
    body: str = "hola mundo test",
    sha: str = "aabbccddeeff001122334455",
) -> Document:
    """Documento real para los tests."""
    return Document(
        doc_id=doc_id,
        doc_type="md",
        path=f"/tmp/{doc_id}.md",
        content_sha256=sha,
        frontmatter=Frontmatter(title="Título"),
        body=body,
    )


def _make_chunk(doc_id: str, index: int, text: str) -> Chunk:
    """Chunk real para los tests."""
    return Chunk(
        doc_id=doc_id,
        chunk_index=index,
        text=text,
        doc_type="md",
        path=f"/tmp/{doc_id}.md",
        title="Título",
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """BD SQLite real con la tabla op_vector_sync creada."""
    p = tmp_path / "kb.sqlite"
    conn = sqlite3.connect(str(p))
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return p


def _read_rows(db_path: Path) -> list[tuple[Any, ...]]:
    """Lee todas las filas de op_vector_sync con una conexión nueva."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        return [tuple(r) for r in conn.execute("SELECT * FROM op_vector_sync ORDER BY doc_id, operation")]
    finally:
        conn.close()


def _insert_row(db_path: Path, doc_id: str, operation: str, status: str, attempts: int, run_id: int = 0) -> None:
    """Inserta una fila inicial en op_vector_sync."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO op_vector_sync (doc_id, operation, run_id, status, last_error, attempts) "
            "VALUES (?, ?, ?, ?, '', ?)",
            (doc_id, operation, run_id, status, attempts),
        )
        conn.commit()
    finally:
        conn.close()


class FakeQdrant:
    """Cliente Qdrant simulado con inyectores de fallo."""

    def __init__(self) -> None:
        self.saved: list[tuple[list[Any], str]] = []
        self.deleted: list[tuple[dict[str, Any], str]] = []
        self.results: list[Any] = []
        self.fail_embeddings = False
        self.fail_batch = False
        self.fail_delete = False
        self.fail_search = False
        self.delete_result: bool | None = None

    def generar_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        if self.fail_embeddings:
            raise RuntimeError("embed fail")
        return [[0.5] * 768 for _ in texts]

    def guardar_documentos_batch(self, docs: list[Any], collection: str) -> None:
        if self.fail_batch:
            raise RuntimeError("upsert fail")
        self.saved.append((docs, collection))

    def eliminar_por_filtro(self, filtro: dict[str, Any], collection: str = "") -> bool:
        if self.fail_delete:
            raise RuntimeError("delete fail")
        self.deleted.append((filtro, collection))
        return True if self.delete_result is None else self.delete_result

    def buscar_documentos(self, collection: str, query: str, top_k: int = 5) -> list[Any]:
        if self.fail_search:
            raise RuntimeError("search fail")
        return self.results


class FakeMotorQdrant:
    """Sustituto de motor.core.qdrant_client.QdrantClient para _get_qdrant."""

    inst: Any = None

    @classmethod
    def instancia(cls, config: Any) -> Any:
        return cls.inst


class TrackingConn:
    """Conexión falsa que registra commit/rollback/close."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled = True

    def close(self) -> None:
        self.closed = True

    def execute(self, *args: Any, **kwargs: Any) -> TrackingConn:
        return self


def _install_fresh_degraded_mode(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Instala un DegradedMode limpio por test y lo retorna."""
    from motor.core.state import DegradedMode

    fresh = DegradedMode()
    monkeypatch.setattr(DegradedMode, "instancia", lambda: fresh)
    return fresh


class TestGetQdrant:
    def test_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dm = _install_fresh_degraded_mode(monkeypatch)
        fake = FakeQdrant()
        FakeMotorQdrant.inst = fake
        monkeypatch.setattr("motor.core.config.UraConfig", lambda: object())
        monkeypatch.setattr("motor.core.qdrant_client.QdrantClient", FakeMotorQdrant)

        result = _get_qdrant()

        assert result is fake
        assert not dm.is_degraded("qdrant_sync")

    def test_sin_embeddings_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dm = _install_fresh_degraded_mode(monkeypatch)
        FakeMotorQdrant.inst = object()
        monkeypatch.setattr("motor.core.config.UraConfig", lambda: object())
        monkeypatch.setattr("motor.core.qdrant_client.QdrantClient", FakeMotorQdrant)

        result = _get_qdrant()

        assert result is None
        assert dm.is_degraded("qdrant_sync")

    def test_excepcion_import_o_instancia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dm = _install_fresh_degraded_mode(monkeypatch)

        def boom(config: Any) -> Any:
            raise RuntimeError("no qdrant")

        monkeypatch.setattr("motor.core.config.UraConfig", lambda: object())
        monkeypatch.setattr("motor.core.qdrant_client.QdrantClient.instancia", staticmethod(boom))

        result = _get_qdrant()

        assert result is None
        assert dm.is_degraded("qdrant_sync")


class TestChunkVersion:
    def test_con_sha(self) -> None:
        doc = _make_doc(sha="1234567890abcdef")
        assert _chunk_version(doc) == "1234567890ab"

    def test_sin_sha(self) -> None:
        doc = _make_doc(sha="")
        assert _chunk_version(doc) == "0"


class TestTrackConn:
    def test_exito_commits_y_cierra(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        conn = TrackingConn()
        monkeypatch.setattr("knowledge.engine.qdrant_sync.open_db", lambda p: conn)

        with _track_conn(db_path):
            pass

        assert conn.committed
        assert not conn.rolled
        assert conn.closed

    def test_error_hace_rollback_y_relanza(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        conn = TrackingConn()
        monkeypatch.setattr("knowledge.engine.qdrant_sync.open_db", lambda p: conn)

        with pytest.raises(ValueError, match="boom"), _track_conn(db_path):
            raise ValueError("boom")

        assert not conn.committed
        assert conn.rolled
        assert conn.closed


class TestTrackOperation:
    def test_failed_nuevo(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            _track_operation(conn, "d1", "upsert", "failed", error="err", run_id=3)
            conn.commit()
        finally:
            conn.close()

        rows = _read_rows(db_path)
        assert len(rows) == 1
        doc_id, operation, run_id, status, last_error, attempts = rows[0][:6]
        assert (doc_id, operation, run_id, status) == ("d1", "upsert", 3, "failed")
        assert last_error == "err"
        assert attempts == 1

    def test_failed_acumula_attempts(self, db_path: Path) -> None:
        _insert_row(db_path, "d1", "upsert", "failed", attempts=1, run_id=3)
        conn = sqlite3.connect(str(db_path))
        try:
            _track_operation(conn, "d1", "upsert", "failed", error="err2", run_id=3)
            conn.commit()
        finally:
            conn.close()

        rows = _read_rows(db_path)
        assert rows[0][3] == "failed"
        assert rows[0][5] == 2

    def test_failed_convierte_a_dead_letter(self, db_path: Path) -> None:
        _insert_row(db_path, "d1", "upsert", "failed", attempts=MAX_SYNC_ATTEMPTS - 1, run_id=0)
        conn = sqlite3.connect(str(db_path))
        try:
            _track_operation(conn, "d1", "upsert", "failed", error="ultimo", run_id=0)
            conn.commit()
        finally:
            conn.close()

        rows = _read_rows(db_path)
        assert rows[0][3] == "dead_letter"
        assert rows[0][5] == MAX_SYNC_ATTEMPTS

    def test_ok_nuevo(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            _track_operation(conn, "d1", "delete", "done", run_id=1)
            conn.commit()
        finally:
            conn.close()

        rows = _read_rows(db_path)
        assert rows[0][3] == "done"
        assert rows[0][4] == ""
        assert rows[0][5] == 0

    def test_ok_resetea_fila_fallida(self, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "failed", attempts=5, run_id=1)
        conn = sqlite3.connect(str(db_path))
        try:
            _track_operation(conn, "d1", "delete", "done", run_id=1)
            conn.commit()
        finally:
            conn.close()

        rows = _read_rows(db_path)
        assert rows[0][3] == "done"
        assert rows[0][4] == ""
        assert rows[0][5] == 0


class TestSyncUpsert:
    def test_sin_chunks_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc(body="   ")
        client = FakeQdrant()
        monkeypatch.setattr("knowledge.engine.qdrant_sync.chunk_document", lambda d, **kw: [])

        assert _sync_upsert(client, doc) is True
        assert client.saved == []

    def test_fallo_embeddings_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc()
        client = FakeQdrant()
        client.fail_embeddings = True
        monkeypatch.setattr(
            "knowledge.engine.qdrant_sync.chunk_document",
            lambda d, **kw: [_make_chunk(d.doc_id, 0, "texto")],
        )

        assert _sync_upsert(client, doc) is False

    def test_dim_incorrecta_se_omite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc()
        client = FakeQdrant()
        monkeypatch.setattr(
            "knowledge.engine.qdrant_sync.chunk_document", lambda d, **kw: [_make_chunk(d.doc_id, 0, "texto")]
        )
        monkeypatch.setattr(client, "generar_embeddings_batch", lambda texts: [[1.0] * 3])

        assert _sync_upsert(client, doc) is True
        assert client.saved == []

    def test_sin_embeddings_para_chunk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc()
        client = FakeQdrant()
        chunks = [_make_chunk("doc-1", 0, "texto a"), _make_chunk("doc-1", 1, "texto b")]
        monkeypatch.setattr("knowledge.engine.qdrant_sync.chunk_document", lambda d, **kw: chunks)
        monkeypatch.setattr(client, "generar_embeddings_batch", lambda texts: [[1.0] * 768])

        assert _sync_upsert(client, doc) is True
        assert len(client.saved[0][0]) == 1
        assert client.saved[0][1] == "ura_documents"
        assert client.saved[0][0][0][0] == "doc-1"

    def test_exito_guarda_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc(sha="aabbccddeeff")
        client = FakeQdrant()
        chunks = [_make_chunk("doc-1", 0, "texto"), _make_chunk("doc-1", 1, "texto2")]
        monkeypatch.setattr("knowledge.engine.qdrant_sync.chunk_document", lambda d, **kw: chunks)

        assert _sync_upsert(client, doc) is True

        docs, collection = client.saved[0]
        assert collection == "ura_documents"
        assert len(docs) == 2
        first = docs[0]
        assert first[0] == "doc-1"
        assert first[1] == "texto"
        payload = first[2]
        assert payload["doc_type"] == "md"
        assert payload["chunk_version"] == "aabbccddeeff"
        assert payload["embed_model"] == "nomic-embed-text:latest"
        assert payload["embed_dim"] == 768
        assert payload["embed_version"] == "1"
        assert "doc_id" not in payload
        assert "text" not in payload

    def test_fallo_batch_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = _make_doc()
        client = FakeQdrant()
        client.fail_batch = True
        monkeypatch.setattr(
            "knowledge.engine.qdrant_sync.chunk_document", lambda d, **kw: [_make_chunk(d.doc_id, 0, "texto")]
        )

        assert _sync_upsert(client, doc) is False


class TestSyncDelete:
    def test_exito_true(self) -> None:
        client = FakeQdrant()
        assert _sync_delete(client, "doc-9") is True
        filtro, collection = client.deleted[0]
        assert collection == "ura_documents"
        assert filtro == {"must": [{"key": "doc_id", "match": {"value": "doc-9"}}]}

    def test_falso_false(self) -> None:
        client = FakeQdrant()
        client.delete_result = False
        assert _sync_delete(client, "doc-9") is False

    def test_excepcion_false(self) -> None:
        client = FakeQdrant()
        client.fail_delete = True
        assert _sync_delete(client, "doc-9") is False


class TestSyncDocuments:
    def test_sin_client_tracking_pending(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: None)
        docs = [_make_doc("d1"), _make_doc("d2")]

        synced = sync_documents(db_path, docs, ["del-1"], run_id=7)

        assert synced == 0
        rows = _read_rows(db_path)
        assert len(rows) == 3
        assert rows[0][:4] == ("d1", "upsert", 7, "pending")
        assert rows[1][:4] == ("d2", "upsert", 7, "pending")
        assert rows[2][:4] == ("del-1", "delete", 7, "pending")

    def test_todo_ok(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        client = FakeQdrant()
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)
        docs = [_make_doc("d1"), _make_doc("d2")]

        synced = sync_documents(db_path, docs, ["del-1"], run_id=1)

        assert synced == 3
        rows = _read_rows(db_path)
        assert rows[0][:4] == ("d1", "upsert", 1, "done")
        assert rows[1][:4] == ("d2", "upsert", 1, "done")
        assert rows[2][:4] == ("del-1", "delete", 1, "done")

    def test_fallo_upsert_no_cuenta(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        client = FakeQdrant()
        client.fail_batch = True
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        synced = sync_documents(db_path, [_make_doc("d1")], ["del-1"], run_id=1)

        assert synced == 1
        rows = _read_rows(db_path)
        assert rows[0][:4] == ("d1", "upsert", 1, "failed")
        assert rows[1][:4] == ("del-1", "delete", 1, "done")

    def test_fallo_delete_no_cuenta(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        client = FakeQdrant()
        client.fail_delete = True
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        synced = sync_documents(db_path, [_make_doc("d1")], ["del-1", "del-2"], run_id=1)

        assert synced == 1
        rows = _read_rows(db_path)
        assert rows[0][:4] == ("d1", "upsert", 1, "done")
        assert rows[1][:4] == ("del-1", "delete", 1, "failed")
        assert rows[2][:4] == ("del-2", "delete", 1, "failed")

    def test_sin_docs_ni_deletes(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        client = FakeQdrant()
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        assert sync_documents(db_path, [], []) == 0


class TestRetryFailed:
    def test_error_abriendo_db(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        monkeypatch.setattr(
            "knowledge.engine.qdrant_sync.open_db", lambda p: (_ for _ in ()).throw(RuntimeError("lock"))
        )

        assert retry_failed(db_path) == 0

    def test_sin_filas(self, db_path: Path) -> None:
        assert retry_failed(db_path) == 0

    def test_filas_agotadas_no_se_reintentan(self, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "failed", attempts=MAX_SYNC_ATTEMPTS)
        assert retry_failed(db_path) == 0

    def test_sin_client_no_recupera(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "pending", attempts=1)
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: None)

        assert retry_failed(db_path) == 0

    def test_recupera_deletes_y_salta_upserts(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "pending", attempts=1, run_id=1)
        _insert_row(db_path, "d2", "upsert", "failed", attempts=3, run_id=2)
        _insert_row(db_path, "d3", "delete", "failed", attempts=2, run_id=4)
        client = FakeQdrant()
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        recovered = retry_failed(db_path)

        assert recovered == 2
        assert len(client.deleted) == 2
        rows = _read_rows(db_path)
        assert rows[0][:4] == ("d1", "delete", 1, "done")
        assert rows[1][:4] == ("d2", "upsert", 2, "failed")
        assert rows[2][:4] == ("d3", "delete", 4, "done")

    def test_delete_fallido_no_recupera(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "pending", attempts=1)
        client = FakeQdrant()
        client.fail_delete = True
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        assert retry_failed(db_path) == 0

    def test_operacion_desconocida_no_recupera(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        _insert_row(db_path, "d1", "migrate", "pending", attempts=1)
        client = FakeQdrant()
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        assert retry_failed(db_path) == 0
        assert client.deleted == []


class TestGetPendingDeleteIds:
    def test_solo_deletes_pendientes_failed(self, db_path: Path) -> None:
        _insert_row(db_path, "d1", "delete", "pending", attempts=1)
        _insert_row(db_path, "d2", "delete", "failed", attempts=2)
        _insert_row(db_path, "d3", "upsert", "pending", attempts=1)
        _insert_row(db_path, "d4", "delete", "done", attempts=0)

        result = get_pending_delete_ids(db_path)

        assert set(result) == {"d1", "d2"}

    def test_error_abriendo_db(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        monkeypatch.setattr(
            "knowledge.engine.qdrant_sync.open_db", lambda p: (_ for _ in ()).throw(RuntimeError("lock"))
        )

        assert get_pending_delete_ids(db_path) == []


class TestSearchSemantic:
    def test_sin_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: None)
        assert search_semantic("query") == []

    def test_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = FakeQdrant()
        client.results = [
            SimpleNamespace(
                payload={
                    "doc_id": "d1",
                    "chunk_index": 2,
                    "text": "texto",
                    "title": "Título",
                    "chunk_version": "abc",
                },
                score=0.9,
            ),
            SimpleNamespace(payload={"doc_id": "d2"}, score=0.5),
        ]
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        hits = search_semantic("query", top_k=10)

        assert hits == [
            {
                "doc_id": "d1",
                "chunk_index": 2,
                "text": "texto",
                "title": "Título",
                "score": 0.9,
                "chunk_version": "abc",
            },
            {"doc_id": "d2", "chunk_index": 0, "text": "", "title": "", "score": 0.5, "chunk_version": ""},
        ]

    def test_excepcion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = FakeQdrant()
        client.fail_search = True
        monkeypatch.setattr("knowledge.engine.qdrant_sync._get_qdrant", lambda: client)

        assert search_semantic("query") == []
