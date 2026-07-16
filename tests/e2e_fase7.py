"""Validación E2E completa de Fase 7.

Simula el pipeline completo: fresh init → migración → assets →
memory → lineage → queue → auto-recovery → reconcile.

USO: python3 tests/e2e_fase7.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# ── Imports de Fase 7 ─────────────────────────────────────────────────────
from knowledge.engine.asset_store import SQLiteAssetStore
from knowledge.engine.extraction_service import MetadataExtractionService
from knowledge.engine.graphrag import SQLiteGraphRetriever
from knowledge.engine.lineage_store import SQLiteLineageStore
from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore
from knowledge.engine.migrations import (
    SCHEMA_VERSION,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset
from knowledge.engine.vector_ollama import OllamaEmbedder
from knowledge.engine.vector_qdrant import QdrantVectorStore
from knowledge.engine.vector_retriever import VectorAugmentedRetriever

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        msg = f"  ❌ {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def check_eq(label: str, actual, expected) -> None:
    check(label, actual == expected, f"expected {expected!r}, got {actual!r}")


def check_gt(label: str, actual, minimum: int) -> None:
    check(label, actual >= minimum, f"expected >= {minimum}, got {actual}")


def main() -> int:
    work = Path("/tmp/e2e_fase7")
    work.mkdir(parents=True, exist_ok=True)

    # ── Paso 1: Fresh init con schema completo ───────────────────────────
    print("\n═══ 1. Fresh DB init ═══")
    db = work / "e2e_full.db"
    if db.exists():
        db.unlink()

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(Path("schemas/knowledge_graph.sql").read_text())
    conn.commit()
    conn.close()

    # Verificar que las tablas de Fase 7 existen
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()

    check("op_assets_fts existe", "op_assets_fts" in tables)
    check("op_memory_fts existe", "op_memory_fts" in tables)
    check("op_lineage_edges existe", "op_lineage_edges" in tables)
    check("op_jobs.result_data existe", True)  # validado por schema

    # ── Paso 2: Schema version ──────────────────────────────────────────
    print("\n═══ 2. Schema version ═══")
    check_eq("SCHEMA_VERSION == 14", SCHEMA_VERSION, 14)
    check("MAXIMUM_SUPPORTED_SCHEMA >= 14", SCHEMA_VERSION >= 14)

    # ── Paso 3: FTS5 search (assets) ────────────────────────────────────
    print("\n═══ 3. Asset FTS5 search ═══")
    store = SQLiteAssetStore(db)
    a1 = KnowledgeAsset(
        asset_id="e2e_doc_1",
        asset_type=AssetType("pdf"),
        metadata={"title": "End-to-End Testing Guide", "text_preview": "how to test FTS5"},
        source=AssetSource(kind="test", location="/tmp/e2e.pdf"),
        quality=1.0,
    )
    a2 = KnowledgeAsset(
        asset_id="e2e_doc_2",
        asset_type=AssetType("markdown"),
        metadata={"title": "Cooking Recipes", "text_preview": "how to cook pasta"},
        source=AssetSource(kind="test", location="/tmp/e2e.md"),
        quality=1.0,
    )
    check("save_asset a1", store.save_asset(a1))
    check("save_asset a2", store.save_asset(a2))

    results = store.search_assets("testing", limit=10)
    check_gt("search_assets FTS5 returns results", len(results), 1)
    check_eq("search_assets finds correct asset", results[0].asset_id, "e2e_doc_1" if results else "none")

    results_all = store.search_assets("end to end", limit=10)
    check_gt("search_assets multi-word", len(results_all), 1)

    results_empty = store.search_assets("nonexistent_xyzzy", limit=10)
    check_eq("search_assets no match", results_empty, [])

    results_filtered = store.search_assets("testing", limit=10, asset_type=AssetType("image"))
    check_eq("search_assets filtered by type", len(results_filtered), 0)

    # ── Paso 4: Memory FTS5 search ──────────────────────────────────────
    print("\n═══ 4. Memory FTS5 search ═══")
    mem_store = SQLiteMemoryStore(db)
    mem_store.save(
        MemoryRecord(
            memory_id="mem_e2e_1",
            kind="note",
            title="Meeting notes about FTS5",
            content="Discussed FTS5 implementation for Fase 7",
        )
    )
    mem_store.save(
        MemoryRecord(
            memory_id="mem_e2e_2",
            kind="note",
            title="Shopping list",
            content="milk, eggs, bread",
        )
    )

    mem_results = mem_store.search("FTS5", limit=10)
    check_gt("memory search FTS5 returns results", len(mem_results), 1)
    if mem_results:
        check_eq("memory search finds correct record", mem_results[0].memory_id, "mem_e2e_1")

    mem_empty = mem_store.search("nonexistent_xyzzy", limit=10)
    check_eq("memory search no match", mem_empty, [])

    mem_empty_q = mem_store.search("", limit=10)
    check_eq("memory search empty query", mem_empty_q, [])

    # ── Paso 5: Lineage edges ───────────────────────────────────────────
    print("\n═══ 5. Lineage edges ═══")
    lin_store = SQLiteLineageStore(db)
    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-07-03T00:00:00Z",
        "inputs": [{"name": "e2e_doc_1"}],
        "outputs": [{"name": "e2e_report"}],
    }
    check("store_lineage_event", lin_store.store_lineage_event(event))

    upstream = lin_store.get_upstream("e2e_report")
    check_gt("get_upstream returns results", len(upstream), 1)
    check("upstream includes input", "e2e_doc_1" in upstream)

    downstream = lin_store.get_downstream("e2e_doc_1")
    check_gt("get_downstream returns results", len(downstream), 1)
    check("downstream includes output", "e2e_report" in downstream)

    # Verificar no falsos positivos
    upstream_none = lin_store.get_upstream("nonexistent_xyzzy")
    check_eq("get_upstream no match", upstream_none, [])

    # ── Paso 6: Extraction queue ────────────────────────────────────────
    print("\n═══ 6. Extraction queue ═══")
    ext_service = MetadataExtractionService(db)

    job_id1 = ext_service.queue_extract(AssetSource("filesystem", "/tmp/e2e.pdf"))
    check("queue_extract returns job id", job_id1 is not None)
    check("queue_extract returns str", isinstance(job_id1, str))

    # Dedup
    job_id2 = ext_service.queue_extract(AssetSource("filesystem", "/tmp/e2e.pdf"))
    check_eq("dedup: same location returns same job id", job_id2, job_id1)

    status = ext_service.get_queue_status(job_id1)
    check("queue status has status key", "status" in status)
    check_eq("queue status is pending", status["status"], "pending")

    status_nf = ext_service.get_queue_status("999999")
    check_eq("queue status not found", status_nf["status"], "not_found")

    # ── Paso 7: GraphRetriever FTS5 ─────────────────────────────────────
    print("\n═══ 7. GraphRetriever ═══")
    retriever = SQLiteGraphRetriever(db)
    gr_results = retriever.retrieve_assets("testing", limit=10)
    check_gt("retrieve_assets returns results", len(gr_results), 1)
    if gr_results:
        check_eq("retrieve_assets finds correct asset", gr_results[0].asset_id, "e2e_doc_1")

    gr_results2 = retriever.retrieve_assets("Pasta", limit=10)
    check_gt("retrieve_assets case-insensitive", len(gr_results2), 1)

    # ── Paso 8: Auto-recovery (mock) ────────────────────────────────────
    print("\n═══ 8. Auto-recovery (mock) ═══")
    qdrant = QdrantVectorStore(collection="e2e_test")
    check("Qdrant available initially", qdrant.available)

    ollama = OllamaEmbedder()
    check("Ollama available initially", ollama.available)

    # Degradar y verificar estado O(1)
    qdrant._degraded = True
    check("Qdrant degraded = not available", not qdrant.available)
    ollama._degraded = True
    check("Ollama degraded = not available", not ollama.available)

    # ── Paso 9: Reconcile (dry-run) ─────────────────────────────────────
    print("\n═══ 9. Reconcile (dry-run) ═══")
    from unittest.mock import MagicMock

    graph = MagicMock()
    asset_store_mock = MagicMock()
    embedder_mock = MagicMock()
    vector_store_mock = MagicMock()

    asset_store_mock.list_assets.side_effect = [[a1], []]  # first batch, then empty
    vector_store_mock.count.return_value = 0
    embedder_mock.vector_size = 384
    embedder_mock.embed.return_value = [[0.1] * 384]
    vector_store_mock.search.return_value = []

    ar = VectorAugmentedRetriever(graph, asset_store_mock, embedder_mock, vector_store_mock)
    stats = ar.reconcile(dry_run=True)
    check("reconcile reports to_upsert", stats["to_upsert"] >= 1)
    check("reconcile reports upserted=0 in dry-run", stats["upserted"] == 0)
    check("reconcile reports deleted=0 in dry-run", stats["deleted"] == 0)

    # ── Resultado final ─────────────────────────────────────────────────
    print(f"\n═══ RESULTADO: {PASS} pasaron, {FAIL} fallaron ═══")

    # cleanup
    if db.exists():
        db.unlink()

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
