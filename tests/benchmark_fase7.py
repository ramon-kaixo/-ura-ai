"""Benchmark comparativo Fase 7 — §14.3 del diseño.

Mide latencias de APIs públicas Fase 7 contra targets del diseño.
USO: python3 tests/benchmark_fase7.py [--verbose]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Añadir raíz del proyecto al path para importar módulos knowledge
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from knowledge.engine.asset_store import SQLiteAssetStore
from knowledge.engine.connection import open_db
from knowledge.engine.lineage_store import SQLiteLineageStore
from knowledge.engine.memory_store import SQLiteMemoryStore
from knowledge.engine.ontology.internal import AssetSource, AssetType
from knowledge.engine.models import KnowledgeAsset
from knowledge.engine.sqlite_writer import init_db

VERBOSE = "--verbose" in sys.argv

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"

_ASSET_TITLES = [
    "Machine Learning Fundamentals",
    "Deep Learning with PyTorch",
    "Neural Networks for NLP",
    "Reinforcement Learning Algorithms",
    "Computer Vision in Practice",
    "Natural Language Processing with Transformers",
    "Introduction to Data Science",
    "Advanced Statistics for Engineers",
    "Probability and Random Processes",
    "Linear Algebra for Machine Learning",
]
_MEMORY_TITLES = [
    "Meeting notes: Project kickoff",
    "Research summary: Attention mechanisms",
    "Code review feedback for PR #42",
    "Architecture decision: Vector store choice",
    "Bug report: FTS5 search returns duplicates",
    "Performance analysis: Batch insert timing",
    "Integration test results for Qdrant",
    "Security review: SQL injection vectors",
    "Deployment checklist for v0.5.0",
    "Retrospective: Fase 6 closure",
]


def _make_asset(asset_id: str, title: str) -> KnowledgeAsset:
    return KnowledgeAsset(
        asset_id=asset_id,
        asset_type=AssetType("pdf"),
        metadata={
            "title": title,
            "text_preview": f"This is the body of {title}. It contains relevant terms for searching.",
        },
        source=AssetSource(kind="benchmark", location=f"/bench/{asset_id}"),
        relationships=(),
        quality=1.0,
        created_at="2026-07-03T00:00:00Z",
        updated_at="2026-07-03T00:00:00Z",
    )


def _make_memory_tuple(memory_id: str, title: str) -> tuple:
    return (memory_id, "note", title, f"Content about {title}", "[]", "[]", "{}",
            "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z")


class Benchmark:
    def __init__(self) -> None:
        self.results: dict[str, float] = {}
        self.db_dir = Path("/tmp/bench_fase7")
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup()

    def _cleanup(self) -> None:
        for f in self.db_dir.glob("*.db"):
            f.unlink(missing_ok=True)

    def _db_path(self, name: str) -> Path:
        return self.db_dir / f"{name}.db"

    def _populate_assets_sql(self, db: Path, count: int) -> None:
        conn = open_db(db)
        for i in range(count):
            title = _ASSET_TITLES[i % len(_ASSET_TITLES)] + f" v{i}"
            meta = json.dumps({
                "title": title,
                "text_preview": f"This is the body of {title}. It contains relevant terms for searching.",
            })
            conn.execute(
                "INSERT OR IGNORE INTO op_assets "
                "(id, asset_type, metadata, source, quality, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"asset_{i}", "pdf", meta,
                 json.dumps({"kind": "benchmark", "location": f"/bench/asset_{i}"}),
                 1.0, "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z"),
            )
        conn.commit()
        conn.close()

    def _setup_fts5_db(self, name: str, count: int) -> SQLiteAssetStore:
        """Crea DB v14 con N assets. Retorna store listo para consultas."""
        db = self._db_path(name)
        init_db(db, _SCHEMA_PATH)
        self._populate_assets_sql(db, count)
        return SQLiteAssetStore(db)

    def _setup_like_db(self, name: str, count: int) -> SQLiteAssetStore:
        """Crea DB sin FTS5 (v13 base) para medir fallback LIKE."""
        db = self._db_path(name)
        conn = open_db(db)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS op_assets (
                id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',
                relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,
                content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT
            );
        """)
        conn.close()
        self._populate_assets_sql(db, count)
        return SQLiteAssetStore(db)

    def _setup_memory_db(self, name: str) -> SQLiteMemoryStore:
        """Crea DB v14 con 10 memory records. Retorna store."""
        db = self._db_path(name)
        init_db(db, _SCHEMA_PATH)
        conn = open_db(db)
        for i, title in enumerate(_MEMORY_TITLES):
            conn.execute(
                "INSERT INTO op_memory "
                "(memory_id, kind, title, content, related_assets, tags, metadata, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _make_memory_tuple(f"mem_{i}", title),
            )
        conn.commit()
        conn.close()
        return SQLiteMemoryStore(db)

    def _setup_lineage_db(self, name: str) -> SQLiteLineageStore:
        """Crea DB v14 con 10 lineage events y edges. Retorna store."""
        db = self._db_path(name)
        init_db(db, _SCHEMA_PATH)
        conn = open_db(db)
        for i in range(10):
            conn.execute(
                "INSERT INTO op_lineage "
                "(event_type, event_time, input_ids, output_ids) "
                "VALUES ('COMPLETE', datetime('now'), ?, ?)",
                (json.dumps([f"input_{i}"]), json.dumps([f"output_{i}"])),
            )
            eid = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
            conn.execute(
                "INSERT INTO op_lineage_edges (src, dst, relation, event_id, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (f"input_{i}", f"output_{i}", "DERIVED_FROM", eid),
            )
        conn.commit()
        conn.close()
        return SQLiteLineageStore(db)

    def _setup_migration_db(self, name: str) -> Path:
        """Crea DB v13 (sin FTS5, sin lineage_edges, sin result_data) con 10 assets."""
        db = self._db_path(name)
        conn = open_db(db)
        conn.executescript("""
            DROP TABLE IF EXISTS op_assets;
            DROP TABLE IF EXISTS op_memory;
            DROP TABLE IF EXISTS op_lineage;
            DROP TABLE IF EXISTS op_jobs;
            CREATE TABLE op_assets (
                id TEXT PRIMARY KEY, asset_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT '{}',
                relationships TEXT NOT NULL DEFAULT '[]', quality REAL NOT NULL DEFAULT 0.0,
                content_sha256 TEXT, wraps TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE op_memory (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
                related_assets TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT, updated_at TEXT
            );
            CREATE TABLE op_lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, event_time TEXT NOT NULL,
                run_id TEXT, job_name TEXT, namespace TEXT,
                input_ids TEXT NOT NULL DEFAULT '[]',
                output_ids TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL, priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', payload TEXT, dedup_key TEXT,
                created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                error TEXT
            );
            PRAGMA user_version = 13;
        """)
        for i in range(10):
            title = _ASSET_TITLES[i % len(_ASSET_TITLES)]
            conn.execute(
                "INSERT INTO op_assets (id, asset_type, metadata, source, quality, created_at, updated_at) "
                "VALUES (?, ?, ?, '{}', 1.0, datetime('now'), datetime('now'))",
                (f"asset_{i}", "pdf",
                 json.dumps({"title": title, "text_preview": f"body {i}"})),
            )
        conn.commit()
        conn.close()
        return db

    def measure(self, label: str, fn, *, target: float | None = None) -> float:
        elapsed = fn()
        self.results[label] = elapsed
        status = "✅" if target is None or elapsed <= target else "❌"
        target_str = f"  (target: <{target*1000:.0f}ms)" if target else ""
        print(f"  {status} {label}: {elapsed*1000:.1f}ms{target_str}")
        return elapsed

    def run(self) -> bool:
        all_pass = True

        # ── 1. FTS5 search (1 asset) ──────────────────────────────────────
        print("\n📊 FTS5 search (1 asset) — target <10ms")
        store = self._setup_fts5_db("fts5_1", 1)
        def _fts5_1():
            return len(store.search_assets("Machine"))
        self.measure("FTS5 1 asset", lambda: _timeit(_fts5_1, 100), target=0.010)
        self.db_dir.joinpath("fts5_1.db").unlink(missing_ok=True)

        # ── 2. FTS5 search (1000 assets) ──────────────────────────────────
        print("\n📊 FTS5 search (1000 assets) — target <50ms")
        store = self._setup_fts5_db("fts5_1000", 1000)
        def _fts5_1000():
            return len(store.search_assets("Learning"))
        result = self.measure("FTS5 1000 assets", lambda: _timeit(_fts5_1000, 20), target=0.050)
        if result > 0.050:
            all_pass = False
            print(f"    ⚠  {result*1000:.1f}ms excede target de 50ms")
        self.db_dir.joinpath("fts5_1000.db").unlink(missing_ok=True)

        # ── 3. LIKE search (1000 assets) — baseline comparison ────────────
        print("\n📊 LIKE search (1000 assets) — baseline (no target)")
        store = self._setup_like_db("like_1000", 1000)
        def _like_1000():
            return len(store.search_assets("Learning"))
        like_time = self.measure("LIKE 1000 assets", lambda: _timeit(_like_1000, 20))
        print(f"    → FTS5 es {like_time/self.results.get('FTS5 1000 assets', 1):.1f}x más rápido")
        self.db_dir.joinpath("like_1000.db").unlink(missing_ok=True)

        # ── 4. Memory FTS5 search (10 records) ────────────────────────────
        print("\n📊 Memory FTS5 search (10 records) — target <10ms")
        mem_store = self._setup_memory_db("memory")
        def _mem_fts():
            return len(mem_store.search("Meeting"))
        self.measure("FTS5 memory 10 records", lambda: _timeit(_mem_fts, 100), target=0.010)
        self.db_dir.joinpath("memory.db").unlink(missing_ok=True)

        # ── 5. Lineage edge lookup (10 assets) ────────────────────────────
        print("\n📊 Lineage edge lookup (10 assets) — target <5ms")
        lin_store = self._setup_lineage_db("lineage")
        def _edge_lookup():
            return lin_store.get_upstream("output_5")
        self.measure("Lineage edge lookup",
                     lambda: _timeit(_edge_lookup, 1000), target=0.005)
        self.db_dir.joinpath("lineage.db").unlink(missing_ok=True)

        # ── 6. Migration v13→v14 ──────────────────────────────────────────
        print("\n📊 Migration v13→v14 — target <100ms")
        db = self._setup_migration_db("migration")
        def _run_migration():
            init_db(db, _SCHEMA_PATH)
        self.measure("Migration v13→v14", lambda: _timeit(_run_migration, 1), target=0.100)
        self.db_dir.joinpath("migration.db").unlink(missing_ok=True)

        # ── 7. E2E (2 docs) ──────────────────────────────────────────────
        print("\n📊 E2E (2 docs) — target <2.0s")
        db = self._db_path("e2e")
        init_db(db, _SCHEMA_PATH)
        store = SQLiteAssetStore(db)
        asset1 = _make_asset("e2e_0", _ASSET_TITLES[0])
        asset2 = _make_asset("e2e_1", _ASSET_TITLES[1])
        def _e2e():
            store.save_asset(asset1)
            store.save_asset(asset2)
            return len(store.search_assets('"Machine" OR "Deep"'))
        self.measure("E2E Fase 7 (2 docs)", lambda: _timeit(_e2e, 1), target=2.000)
        self.db_dir.joinpath("e2e.db").unlink(missing_ok=True)

        # ── Summary ───────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("RESUMEN BENCHMARK FASE 7")
        print("=" * 60)
        for label, elapsed in self.results.items():
            print(f"  {label}: {elapsed*1000:.1f}ms")

        targets = {
            "FTS5 1 asset": 0.010,
            "FTS5 1000 assets": 0.050,
            "FTS5 memory 10 records": 0.010,
            "Lineage edge lookup": 0.005,
            "Migration v13→v14": 0.100,
            "E2E Fase 7 (2 docs)": 2.000,
        }
        passes = 0
        fails = 0
        for label, target in targets.items():
            actual = self.results.get(label, float("inf"))
            if actual <= target:
                passes += 1
                print(f"  ✅ PASS: {label} ({actual*1000:.1f}ms ≤ {target*1000:.0f}ms)")
            else:
                fails += 1
                print(f"  ❌ FAIL: {label} ({actual*1000:.1f}ms > {target*1000:.0f}ms)")
                all_pass = False

        print(f"\nResultado: {passes}/{passes + fails} targets cumplidos")
        print(f"LIKE baseline (1000 assets): {self.results.get('LIKE 1000 assets', 0)*1000:.1f}ms")
        return all_pass


def _timeit(fn, iterations: int = 1) -> float:
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    end = time.perf_counter()
    return (end - start) / max(iterations, 1)


if __name__ == "__main__":
    b = Benchmark()
    success = b.run()
    sys.exit(0 if success else 1)
