"""Tests Fase 7 — Auto-recovery/Queue (split de test_fase7.py)."""
from __future__ import annotations

from pathlib import Path

from _fase7_helpers import (  # noqa: F401
    AssetSource,
    MagicMock,
    OllamaEmbedder,
    QdrantVectorStore,
    httpx,
    mock_ollama_health,
    mock_qdrant_client,
    patch,
    pytest,
    sqlite3,
)


class TestQdrantAutoRecovery:
    def test_check_available_resets_degraded(self, mock_qdrant_client):  # noqa: F811
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        mock_qdrant_client.get.return_value.status_code = 200
        assert store.check_available()
        assert store.available

    def test_check_available_4xx_no_recovery(self, mock_qdrant_client):  # noqa: F811
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        resp = MagicMock()
        resp.status_code = 403
        mock_qdrant_client.get.return_value = resp
        assert not store.check_available()
        assert not store.available

    def test_check_available_5xx_backoff(self, mock_qdrant_client):  # noqa: F811
        store = QdrantVectorStore(collection="test")
        store._degraded = True
        store._last_check = 0.0
        mock_qdrant_client.get.side_effect = httpx.HTTPError("5xx")
        assert not store.check_available()
        assert store._backoff > 1.0

    def test_available_returns_not_degraded(self, mock_qdrant_client):  # noqa: F811
        store = QdrantVectorStore(collection="test")
        assert store.available
        store._degraded = True
        assert not store.available


# ── Ollama auto-recovery ─────────────────────────────────────────────────


class TestOllamaAutoRecovery:
    def test_check_available_resets_degraded(self, mock_ollama_health):  # noqa: F811
        embedder = OllamaEmbedder()
        embedder._degraded = True
        embedder._last_check = 0.0
        mock_ollama_health.return_value = {"status": "ok", "modelos_disponibles": [], "latency_ms": 5}
        assert embedder.check_available()
        assert embedder.available

    def test_check_available_failure_backoff(self, mock_ollama_health):  # noqa: F811
        embedder = OllamaEmbedder()
        embedder._degraded = True
        embedder._last_check = 0.0
        mock_ollama_health.return_value = {"status": "error", "detail": "fail", "latency_ms": 100}
        assert not embedder.check_available()
        assert embedder._backoff > 1.0

    def test_available_returns_boolean(self, mock_ollama_health):  # noqa: F811
        embedder = OllamaEmbedder()
        assert embedder.available
        embedder._degraded = True
        assert not embedder.available


# ── ExtractionService queue ───────────────────────────────────────────────



class TestExtractionQueue:
    def test_queue_extract_creates_job(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_queue.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        job_id = service.queue_extract(AssetSource("filesystem", "/tmp/test.md"))

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status, job_type FROM op_jobs WHERE id = ?", (int(job_id),)).fetchone()
        conn.close()
        assert row is not None
        assert row["status"] == "pending"
        assert row["job_type"] == "extraction"

    def test_get_queue_status(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_status.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        cur = conn.execute(
            "INSERT INTO op_jobs (job_type, status, created_at) VALUES ('extraction', 'done', datetime('now'))",
        )
        job_id = str(cur.lastrowid)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        status = service.get_queue_status(job_id)
        assert status["status"] == "done"

    def test_get_queue_status_not_found(self, tmp_path: Path):
        from knowledge.engine.extraction_service import MetadataExtractionService

        db = tmp_path / "test_nf.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT, result_data TEXT
            );
        """)
        conn.commit()
        conn.close()

        service = MetadataExtractionService(db)
        status = service.get_queue_status("9999")
        assert status["status"] == "not_found"


# ── Reconciliation ────────────────────────────────────────────────────────


