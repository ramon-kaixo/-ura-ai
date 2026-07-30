"""Integration tests: Knowledge DB → RuleEvaluator (SQLite temp real).
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from knowledge.engine.rules import RuleEvaluator, _BUILTIN_RULES


def _create_db(
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
) -> Path:
    """Create a temp knowledge.db with kg_nodes + kg_edges tables and seed data."""
    fp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = Path(fp.name)
    fp.close()

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id             TEXT PRIMARY KEY,
            type           TEXT NOT NULL,
            path           TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            frontmatter    TEXT NOT NULL,
            body           TEXT NOT NULL DEFAULT '',
            semantic       TEXT,
            quality        REAL,
            confidence     REAL,
            embed_hash     TEXT,
            updated_at     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kg_edges (
            src      TEXT NOT NULL,
            dst      TEXT NOT NULL,
            relation TEXT NOT NULL,
            metadata TEXT,
            PRIMARY KEY (src, dst, relation)
        );
        CREATE TABLE IF NOT EXISTS kg_active_version (
            singleton         INTEGER PRIMARY KEY CHECK (singleton = 1),
            graph_version     INTEGER NOT NULL,
            source_commit     TEXT NOT NULL,
            compiler_version  TEXT NOT NULL,
            qdrant_collection TEXT NOT NULL DEFAULT '',
            swapped_at        TEXT NOT NULL,
            determinism_hash  TEXT NOT NULL DEFAULT '',
            determinism_algorithm TEXT NOT NULL DEFAULT 'sha256-v1'
        );
    """)

    for n in (nodes or []):
        conn.execute(
            "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, body, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                n["id"],
                n.get("type", "doc"),
                n.get("path", f"/{n['id']}.md"),
                n.get("content_sha256", "0" * 64),
                json.dumps(n.get("frontmatter", {})),
                n.get("body", ""),
            ),
        )

    for e in (edges or []):
        conn.execute(
            "INSERT INTO kg_edges (src, dst, relation) VALUES (?, ?, ?)",
            (e["src"], e["dst"], e.get("relation", "references")),
        )

    conn.commit()
    conn.close()
    return path


def _run_rules(db_path: Path) -> list:
    """Replicate the exact pipeline logic: SQL → RuleEvaluator."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, type, path, frontmatter, body FROM kg_nodes").fetchall()
    edges = conn.execute("SELECT src, dst FROM kg_edges").fetchall()
    conn.close()

    all_node_ids = {r["id"] for r in rows}
    all_relation_targets = {e["dst"] for e in edges}

    documents = []
    for r in rows:
        fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
        documents.append({
            "id": r["id"],
            "path": r["path"],
            "type": r["type"],
            "title": fm.get("title", ""),
            "tags": fm.get("tags", []),
            "body": r["body"] or "",
            "relations": [e["dst"] for e in edges if e["src"] == r["id"]],
        })

    evaluator = RuleEvaluator()
    return evaluator.evaluate(documents, all_node_ids, all_relation_targets)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRulesIntegration:
    def test_empty_db(self) -> None:
        db_path = _create_db()
        findings = _run_rules(db_path)
        assert len(findings) == 0
        db_path.unlink()

    def test_doc_no_title(self) -> None:
        db_path = _create_db(nodes=[{"id": "d1", "frontmatter": {}}])
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert "R001" in rule_ids
        db_path.unlink()

    def test_doc_no_tags(self) -> None:
        db_path = _create_db(nodes=[{"id": "d1", "frontmatter": {"title": "X"}}])
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert "R002" in rule_ids
        db_path.unlink()

    def test_doc_empty_body(self) -> None:
        db_path = _create_db(nodes=[{"id": "d1", "frontmatter": {"title": "X", "tags": ["a"]}, "body": ""}])
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert "R003" in rule_ids
        db_path.unlink()

    def test_relation_to_nonexistent(self) -> None:
        db_path = _create_db(
            nodes=[{"id": "d1", "frontmatter": {"title": "T", "tags": ["a"]}, "body": "hello"}],
            edges=[{"src": "d1", "dst": "ghost"}],
        )
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert "R004" in rule_ids
        db_path.unlink()

    def test_orphan_no_relations(self) -> None:
        """No outgoing edges and id not in any edge dst → orphan."""
        db_path = _create_db(nodes=[{"id": "orphan", "frontmatter": {"title": "O", "tags": ["x"]}, "body": "body"}])
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert "R005" in rule_ids
        db_path.unlink()

    def test_mixed_rules(self) -> None:
        """5 docs, each triggering a different rule."""
        nodes = [
            {"id": "no-title", "frontmatter": {}},
            {"id": "no-tags", "frontmatter": {"title": "T"}},
            {"id": "no-body", "frontmatter": {"title": "T", "tags": ["a"]}, "body": ""},
            {"id": "source", "frontmatter": {"title": "T", "tags": ["a"]}, "body": "ok"},
            {"id": "orphan", "frontmatter": {"title": "O", "tags": ["x"]}, "body": "body"},
        ]
        edges = [{"src": "source", "dst": "ghost"}]
        db_path = _create_db(nodes=nodes, edges=edges)
        findings = _run_rules(db_path)
        rule_ids = {f.rule_id for f in findings}
        assert rule_ids == {"R001", "R002", "R003", "R004", "R005"}
        db_path.unlink()

    def test_all_clean_no_findings(self) -> None:
        """A perfect document triggers no rules.
        Needs an incoming relation to avoid R005 (orphan)."""
        db_path = _create_db(
            nodes=[{
                "id": "perfect",
                "frontmatter": {"title": "Perfect", "tags": ["clean"]},
                "body": "This document has everything it needs.",
            }],
            edges=[{"src": "some-parent", "dst": "perfect"}],
        )
        findings = _run_rules(db_path)
        assert len(findings) == 0
        db_path.unlink()
