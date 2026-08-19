"""Tests de cobertura para knowledge/engine/graphrag.py."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from knowledge.engine.asset_store import SQLiteAssetStore
from knowledge.engine.governance_store import SQLiteGovernanceStore
from knowledge.engine.graphrag import (
    ContextBundle,
    RetrievalResult,
    SQLiteGraphRetriever,
    _compute_score,
    _serializar_assets,
    _serializar_memorias,
)
from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset
from knowledge.engine.sqlite_writer import init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


def _mk_db(tmp_path: Path) -> Path:
    db = tmp_path / "g.db"
    init_db(db, SCHEMA)
    return db


def _mk_retriever(tmp_path: Path) -> tuple[SQLiteGraphRetriever, Path]:
    db = _mk_db(tmp_path)
    return SQLiteGraphRetriever(db), db


def _seed_assets(db: Path) -> None:
    store = SQLiteAssetStore(db)
    for aid, title, q in (("a1", "GraphRAG motor", 0.9), ("a2", "Memoria episódica", 0.7), ("a3", "Otro", 0.4)):
        store.save_asset(
            KnowledgeAsset(
                asset_id=aid,
                asset_type=AssetType.MARKDOWN,
                metadata={"title": title},
                source=AssetSource(kind="file", location="docs/x.md"),
                quality=q,
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )


def _seed_memory(db: Path) -> None:
    store = SQLiteMemoryStore(db)
    store.save(
        MemoryRecord(
            memory_id="m1",
            kind="learning",
            title="Lección GraphRAG",
            content="El contexto se recupera de los stores.",
            related_assets=("a1",),
            tags=("graphrag",),
        )
    )


def _seed_lineage(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES ('a1', 'a2', 'relates_to', '2026-08-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO op_lineage (id, event_type, event_time, run_id, job_name, namespace, input_ids, output_ids, metadata) "
        "VALUES (1, 'compile', '2026-08-01T00:00:00Z', 1, 'job', 'ns', '[\"a1\"]', '[]', '{}')"
    )
    conn.commit()
    conn.close()


def _seed_governance(db: Path) -> None:
    store = SQLiteGovernanceStore(db)
    store.set_policy("a1", {"policy": "retention-30d"})


# ── ContextBundle ───────────────────────────────────────────────────────────


def test_context_bundle_to_dict() -> None:
    b = ContextBundle(
        query="q",
        assets=[{"x": 1}],
        memories=[],
        lineage=[],
        governance=[],
        neighbors=[],
        total_duration_ms=1.5,
        asset_count=1,
        memory_count=0,
        lineage_count=0,
        governance_count=0,
        neighbor_count=0,
    )
    d = b.to_dict()
    assert d["query"] == "q"
    assert d["stats"] == {
        "assets": 1,
        "memories": 0,
        "lineage": 0,
        "governance": 0,
        "neighbors": 0,
        "duration_ms": 1.5,
    }
    assert ContextBundle(query="q").to_dict()["stats"]["assets"] == 0


# ── _compute_score ──────────────────────────────────────────────────────────


def test_compute_score_asset_title_match() -> None:
    a = KnowledgeAsset(
        asset_id="a",
        asset_type=AssetType.MARKDOWN,
        metadata={"title": "GraphRAG motor"},
        quality=0.9,
        updated_at=datetime.now(UTC).isoformat(),
    )
    s = _compute_score("graphrag", asset=a, max_days=365)
    assert 0.4 <= s <= 1.0
    s2 = _compute_score("zzz", asset=a)
    assert s2 < s


def test_compute_score_recency_invalida() -> None:
    a = KnowledgeAsset(
        asset_id="a",
        asset_type=AssetType.MARKDOWN,
        metadata={"title": "x"},
        quality=0.5,
        updated_at="no-es-fecha",
    )
    assert _compute_score("x", asset=a) >= 0.15


def test_compute_score_memory_y_vacio() -> None:
    mem = MemoryRecord(memory_id="m", kind="note", title="Nota GraphRAG", content="c", tags=(), related_assets=())
    s = _compute_score("graphrag", memory=mem)
    assert s > 0
    assert _compute_score("", None, None) >= 0.075


def test_compute_score_asset_viejo() -> None:
    a = KnowledgeAsset(
        asset_id="a",
        asset_type=AssetType.MARKDOWN,
        metadata={"title": "viejo"},
        quality=0.5,
        updated_at=(datetime.now(UTC) - timedelta(days=1000)).isoformat(),
    )
    s = _compute_score("viejo", asset=a, max_days=365)
    assert s == 0.4 + 0.075


# ── SQLiteGraphRetriever E2E ────────────────────────────────────────────────


def test_retrieve_assets(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    assert r.retrieve_assets("") == []
    _seed_assets(db)
    results = r.retrieve_assets("graphrag", limit=5)
    assert results[0].asset_id == "a1"
    assert results[0].score > 0
    assert results[0].kind == "markdown"
    assert r._get_asset_store() is r._get_asset_store()


def test_retrieve_assets_con_tipo(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_assets(db)
    results = r.retrieve_assets("motor", limit=5, asset_type=AssetType.MARKDOWN)
    assert len(results) >= 1
    assert all(x.asset_id in {"a1", "a2", "a3"} for x in results)


def test_retrieve_memory(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    assert r.retrieve_memory("nada") == []
    _seed_memory(db)
    results = r.retrieve_memory("graphrag", limit=5)
    assert results[0].asset_id == "m1"
    assert results[0].kind == "learning"
    assert results[0].metadata["tags"] == ["graphrag"]
    assert r._get_memory_store() is r._get_memory_store()


def test_retrieve_memory_con_kind(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_memory(db)
    assert r.retrieve_memory("graphrag", kind="conversation") == []
    assert len(r.retrieve_memory("graphrag", kind="learning")) == 1


def test_retrieve_lineage(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_lineage(db)
    out = r.retrieve_lineage("a1")
    assert out[0]["upstream"] == []
    assert out[0]["events"] == 1
    assert r._get_lineage_store() is r._get_lineage_store()


def test_retrieve_governance(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_governance(db)
    out = r.retrieve_governance("a1")
    assert "retention-30d" in out[0]["policy"]
    assert r._get_governance_store() is r._get_governance_store()


def test_retrieve_neighbors_bfs(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    conn = sqlite3.connect(db)
    for s, d in (("a1", "a2"), ("a2", "a3"), ("a1", "a4")):
        conn.execute("INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES (?, ?, 'r', '2026-08-01T00:00:00Z')", (s, d))
    conn.commit()
    conn.close()
    out = r.retrieve_neighbors("a1", depth=1)
    assert {n["asset_id"] for n in out} == {"a2", "a4"}
    out2 = r.retrieve_neighbors("a1", depth=2)
    assert {n["asset_id"] for n in out2} == {"a2", "a3", "a4"}
    conn = sqlite3.connect(db)
    conn.execute("INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES ('a9', 'a1', 'r', '2026-08-01T00:00:00Z')")
    conn.execute("INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES ('a8', 'a1', 'r', '2026-08-01T00:00:00Z')")
    conn.commit()
    conn.close()
    assert len(r.retrieve_neighbors("a1", depth=1, max_nodes=1)) == 2


def test_retrieve_neighbors_ciclo(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES ('a1', 'a2', 'r', '2026-08-01T00:00:00Z')")
    conn.execute("INSERT OR REPLACE INTO op_lineage_edges (src, dst, relation, created_at) VALUES ('a2', 'a1', 'r', '2026-08-01T00:00:00Z')")
    conn.commit()
    conn.close()
    out = r.retrieve_neighbors("a1", depth=3)
    assert {n["asset_id"] for n in out} == {"a2"}


# ── build_context ───────────────────────────────────────────────────────────


def test_build_context_completo(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_assets(db)
    _seed_memory(db)
    _seed_lineage(db)
    _seed_governance(db)
    b = r.build_context("graphrag", max_assets=5, max_memories=5, neighbor_depth=1)
    assert b.asset_count == 1
    assert b.assets[0]["asset_id"] == "a1"
    assert b.memory_count == 1
    assert b.lineage_count == 1
    assert b.governance_count == 1
    assert b.neighbor_count == 1
    assert b.total_duration_ms >= 0


def test_build_context_sin_grafo(tmp_path) -> None:
    r, db = _mk_retriever(tmp_path)
    _seed_assets(db)
    b = r.build_context("graphrag", max_assets=5, max_memories=5, include_lineage=False, include_governance=False, neighbor_depth=0)
    assert b.asset_count == 1
    assert b.lineage_count == 0
    assert b.governance_count == 0
    assert b.neighbor_count == 0


# ── serializadores ──────────────────────────────────────────────────────────


def test_serializar() -> None:
    rr = RetrievalResult(asset_id="a", score=0.9, title="t", kind="doc", snippet="s")
    assets = _serializar_assets([rr])
    assert assets[0] == {"asset_id": "a", "score": 0.9, "title": "t", "kind": "doc", "snippet": "s"}
    mems = _serializar_memorias([rr])
    assert mems[0]["memory_id"] == "a"
    assert mems[0]["metadata"] == {}
    assert _serializar_assets([]) == []
    assert _serializar_memorias([]) == []
    assert RetrievalResult(asset_id="a", score=0.0).metadata == {}
