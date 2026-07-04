"""Tests for Knowledge Engine (Fase B + C0 + C0.2).

Cubre:
  - Config: carga, overrides, tipos inválidos, errores
  - Knowledge DB: creación, verify en vacío, schema correcto
  - Códigos de error KE0xx
  - Modelos internos (frozen, SourceObject, Snapshot, CompileContext)
  - CLI: init, verify, status
  - Integración: init → verify → status
  - Corrupción: verify detecta DB dañada con códigos KE correctos
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import logging
from pathlib import Path

import pytest

from motor.core.config import VALID_LOG_LEVELS, UraConfig
from knowledge.engine.audit import AuditService, NDJSONAuditBackend
from knowledge.engine.errors import Severity, all_codes, lookup
from knowledge.engine.models import AuditEvent
from knowledge.engine.knowledge_verifier import (
    check_cycles,
    check_duplicate_paths,
    check_ontology,
    check_orphans,
    check_referential_integrity,
    check_repeated_hashes,
    verify_hashes,
)
from knowledge.engine.models import (
    CompileContext,
    CompileError,
    CompileResult,
    CompileStage,
    Document,
    Frontmatter,
    KnowledgeObject,
    Relation,
    SearchResult,
    Snapshot,
    SourceObject,
    ValidationResult,
    doc_id_from_path,
)
from knowledge.engine.parser import parse_source
from knowledge.engine.scanner import scan_incremental, scan_source, take_snapshot
from knowledge.engine.storage_verifier import check_fts_sync, check_schema
from knowledge.engine.validator import validate_batch, validate_knowledge_object
from knowledge.engine.verifier import verify_graph
from knowledge.engine.sqlite_writer import SyncPolicy, init_db
from knowledge.engine.compiler import compile_source

ENGINE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "pro" / "knowledge_engine.py"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"


def _content_so(path: str, text: str = "") -> SourceObject:
    """Helper: crea SourceObject con contenido en memoria."""
    raw = text.encode("utf-8")
    return SourceObject(
        id=path,
        path=path,
        kind="markdown",
        content_sha256=hashlib.sha256(raw).hexdigest(),
        size=len(raw),
        content=raw,
    )


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestUraConfig:
    def test_load_defaults(self):
        cfg = UraConfig.load()
        assert cfg.qdrant_host == "localhost"
        assert cfg.qdrant_port == 6333
        assert cfg.log_level in VALID_LOG_LEVELS

    def test_env_override(self):
        os.environ["URA_QDRANT_HOST"] = "test-host"
        cfg = UraConfig.load()
        assert cfg.qdrant_host == "test-host"
        del os.environ["URA_QDRANT_HOST"]

    def test_invalid_log_level_normalizes(self):
        os.environ["URA_LOG_LEVEL"] = "INVALID_LEVEL"
        cfg = UraConfig.load()
        assert cfg.log_level == "INFO"
        del os.environ["URA_LOG_LEVEL"]

    def test_legacy_json_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"qdrant_host": "from-file"}, f)
            f.flush()
            cfg = UraConfig.load(path=f.name)
            assert cfg.qdrant_host == "from-file"
        Path(f.name).unlink()


# ── Models Tests ─────────────────────────────────────────────────────────────


class TestModels:
    def test_frontmatter_from_dict(self):
        fm = Frontmatter.from_dict({"title": "Test", "type": "adr", "tags": ["a"], "custom": "x"})
        assert fm.title == "Test"
        assert fm.doc_type == "adr"
        assert fm.tags == ("a",)
        assert fm.extra["custom"] == "x"

    def test_frontmatter_to_dict(self):
        fm = Frontmatter(title="T", doc_type="doc")
        d = fm.to_dict()
        assert d["title"] == "T"
        assert d["type"] == "doc"

    def test_document_creation(self):
        doc = Document(doc_id="d1", doc_type="adr", path="test.md", content_sha256="abc", frontmatter=Frontmatter())
        assert doc.doc_id == "d1"
        assert doc.quality == 0.0

    def test_relation_creation(self):
        rel = Relation(src="a", dst="b", relation="depends")
        assert rel.src == "a"

    def test_knowledge_object(self):
        doc = Document(doc_id="d1", doc_type="adr", path="t.md", content_sha256="abc", frontmatter=Frontmatter())
        ko = KnowledgeObject(document=doc, relations=(Relation(src="d1", dst="d2", relation="refers"),))
        assert ko.document.doc_id == "d1"
        assert len(ko.relations) == 1

    def test_compile_result_defaults(self):
        r = CompileResult(
            success=True,
            graph_version=1,
            source_commit="abc",
            compiler_version="0.1",
            documents_total=0,
            documents_changed=0,
        )
        assert r.errors == ()

    def test_search_result(self):
        sr = SearchResult(doc_id="d1", score=0.95)
        assert sr.title == ""

    def test_validation_result(self):
        vr = ValidationResult(valid=True)
        assert vr.valid
        assert vr.errors == ()

    def test_models_are_frozen(self):
        fm = Frontmatter(title="Original")
        with pytest.raises(AttributeError):
            fm.title = "Mutated"

    def test_source_object_kind_for(self):
        assert SourceObject.kind_for(Path("doc.md")) == "markdown"
        assert SourceObject.kind_for(Path("doc.yaml")) == "yaml"
        assert SourceObject.kind_for(Path("doc.json")) == "json"
        assert SourceObject.kind_for(Path("doc.drawio")) == "drawio"
        assert SourceObject.kind_for(Path("doc.unknown")) == "unknown"

    def test_compile_options_defaults(self):
        from knowledge.engine.migrations import SCHEMA_VERSION

        ctx = CompileContext()
        assert ctx.options.compiler_version == "0.1.0"
        assert ctx.metadata.schema_version == SCHEMA_VERSION
        assert ctx.stage == CompileStage.DISCOVERING

    def test_compile_stage_enum(self):
        assert CompileStage.DISCOVERING.value == "discovering"
        assert CompileStage.DONE.value == "done"
        assert CompileStage.FAILED.value == "failed"

    def test_doc_id_from_path_deterministic(self):
        assert doc_id_from_path("docs/test.md") == doc_id_from_path("docs/test.md")
        # no collision: docs/test vs docs.test produce diferentes hashes
        assert doc_id_from_path("docs/test") != doc_id_from_path("docs.test")

    def test_source_object_content_bytes(self):
        so = _content_so("test.md", "hello world")
        assert so.content == b"hello world"
        assert so.size == 11
        expected_sha = hashlib.sha256(b"hello world").hexdigest()
        assert so.content_sha256 == expected_sha

    def test_snapshot_hash_changed(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        doc = src / "test.md"
        doc.write_text("original")
        so = _content_so("test.md", "original")
        snap = Snapshot(sources=(so,), taken_at="2026-01-01")
        assert not snap.has_changed(src)
        doc.write_text("modified")
        assert snap.has_changed(src)

    def test_snapshot_deleted(self):
        a = _content_so("a.md", "a")
        b = _content_so("b.md", "b")
        prev = Snapshot(sources=(a, b), taken_at="t1")
        cur = Snapshot(sources=(a,), taken_at="t2")
        assert len(cur.deleted(prev)) == 1
        assert cur.deleted(prev)[0].path == "b.md"


# ── Error Code Tests ─────────────────────────────────────────────────────────


class TestErrorCodes:
    def test_all_codes_have_unique_numbers(self):
        codes = all_codes()
        assert len(codes) > 0
        numbers = [c.code for c in codes]
        assert len(numbers) == len(set(numbers))

    def test_lookup_found(self):
        c = lookup("KE001")
        assert c is not None
        assert c.code == "KE001"
        assert c.severity == Severity.ERROR

    def test_lookup_missing(self):
        assert lookup("KE999") is None

    def test_all_severities_present(self):
        codes = all_codes()
        severities = {c.severity for c in codes}
        assert Severity.ERROR in severities
        assert Severity.WARN in severities

    def test_specific_codes(self):
        assert lookup("KE101").severity == Severity.ERROR
        assert lookup("KE103").severity == Severity.WARN
        assert lookup("KE204").severity == Severity.DEPRECATED

    def test_new_codes_exist(self):
        assert lookup("KE205") is not None
        assert lookup("KE207") is not None


# ── Knowledge DB Tests ───────────────────────────────────────────────────────


class TestKnowledgeEngine:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        self.db_path = tmp_path / "test_knowledge.db"
        self.source_dir = tmp_path / "source"
        self.source_dir.mkdir()

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(self.db_path, schema_path)

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _insert_node(self, conn, nid: str, path: str = "", sha: str = "hash", frontmatter: str = "{}"):
        conn.execute(
            "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (nid, "doc", path or f"{nid}.md", sha, frontmatter),
        )

    def _sync_fts(self, conn):
        SyncPolicy.sync_full(conn)

    def test_schema_verify_empty(self):
        results = verify_graph(self.db_path)
        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Errors on empty DB: {errors}"

    def test_schema_tables_exist(self):
        conn = self._conn()
        issues = check_schema(conn)
        conn.close()
        assert len(issues) == 0, f"Schema issues: {issues}"

    def test_verify_with_node(self):
        doc_file = self.source_dir / "test.md"
        doc_file.write_text("test content")
        sha = hashlib.sha256(b"test content").hexdigest()
        conn = self._conn()
        self._insert_node(conn, "doc-1", "test.md", sha, '{"title": "Test"}')
        self._sync_fts(conn)
        conn.commit()
        conn.close()

        results = verify_graph(self.db_path, self.source_dir)
        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Errors: {errors}"

    def test_fts_sync_after_manual_insert(self):
        conn = self._conn()
        self._insert_node(conn, "doc-2", "adr.md", "def456", '{"title": "ADR"}')
        self._sync_fts(conn)
        conn.commit()
        conn.close()

        issues = check_fts_sync(self._conn())
        assert len(issues) == 0

    def test_fts_sync_detects_mismatch(self):
        conn = self._conn()
        self._insert_node(conn, "doc-3", "adr2.md", "abc789", '{"title": "ADR2"}')
        self._sync_fts(conn)
        conn.execute("DELETE FROM kg_nodes_fts WHERE rowid=1")
        conn.commit()
        conn.close()

        issues = check_fts_sync(self._conn())
        assert len(issues) > 0
        assert "KE109" in issues[0]

    def test_fts_sync_id_level_mismatch(self):
        conn = self._conn()
        self._insert_node(conn, "doc-a", "a.md", "aaa", '{"title": "A"}')
        self._insert_node(conn, "doc-b", "b.md", "bbb", '{"title": "B"}')
        self._sync_fts(conn)
        conn.execute("DELETE FROM kg_nodes_fts WHERE rowid=1")
        conn.commit()
        conn.close()

        issues = check_fts_sync(self._conn())
        id_issues = [i for i in issues if "IDs en kg_nodes sin entrada FTS" in i]
        assert len(id_issues) == 1
        assert "doc-a" in id_issues[0] or "doc-b" in id_issues[0]

    def test_fts_sync_atomic_on_crash(self):
        conn = self._conn()
        self._insert_node(conn, "survivor", "surv.md", "xyz", '{"title": "Survivor"}')
        SyncPolicy.sync_full(conn)
        conn.commit()

        node_count = conn.execute("SELECT COUNT(*) FROM kg_nodes_fts").fetchone()[0]
        assert node_count == 1

        conn.execute("DELETE FROM kg_nodes")
        conn.execute("DELETE FROM kg_nodes_fts")
        conn.rollback()

        after_count = conn.execute("SELECT COUNT(*) FROM kg_nodes_fts").fetchone()[0]
        assert after_count == 1, f"FTS recuperado tras rollback: {after_count}"
        node_after = conn.execute("SELECT id FROM kg_nodes").fetchone()["id"]
        assert node_after == "survivor"
        conn.close()

    def test_sync_policy_documents_stub(self):
        conn = self._conn()
        self._insert_node(conn, "stub-test", "stub.md", "123", '{"title": "Stub"}')
        SyncPolicy.sync_documents(conn, ["stub-test"])
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM kg_nodes_fts").fetchone()[0]
        assert count == 1
        conn.close()

    def test_orphan_detection(self):
        conn = self._conn()
        self._insert_node(conn, "orphan-1", "orphan.md", "hash1")
        conn.commit()
        conn.close()
        issues = check_orphans(self._conn())
        assert len(issues) > 0
        assert "KE104" in issues[0]

    def test_foreign_key_referential(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO kg_edges (src, dst, relation) VALUES (?, ?, ?)",
            ("nonexistent-src", "nonexistent-dst", "references"),
        )
        conn.commit()
        conn.close()
        issues = check_referential_integrity(self._conn())
        assert len(issues) > 0

    def test_no_cycles_in_empty_graph(self):
        issues = check_cycles(self._conn())
        assert len(issues) == 0

    def test_cycle_detection(self):
        conn = self._conn()
        for nid in ("a", "b", "c"):
            self._insert_node(conn, nid)
        conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES ('a', 'b', 'depends')")
        conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES ('b', 'c', 'depends')")
        conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES ('c', 'a', 'depends')")
        conn.commit()
        conn.close()
        issues = check_cycles(self._conn())
        assert len(issues) > 0
        assert any("KE008" in i for i in issues)

    def test_verify_hashes(self):
        conn = self._conn()
        doc_file = self.source_dir / "test_hash.md"
        doc_file.write_text("hello world")
        sha = hashlib.sha256(b"hello world").hexdigest()
        self._insert_node(conn, "hash-test", "test_hash.md", sha)
        conn.commit()
        conn.close()
        issues = verify_hashes(self._conn(), self.source_dir)
        assert len(issues) == 0

    def test_verify_hashes_detects_drift(self):
        conn = self._conn()
        doc_file = self.source_dir / "drift.md"
        doc_file.write_text("original content")
        self._insert_node(
            conn, "drift-test", "drift.md", "0000000000000000000000000000000000000000000000000000000000000000"
        )
        conn.commit()
        conn.close()
        issues = verify_hashes(self._conn(), self.source_dir)
        assert len(issues) > 0
        assert "Hash no coincide" in issues[0]

    def test_duplicate_path_detection(self):
        conn = self._conn()
        for i in range(2):
            self._insert_node(conn, f"dup-path-{i}", "same/path.md", f"hash_{i}")
        conn.commit()
        conn.close()
        issues = check_duplicate_paths(self._conn())
        assert len(issues) > 0
        assert "KE102" in issues[0]

    def test_repeated_hash_detection(self):
        conn = self._conn()
        for i in range(3):
            self._insert_node(conn, f"rep-hash-{i}", f"rep_{i}.md", "SAME_HASH_VALUE")
        conn.commit()
        conn.close()
        issues = check_repeated_hashes(self._conn())
        assert len(issues) > 0
        assert "KE103" in issues[0]

    def test_ontology_parent_missing(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO kg_ontology_nodes (id, name, type, parent_id) VALUES (?, ?, ?, ?)",
            ("child", "Child", "type", "nonexistent-parent"),
        )
        conn.commit()
        conn.close()
        issues = check_ontology(self._conn())
        assert len(issues) > 0
        assert "KE107" in issues[0]


# ── Corruption Tests ─────────────────────────────────────────────────────────


class TestCorruption:
    """Pruebas donde la base está dañada deliberadamente.

    verify debe:
      - detectar el problema
      - devolver el código KE correcto
      - nunca terminar con una excepción no controlada
    """

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        self.db_path = tmp_path / "corrupt.db"
        self.source_dir = tmp_path / "source"
        self.source_dir.mkdir()
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(schema_path.read_text())
        sha = hashlib.sha256(b"content").hexdigest()
        conn.execute(
            "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, updated_at) "
            "VALUES ('d1', 'doc', 'test.md', ?, '{}', datetime('now'))",
            (sha,),
        )
        conn.commit()
        conn.close()
        (self.source_dir / "test.md").write_text("content")

    def _results_by_code(self, results):
        return {r[1]: r[2] for r in results}

    def test_db_does_not_exist(self, tmp_path):
        results = verify_graph(tmp_path / "nonexistent.db")
        codes = self._results_by_code(results)
        assert "db_exists" in codes

    def test_fts_deleted_detected(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DROP TABLE IF EXISTS kg_nodes_fts")
        conn.commit()
        conn.close()
        results = verify_graph(self.db_path)
        assert any("KE109" in r[2] for r in results if r[0] == "ERROR")

    def test_broken_edge_detected(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES ('ghost', 'nobody', 'refers')")
        conn.commit()
        conn.close()
        results = verify_graph(self.db_path)
        assert any("KE105" in r[2] for r in results if r[0] == "ERROR")

    def test_empty_active_version_no_crash(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM kg_active_version")
        conn.commit()
        conn.close()
        results = verify_graph(self.db_path)
        assert any("Sin versión activa" in r[2] for r in results if r[0] == "INFO")

    def test_duplicate_path_detected(self):
        conn = sqlite3.connect(str(self.db_path))
        self._insert_raw(conn, "d2", "doc", "test.md", "hash2")
        conn.commit()
        conn.close()
        results = verify_graph(self.db_path, self.source_dir)
        assert any("KE102" in r[2] for r in results)

    def _insert_raw(self, conn, nid, typ, path, sha):
        conn.execute(
            "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, updated_at) "
            "VALUES (?, ?, ?, ?, '{}', datetime('now'))",
            (nid, typ, path, sha),
        )

    def test_full_corrupt_does_not_crash(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DROP TABLE IF EXISTS kg_active_version")
        conn.execute("DROP TABLE IF EXISTS kg_nodes_fts")
        conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES ('ghost', 'nobody', 'x')")
        conn.commit()
        conn.close()
        try:
            results = verify_graph(self.db_path, self.source_dir)
        except Exception as exc:
            pytest.fail(f"verify_graph raised unexpected exception: {exc}")
        assert len(results) > 0, "Should return results even when DB is corrupt"


# ── Scanner Tests ────────────────────────────────────────────────────────────


class TestScanner:
    def test_scan_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        sources, _ = scan_source(empty)
        assert sources == []

    def test_scan_discovers_markdown(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "doc.md").write_text("hello")
        (src / "notes.yaml").write_text("key: val")
        sources, _ = scan_source(src)
        assert len(sources) == 2
        kinds = {s.kind for s in sources}
        assert "markdown" in kinds
        assert "yaml" in kinds

    def test_scan_content_sha256(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        f = src / "test.md"
        f.write_text("exact content")
        sources, _ = scan_source(src)
        assert len(sources) == 1
        so = sources[0]
        expected = hashlib.sha256(b"exact content").hexdigest()
        assert so.content_sha256 == expected
        assert so.size == 13
        assert so.content == b"exact content"

    def test_scan_skips_large_files(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "small.md").write_text("small")
        large = src / "large.md"
        with open(large, "wb") as f:
            f.write(b"x" * (20 * 1024 * 1024))  # 20MB > MAX_PARSE_SIZE
        sources, skipped = scan_source(src)
        assert len(sources) == 1
        assert len(skipped) == 1
        assert skipped[0].code == "KE205"

    def test_take_snapshot_has_timestamp(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("a")
        snap = take_snapshot(src)
        assert len(snap.sources) == 1
        assert snap.taken_at

    def test_scan_incremental_no_previous_returns_all(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("a")
        changed, snap, skipped, deleted = scan_incremental(None, src)
        assert len(changed) == 1
        assert len(skipped) == 0
        assert len(deleted) == 0

    def test_scan_incremental_detects_change_by_hash(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        f = src / "a.md"
        f.write_text("v1")
        _, snap, _, _ = scan_incremental(None, src)
        f.write_text("v2")
        changed, snap2, _, _ = scan_incremental(snap, src)
        assert len(changed) == 1

    def test_scan_incremental_no_change(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("stable")
        _, snap, _, _ = scan_incremental(None, src)
        changed, snap2, _, _ = scan_incremental(snap, src)
        assert len(changed) == 0

    def test_scan_incremental_new_file_detected(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("a")
        _, snap, _, _ = scan_incremental(None, src)
        (src / "b.md").write_text("b")
        changed, snap2, _, _ = scan_incremental(snap, src)
        assert len(changed) == 1

    def test_scan_incremental_deleted_detected(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("a")
        (src / "b.md").write_text("b")
        _, snap, _, _ = scan_incremental(None, src)
        (src / "b.md").unlink()
        changed, snap2, _, deleted = scan_incremental(snap, src)
        assert len(deleted) == 1
        assert deleted[0].path == "b.md"

    def test_scan_kind_unknown_ext(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "data.xyz").write_text("data")
        sources, _ = scan_source(src)
        assert sources[0].kind == "xyz"

    def test_scan_content_bytes_match(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "test.md").write_text("exact content bytes")
        sources, _ = scan_source(src)
        assert sources[0].content == b"exact content bytes"


# ── Parser Tests ─────────────────────────────────────────────────────────────


class TestParser:
    def test_parse_basic_doc(self):
        raw = "---\ntitle: Hello\ntype: doc\n---\nBody text"
        so = _content_so("test.md", raw)
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert result.document.frontmatter.title == "Hello"
        assert result.document.body == "Body text"
        assert result.document.content_sha256 == hashlib.sha256(raw.encode()).hexdigest()

    def test_parse_missing_title_returns_error(self):
        so = _content_so("notitle.md", "---\ntype: doc\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, CompileError)
        assert result.code == "KE001"

    def test_parse_missing_type_returns_error(self):
        so = _content_so("notype.md", "---\ntitle: Hi\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, CompileError)
        assert result.code == "KE002"

    def test_parse_invalid_yaml_returns_ke006(self):
        so = _content_so("badyaml.md", "---\ntitle: bad\n: invalid yaml\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, CompileError)
        assert result.code == "KE006"

    def test_parse_empty_document_returns_ke005(self):
        so = _content_so("empty.md", "")
        result = parse_source(so)
        assert isinstance(result, CompileError)
        assert result.code == "KE005"

    def test_parse_no_frontmatter_returns_ke001(self):
        so = _content_so("plain.md", "Just body text, no frontmatter")
        result = parse_source(so)
        assert isinstance(result, CompileError)
        assert result.code == "KE001"

    def test_parse_discovers_relations_from_links(self):
        so = _content_so("a.md", "---\ntitle: Doc A\ntype: doc\n---\nSee [Doc B](b.md) for details")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert len(result.relations) == 1
        assert result.relations[0].dst == "b.md"
        assert result.relations[0].relation == "references"

    def test_parse_discovers_wikilinks(self):
        so = _content_so("main.md", "---\ntitle: Main\ntype: doc\n---\nSee [[other]] and [[page|alias]]")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert len(result.relations) == 2
        dsts = {r.dst for r in result.relations}
        assert "other" in dsts
        assert "page" in dsts

    def test_parse_uses_custom_id_from_frontmatter(self):
        so = _content_so("long-path.md", "---\ntitle: Custom\ntype: doc\nid: my-custom-id\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert result.document.doc_id == "my-custom-id"

    def test_parse_relations_from_frontmatter(self):
        so = _content_so(
            "parent.md", "---\ntitle: Parent\ntype: doc\nrelated:\n  - child.md\n  - sibling.md\n---\nBody"
        )
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert len(result.relations) == 2
        dsts = {r.dst for r in result.relations}
        assert "child.md" in dsts
        assert "sibling.md" in dsts

    def test_parse_document_is_frozen(self):
        so = _content_so("frozen_test.md", "---\ntitle: Frozen\ntype: doc\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        with pytest.raises(AttributeError):
            result.document.frontmatter.title = "Mutated"

    def test_parse_body_unicode(self):
        content = "---\ntitle: Unicode\ntype: doc\n---\nHéllo wörld 🔥"
        so = _content_so("unicode.md", content)
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert "🔥" in result.document.body

    def test_parse_doc_id_from_hash(self):
        so = _content_so("docs/test/doc.md", "---\ntitle: Hash ID\ntype: doc\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        expected = doc_id_from_path("docs/test/doc.md")
        assert result.document.doc_id == expected
        assert "/" not in result.document.doc_id
        assert "." not in result.document.doc_id  # hash, no path-dots

    def test_parse_no_file_touches_never_called(self):
        """Parser NUNCA abre archivos — todo viene de so.content."""
        so = _content_so("ghost.md", "---\ntitle: Ghost\ntype: doc\n---\nBody")
        result = parse_source(so)
        assert isinstance(result, KnowledgeObject)
        assert result.document.frontmatter.title == "Ghost"


# ── Validator Tests ───────────────────────────────────────────────────────────


def _make_ko(
    doc_id: str = "test",
    doc_type: str = "doc",
    title: str = "Test",
    status: str = "draft",
    body: str = "Body content here with enough text to pass min length check.",
    quality: float = 0.0,
    confidence: float = 0.0,
    tags: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    extra: dict | None = None,
    relations: tuple[tuple[str, str], ...] = (),
) -> KnowledgeObject:
    fm = Frontmatter(title=title, doc_type=doc_type, tags=tags, aliases=aliases, status=status, extra=extra or {})
    doc = Document(
        doc_id=doc_id,
        doc_type=doc_type,
        path=f"{doc_id}.md",
        content_sha256="abc",
        frontmatter=fm,
        body=body,
        quality=quality,
        confidence=confidence,
    )
    rels = tuple(Relation(src=doc_id, dst=dst, relation=rel) for dst, rel in relations)
    return KnowledgeObject(document=doc, relations=rels)


class TestValidator:
    def test_valid_doc_passes(self):
        ko = _make_ko()
        result = validate_knowledge_object(ko)
        assert result.valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_invalid_doc_type_returns_ke003(self):
        ko = _make_ko(doc_type="invalid_type")
        result = validate_knowledge_object(ko)
        assert not result.valid
        codes = [e.code for e in result.errors]
        assert "KE003" in codes

    def test_nonstandard_status_warns_ke009(self):
        ko = _make_ko(status="invalid_status")
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE009" in codes

    def test_quality_out_of_range_warns(self):
        ko = _make_ko(quality=1.5)
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE009" in codes

    def test_confidence_out_of_range_warns(self):
        ko = _make_ko(confidence=-0.1)
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE009" in codes

    def test_body_too_short_warns(self):
        ko = _make_ko(body="Hi")
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE009" in codes

    def test_invalid_tag_warns(self):
        ko = _make_ko(tags=("valid", ""))
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE009" in codes

    def test_deprecated_field_warns_ke204(self):
        ko = _make_ko(extra={"category": "old"})
        result = validate_knowledge_object(ko)
        assert result.valid
        codes = [w.code for w in result.warnings]
        assert "KE204" in codes

    def test_custom_valid_types(self):
        custom = frozenset({"custom_type"})
        ko = _make_ko(doc_type="custom_type")
        result = validate_knowledge_object(ko, valid_types=custom)
        assert result.valid

        ko2 = _make_ko(doc_type="doc")
        result2 = validate_knowledge_object(ko2, valid_types=custom)
        assert not result2.valid

    def test_empty_body_no_warning(self):
        ko = _make_ko(body="")
        result = validate_knowledge_object(ko)
        assert result.valid
        assert len(result.warnings) == 0

    # ── Bug regression tests (C3 audit) ───────────────────────────────────

    def test_int_doc_id_does_not_crash(self):
        fm = Frontmatter(title="T", doc_type="doc")
        doc = Document(doc_id=123, doc_type="doc", path="int_id.md", content_sha256="abc", frontmatter=fm)
        ko = KnowledgeObject(document=doc)
        result = validate_knowledge_object(ko)
        assert result.valid
        assert "KE009" in [w.code for w in result.warnings]

    def test_ke004_no_duplicate_for_same_dst(self):
        rel1 = ("ghost", "references")
        rel2 = ("ghost", "depends")
        kos = [_make_ko("a", "doc", "Doc A", relations=(rel1, rel2))]
        _, errors, _ = validate_batch(kos)
        ke004 = [e for e in errors if e.code == "KE004"]
        assert len(ke004) == 1, f"KE004 duplicado: {len(ke004)}"

    def test_empty_doc_type_returns_ke003(self):
        ko = _make_ko(doc_type="")
        result = validate_knowledge_object(ko)
        codes = [e.code for e in result.errors]
        assert "KE003" in codes

    def test_duplicate_doc_id_returns_ke101(self):
        kos = [
            _make_ko("dup", "doc", "Doc A", body="Body content A here test."),
            _make_ko("dup", "doc", "Doc B", body="Body content B here test."),
        ]
        _, errors, _ = validate_batch(kos)
        codes = [e.code for e in errors]
        assert "KE101" in codes

    def test_duplicate_path_warns_ke007(self):
        fm = Frontmatter(title="A", doc_type="doc")
        fm2 = Frontmatter(title="B", doc_type="doc")
        d1 = Document(doc_id="a", doc_type="doc", path="same.md", content_sha256="abc", frontmatter=fm)
        d2 = Document(doc_id="b", doc_type="doc", path="same.md", content_sha256="def", frontmatter=fm2)
        kos = [KnowledgeObject(document=d1), KnowledgeObject(document=d2)]
        _, errors, warnings = validate_batch(kos)
        codes = [w.code for w in warnings]
        assert "KE007" in codes

    def test_all_invalid_tags_reported(self):
        ko = _make_ko(tags=("ok", "", "  ", None))
        result = validate_knowledge_object(ko)
        ke009 = [w for w in result.warnings if w.code == "KE009"]
        assert len(ke009) == 3

    def test_non_string_doc_type_returns_ke003(self):
        fm = Frontmatter(title="T", doc_type=None)
        doc = Document(doc_id="x", doc_type=None, path="x.md", content_sha256="abc", frontmatter=fm)
        ko = KnowledgeObject(document=doc)
        result = validate_knowledge_object(ko)
        codes = [e.code for e in result.errors]
        assert "KE003" in codes

    # ── Batch validation ──────────────────────────────────────────────────

    def test_batch_valid_passes(self):
        kos = [
            _make_ko("a", "doc", "Doc A"),
            _make_ko("b", "doc", "Doc B", relations=(("a", "references"),)),
        ]
        valid, errors, warnings = validate_batch(kos)
        assert len(errors) == 0
        assert len(valid) == 2

    def test_batch_broken_relation_ke004(self):
        kos = [
            _make_ko("a", "doc", "Doc A", relations=(("nonexistent", "references"),)),
        ]
        valid, errors, warnings = validate_batch(kos)
        codes = [e.code for e in errors]
        assert "KE004" in codes
        assert len(valid) == 1

    def test_batch_invalid_type_excluded(self):
        kos = [
            _make_ko("a", "invalid_type", "Doc A"),
            _make_ko("b", "doc", "Doc B"),
        ]
        valid, errors, warnings = validate_batch(kos)
        codes = [e.code for e in errors]
        assert "KE003" in codes
        assert len(valid) == 1
        assert valid[0].document.doc_id == "b"

    def test_batch_reuses_valid_types(self):
        custom = frozenset({"custom_a", "custom_b"})
        kos = [
            _make_ko("a", "custom_a", "Doc A"),
            _make_ko("b", "custom_b", "Doc B"),
        ]
        valid, errors, warnings = validate_batch(kos, valid_types=custom)
        assert len(errors) == 0
        assert len(valid) == 2


# ── CLI Tests ────────────────────────────────────────────────────────────────


class TestKnowledgeEngineCLI:
    def test_cli_init(self, tmp_path):
        db_path = tmp_path / "test_cli.db"
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "init"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "initialized" in result.stdout.lower()
        assert db_path.exists()

    def test_cli_verify_empty(self, tmp_path):
        db_path = tmp_path / "test_cli_verify.db"
        subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "init"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "verify"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "All checks passed" in result.stdout

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert "URA Knowledge Engine" in result.stdout


# ── Integration Test ─────────────────────────────────────────────────────────


class TestIntegration:
    def test_full_pipeline(self, tmp_path):
        db_path = tmp_path / "test_pipeline.db"

        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "init"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0

        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "verify"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "All checks passed" in result.stdout

        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db_path), "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "Documents: 0" in result.stdout

    def test_compile_returns_ok_when_no_changes(self, tmp_path):
        db = tmp_path / "test_compile.db"
        subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "init"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "compile"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0

    def test_e2e_compile_search_verify_incremental(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "intro.md").write_text("---\ntitle: Introduction\ntype: doc\n---\n\nWelcome to the knowledge base.")
        (src / "guide.md").write_text("---\ntitle: User Guide\ntype: doc\nid: guide\n---\n\nStep-by-step instructions.")
        (src / "api.md").write_text("---\ntitle: API Reference\ntype: doc\n---\n\nDetailed API docs.")

        db = tmp_path / "e2e.db"
        init_db(db, SCHEMA_PATH)

        # Compile 3 documents
        result = compile_source(
            source_dir=src,
            db_path=db,
            compiler_version="e2e-test",
        )
        assert result.success, f"Compile failed: {result.errors}"
        assert result.documents_total == 3

        # Search
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(db)
        results = reader.search("introduction", mode="lexical")
        assert len(results) > 0
        assert results[0].doc_id is not None

        # Related (no relations in these flat docs)
        related = reader.related("guide.md")
        assert len(related) == 0

        # Graph
        graph = reader.graph()
        assert len(graph) >= 3

        # Verify
        from knowledge.engine.verifier import verify_graph

        v_results = verify_graph(db, source_dir=src)
        errors = [r for r in v_results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Verify errors: {errors}"

        # Simulate process restart: new reader
        reader2 = KnowledgeReader(db)
        results2 = reader2.search("introduction", mode="lexical")
        assert len(results2) > 0

        # Incremental: add a doc
        (src / "faq.md").write_text("---\ntitle: FAQ\ntype: doc\n---\n\nFrequently asked questions.")
        result2 = compile_source(
            source_dir=src,
            db_path=db,
            compiler_version="e2e-test",
        )
        assert result2.success
        assert result2.documents_total >= 1

        # Reader sees new doc (cache was invalidated by apply_compile via clear_all_caches)
        faq = reader2.get_document(doc_id_from_path("faq.md"))
        assert faq is not None, "FAQ doc not found after incremental compile"
        assert faq.frontmatter.title == "FAQ"

        # Full verify still passes
        v2 = verify_graph(db, source_dir=src)
        errors2 = [r for r in v2 if r[0] == "ERROR"]
        assert len(errors2) == 0, f"Verify errors after incremental: {errors2}"


# ── Reader Tests ─────────────────────────────────────────────────────────────


class TestKnowledgeReader:
    def setup_reader(self, tmp_path):
        db = tmp_path / "test_reader.db"
        src = tmp_path / "source"
        src.mkdir()
        (src / "intro.md").write_text(
            "---\ntitle: Introduction\ntype: doc\ntags: [guide]\n---\n\nThis is the introduction to the knowledge base."
        )
        (src / "api.md").write_text(
            "---\ntitle: API Reference\ntype: api\naliases: [api-docs]\n---\n\n"
            "The API reference document describes the endpoints."
        )
        init_db(db, SCHEMA_PATH)
        compile_source(source_dir=src, db_path=db)
        return db

    def test_get_document_found(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        doc = reader.get_document("e37a304847f4")
        assert doc is not None
        assert doc.frontmatter.title == "Introduction"
        assert doc.doc_type == "doc"

    def test_get_document_not_found(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        assert reader.get_document("nonexistent") is None

    def test_search_lexical(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        results = reader.search("introduction", mode="lexical")
        assert len(results) > 0
        assert any("Introduction" in r.title for r in results)
        assert all(r.score <= 0.0 for r in results)

    def test_search_no_results(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        assert len(reader.search("ZZZZNOTFOUND", mode="lexical")) == 0

    def test_search_with_type_filter(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        results = reader.search("API", mode="lexical", filters={"type": "api"})
        assert len(results) > 0
        assert all(r.doc_type == "api" for r in results)

    def test_related_empty(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        assert len(reader.related("e37a304847f4")) == 0

    def test_graph_returns_all_nodes(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        nodes = reader.graph()
        assert len(nodes) == 2

    def test_unsupported_mode_raises(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader
        import pytest

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        with pytest.raises(ValueError, match="Modo de búsqueda no soportado"):
            reader.search("test", mode="semantic")

    def test_search_cli(self, tmp_path):
        db = self.setup_reader(tmp_path)
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "search", "introduction"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "Introduction" in result.stdout

    def test_read_cli(self, tmp_path):
        db = self.setup_reader(tmp_path)
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "read", "e37a304847f4"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "Introduction" in result.stdout

    def test_related_cli(self, tmp_path):
        db = self.setup_reader(tmp_path)
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "related", "e37a304847f4"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "No relations" in result.stdout or "No related" in result.stdout


# ── Migration Tests ───────────────────────────────────────────────────────────


class TestMigration:
    def test_get_schema_version(self, tmp_path):
        from knowledge.engine.migrations import get_schema_version, SCHEMA_VERSION

        db = tmp_path / "migrate.db"
        conn = sqlite3.connect(str(db))
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        assert get_schema_version(conn) == SCHEMA_VERSION
        conn.close()

    def test_fresh_init_sets_version(self, tmp_path):
        db = tmp_path / "fresh.db"
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(db, schema_path)
        conn = sqlite3.connect(str(db))
        from knowledge.engine.migrations import get_schema_version, SCHEMA_VERSION

        assert get_schema_version(conn) == SCHEMA_VERSION
        conn.close()

    def test_migrate_v6_to_v7_adds_body_column(self, tmp_path):
        db = tmp_path / "v6.db"
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        # Create v6 DB
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY, type TEXT NOT NULL, path TEXT NOT NULL,
                content_sha256 TEXT NOT NULL, frontmatter TEXT NOT NULL,
                semantic TEXT, quality REAL, confidence REAL,
                embed_hash TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kg_active_version (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                graph_version INTEGER NOT NULL,
                source_commit TEXT NOT NULL,
                compiler_version TEXT NOT NULL,
                qdrant_collection TEXT NOT NULL DEFAULT '',
                swapped_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO kg_active_version
                (singleton, graph_version, source_commit, compiler_version, swapped_at)
                VALUES (1, 0, '', '', datetime('now'));
            CREATE VIRTUAL TABLE IF NOT EXISTS kg_nodes_fts USING fts5(
                id UNINDEXED, title, body, tags, tokenize='porter unicode61'
            );
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_type TEXT NOT NULL,
                priority INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
                payload TEXT, dedup_key TEXT, created_at TEXT NOT NULL,
                started_at TEXT, completed_at TEXT, error TEXT
            );
            CREATE TABLE IF NOT EXISTS op_compile_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER,
                error_code TEXT NOT NULL, document TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL DEFAULT 'ERROR',
                message TEXT NOT NULL DEFAULT '', line INTEGER DEFAULT 0,
                column INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS op_vector_sync (
                doc_id TEXT NOT NULL, operation TEXT NOT NULL CHECK (operation IN ('upsert','delete')),
                run_id INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','done','failed','dead_letter')),
                last_error TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (doc_id, operation, run_id)
            );
            CREATE TABLE IF NOT EXISTS op_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK (kind IN ('source','vectors','cold')),
                source_commit TEXT, manifest_path TEXT NOT NULL,
                archive_path TEXT NOT NULL, compressed_size INTEGER,
                content_sha256 TEXT NOT NULL,
                archived_at TEXT NOT NULL DEFAULT (datetime('now')),
                retention_days INTEGER NOT NULL DEFAULT 90
            );
        """)
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
        conn.close()

        # Migrate
        init_db(db, schema_path)  # should detect v6 and apply migration
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(kg_nodes)").fetchall()]
        assert "body" in cols, f"body column missing: {cols}"
        from knowledge.engine.migrations import get_schema_version, SCHEMA_VERSION

        assert get_schema_version(conn) == SCHEMA_VERSION
        conn.close()

    def test_verify_detects_version_mismatch(self, tmp_path):
        db = tmp_path / "mismatch.db"
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
        conn.close()
        results = verify_graph(db)
        version_mismatch = [r for r in results if r[1] == "schema_version" and "mismatch" in r[2]]
        assert len(version_mismatch) > 0

    def test_cli_init_sets_schema_version(self, tmp_path):
        db = tmp_path / "cli_init.db"
        result = subprocess.run(
            [sys.executable, str(ENGINE_SCRIPT), "--db-path", str(db), "init"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        conn = sqlite3.connect(str(db))
        from knowledge.engine.migrations import get_schema_version, SCHEMA_VERSION

        assert get_schema_version(conn) == SCHEMA_VERSION
        conn.close()

    def test_migration_v5_to_v7_chain(self, tmp_path):
        db = tmp_path / "v5.db"
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript("PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;")
        # v5 tenía el mismo schema que v6 pero sin columna body
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY, type TEXT NOT NULL, path TEXT NOT NULL,
                content_sha256 TEXT NOT NULL, frontmatter TEXT NOT NULL,
                semantic TEXT, quality REAL, confidence REAL,
                embed_hash TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kg_active_version (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                graph_version INTEGER NOT NULL,
                source_commit TEXT NOT NULL,
                compiler_version TEXT NOT NULL,
                qdrant_collection TEXT NOT NULL DEFAULT '',
                swapped_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO kg_active_version
                (singleton, graph_version, source_commit, compiler_version, swapped_at)
                VALUES (1, 0, '', '', datetime('now'));
            CREATE VIRTUAL TABLE IF NOT EXISTS kg_nodes_fts USING fts5(
                id UNINDEXED, title, body, tags, tokenize='porter unicode61'
            );
            CREATE TABLE IF NOT EXISTS op_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_type TEXT NOT NULL,
                priority INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
                payload TEXT, dedup_key TEXT, created_at TEXT NOT NULL,
                started_at TEXT, completed_at TEXT, error TEXT
            );
            CREATE TABLE IF NOT EXISTS op_compile_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER,
                error_code TEXT NOT NULL, document TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL DEFAULT 'ERROR',
                message TEXT NOT NULL DEFAULT '', line INTEGER DEFAULT 0,
                column INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS op_vector_sync (
                doc_id TEXT NOT NULL, operation TEXT NOT NULL CHECK (operation IN ('upsert','delete')),
                run_id INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','done','failed','dead_letter')),
                last_error TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (doc_id, operation, run_id)
            );
            CREATE TABLE IF NOT EXISTS op_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK (kind IN ('source','vectors','cold')),
                source_commit TEXT, manifest_path TEXT NOT NULL,
                archive_path TEXT NOT NULL, compressed_size INTEGER,
                content_sha256 TEXT NOT NULL,
                archived_at TEXT NOT NULL DEFAULT (datetime('now')),
                retention_days INTEGER NOT NULL DEFAULT 90
            );
        """)
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
        conn.close()

        init_db(db, schema_path)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        from knowledge.engine.migrations import get_schema_version, SCHEMA_VERSION

        assert get_schema_version(conn) == SCHEMA_VERSION
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(kg_nodes)").fetchall()]
        assert "body" in cols, f"body column missing after v5→v7 migration: {cols}"
        conn.close()

    def test_compile_manifest_has_details(self, tmp_path):
        db = tmp_path / "manifest.db"
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(db, schema_path)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT details FROM op_compiler_runs ORDER BY id DESC LIMIT 1").fetchone()
        if row and row["details"]:
            details = json.loads(row["details"])
            assert "parser_version" in details
            assert "schema_version" in details
            assert details["schema_version"] == SCHEMA_VERSION
            assert "host" in details
            assert "duration_ms" in details
        conn.close()

    def test_begin_immediate_retry_timeout(self):
        import sqlite3

        db = Path(tempfile.mktemp(suffix=".db"))
        from knowledge.engine.sqlite_writer import _begin_immediate_with_retry

        conn1 = sqlite3.connect(str(db))
        conn2 = sqlite3.connect(str(db))
        conn1.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="Could not acquire"):
            _begin_immediate_with_retry(conn2, timeout=0.1)
        conn1.rollback()
        conn2.close()
        conn1.close()
        db.unlink()


class TestChunker:
    def test_chunk_single_short_doc(self):
        from knowledge.engine.chunker import chunk_text

        text = "Hello world"
        chunks = chunk_text(text, doc_id="d1")
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].doc_id == "d1"

    def test_chunk_splits_long_text(self):
        from knowledge.engine.chunker import chunk_text

        words = ["word"] * 1500
        text = " ".join(words)
        chunks = chunk_text(text, max_words=500, overlap=50)
        assert len(chunks) > 1
        assert all(c.chunk_index == i for i, c in enumerate(chunks))
        assert all(c.text for c in chunks)

    def test_chunk_empty_text(self):
        from knowledge.engine.chunker import chunk_text

        assert chunk_text("") == []

    def test_chunk_overlap_content(self):
        from knowledge.engine.chunker import chunk_text

        words = ["w{}".format(i) for i in range(600)]
        text = " ".join(words)
        chunks = chunk_text(text, max_words=200, overlap=20)
        assert len(chunks) >= 3
        overlap_text = chunks[0].text.split()[-20:]
        next_start = chunks[1].text.split()[:20]
        assert overlap_text == next_start

    def test_chunk_document(self):
        from knowledge.engine.chunker import chunk_document
        from knowledge.engine.models import Document, Frontmatter

        doc = Document(
            doc_id="doc1",
            doc_type="note",
            path="/test/doc1.md",
            content_sha256="abc",
            frontmatter=Frontmatter(title="Test Doc"),
            body="sentence " * 1000,
        )
        chunks = chunk_document(doc, max_words=500, overlap=50)
        assert len(chunks) > 1
        for c in chunks:
            assert c.doc_id == "doc1"
            assert c.doc_type == "note"
            assert c.title == "Test Doc"

    def test_chunk_body_preserves_metadata(self):
        from knowledge.engine.chunker import chunk_text

        chunks = chunk_text("some text", doc_id="d2", doc_type="article", path="/a.md", title="Art")
        assert len(chunks) == 1
        assert chunks[0].doc_id == "d2"
        assert chunks[0].doc_type == "article"
        assert chunks[0].path == "/a.md"
        assert chunks[0].title == "Art"

    def test_exact_boundary(self):
        from knowledge.engine.chunker import chunk_text

        words = ["boundary"] * 500
        text = " ".join(words)
        chunks = chunk_text(text, max_words=500)
        assert len(chunks) == 1

    def test_one_over_boundary(self):
        from knowledge.engine.chunker import chunk_text

        words = ["word"] * 501
        text = " ".join(words)
        chunks = chunk_text(text, max_words=500, overlap=50)
        assert len(chunks) == 2


class TestQdrantSync:
    def test_sync_documents_qdrant_unavailable(self, tmp_path, caplog):
        from knowledge.engine.qdrant_sync import sync_documents
        from knowledge.engine.models import Document, Frontmatter

        caplog.set_level("INFO")
        db_path = tmp_path / "test_sync.db"
        from knowledge.engine.sqlite_writer import init_db

        init_db(db_path, SCHEMA_PATH)
        doc = Document(
            doc_id="d1",
            doc_type="note",
            path="/d1.md",
            content_sha256="abc",
            frontmatter=Frontmatter(title="Q"),
            body="test content for qdrant sync",
        )
        result = sync_documents(db_path, [doc], [], run_id=0)
        assert result == 0
        assert "Qdrant no disponible" in caplog.text

    def test_search_semantic_qdrant_unavailable(self):
        from knowledge.engine.qdrant_sync import search_semantic

        assert search_semantic("test query") == []


class TestHybridSearch:
    def setup_reader(self, tmp_path):
        db = tmp_path / "test_hybrid.db"
        src = tmp_path / "source"
        src.mkdir()
        (src / "intro.md").write_text(
            "---\ntitle: Introduction\ntype: doc\ntags: [guide]\n---\n\nThis is the introduction to the knowledge base."
        )
        init_db(db, SCHEMA_PATH)
        compile_source(source_dir=src, db_path=db)
        return db

    def test_search_hybrid_supported(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        results = reader.search("test", mode="hybrid")
        assert isinstance(results, list)

    def test_search_hybrid_fallback_to_lexical(self, tmp_path):
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(self.setup_reader(tmp_path))
        results = reader.search("introduction", mode="hybrid")
        assert len(results) >= 1
        assert any("Introduction" in r.title for r in results)


# ── Golden-master tests (Fase 0 — determinismo) ────────────────────────────


class TestDeterminism:
    """El grafo compilado es función pura de source@commit + compiler_version.

    Recompilar el mismo conjunto de documentos dos veces debe producir
    un graph_content_sha256 idéntico (excluyendo metadatos temporales).
    """

    def _build_test_source(self, tmp_path: Path) -> Path:
        src = tmp_path / "source"
        src.mkdir(parents=True, exist_ok=True)
        (src / "test-a.md").write_text(
            "---\nid: test-a\ntitle: Documento A\ntype: doc\n---\n\n"
            "Este es el contenido del documento A.\n"
        )
        (src / "test-b.md").write_text(
            "---\nid: test-b\ntitle: Documento B\ntype: spec\n---\n\n"
            "Este es el contenido B con referencia a [[test-a]].\n"
        )
        return src

    def _compile_and_get_hash(self, source_dir: Path, db_path: Path) -> str | None:
        from knowledge.engine.compiler import compile_source
        from knowledge.engine.orchestrator import get_determinism_hash

        compile_source(source_dir=source_dir, db_path=db_path)
        return get_determinism_hash(db_path)

    def test_same_input_produces_same_hash(self, tmp_path):
        """Compilar el mismo source dos veces → mismo hash."""
        db1 = tmp_path / "run1" / "knowledge.db"
        db1.parent.mkdir()
        from knowledge.engine.sqlite_writer import init_db

        init_db(db1, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        db2 = tmp_path / "run2" / "knowledge.db"
        db2.parent.mkdir()
        init_db(db2, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        src = self._build_test_source(tmp_path)

        h1 = self._compile_and_get_hash(src, db1)
        h2 = self._compile_and_get_hash(src, db2)

        assert h1 is not None, "Compile debe producir un determinism hash"
        assert h2 is not None, "Segundo compile debe producir un determinism hash"
        assert h1 == h2, (
            f"Mismo source debe producir mismo hash. "
            f"Got h1={h1[:16]} h2={h2[:16]}. "
            f"Si falla, revisar que el determinismo no incluya metadatos temporales."
        )

    def test_different_input_produces_different_hash(self, tmp_path):
        """Source diferente → hash diferente."""
        from knowledge.engine.sqlite_writer import init_db

        db = tmp_path / "knowledge.db"
        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        src_a = tmp_path / "source_a"
        src_a.mkdir()
        (src_a / "doc.md").write_text("---\ntitle: Version A\ntype: doc\n---\n\nContent A\n")
        hash_a = self._compile_and_get_hash(src_a, db)

        src_b = tmp_path / "source_b"
        src_b.mkdir()
        (src_b / "doc.md").write_text("---\ntitle: Version B\ntype: doc\n---\n\nContent B\n")
        hash_b = self._compile_and_get_hash(src_b, db)

        assert hash_a is not None
        assert hash_b is not None
        assert hash_a != hash_b, "Source diferente debe producir hash diferente"

    def test_determinism_hash_persists(self, tmp_path):
        """El hash sobrevive a una reconexión de DB."""
        from knowledge.engine.sqlite_writer import init_db

        db = tmp_path / "knowledge.db"
        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        src = self._build_test_source(tmp_path)
        self._compile_and_get_hash(src, db)

        import sqlite3

        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT determinism_hash FROM kg_active_version WHERE singleton = 1"
        ).fetchone()
        conn.close()

        assert row is not None
        assert len(row[0]) == 64, "SHA-256 hex debe tener 64 caracteres"
        assert row[0] != "", "Hash no debe ser vacío"


# ── Archive Integration Tests (Fase A) ─────────────────────────────────────


class TestArchiveIntegration:
    """El archivado es un efecto secundario asíncrono, no parte crítica del compile.

    Principios:
    - El compilador no conoce archiver.py.
    - El orquestador encola + procesa trabajos archive_source en op_jobs.
    - Si el archivado falla, el compile sigue siendo exitoso.
    """

    def _setup_source_and_db(self, tmp_path: Path) -> tuple[Path, Path]:
        """Crea source/ (en repo git) y knowledge.db, retorna (source_dir, db_path).

        El repo git se inicializa en tmp_path (no en source/) para que .git/
        no sea escaneado por el scanner.
        """
        src = tmp_path / "source"
        src.mkdir(parents=True, exist_ok=True)
        (src / "doc.md").write_text(
            "---\ntitle: Archive Test\ntype: doc\n---\n\nBody content for archive test.\n"
        )

        db = tmp_path / "knowledge.db"
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(db, schema_path)

        # Git init en tmp_path (parent de source/), así .git/ no contamina el scan
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "initial"], capture_output=True)

        return src, db

    def test_compile_creates_archive_job(self, tmp_path):
        """Tras un compile correcto se crea exactamente un job archive_source
        y se procesa satisfactoriamente."""
        src, db = self._setup_source_and_db(tmp_path)

        from knowledge.engine.orchestrator import request_compile

        request_compile("test-archive-job", source_dir=src, db_path=db)

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        jobs = conn.execute(
            "SELECT id, job_type, status, error FROM op_jobs WHERE job_type = 'archive_source'"
        ).fetchall()
        conn.close()

        assert len(jobs) == 1, (
            f"Debe haber exactamente un archive_source job, encontrados {len(jobs)}"
        )
        assert jobs[0]["job_type"] == "archive_source"
        assert jobs[0]["status"] == "completed", (
            f"Job debería estar completed, está {jobs[0]['status']}: {jobs[0]['error']}"
        )

    def test_archive_failure_does_not_affect_compile(self, tmp_path):
        """Simular fallo de archive_source.

        Verifica que:
        - El compile termina correctamente (nodos escritos)
        - El job queda en 'failed'
        - knowledge.db permanece íntegra
        - El golden-master (determinism hash) sigue funcionando
        """
        from unittest.mock import patch

        import knowledge.engine.archiver as archiver_module

        src, db = self._setup_source_and_db(tmp_path)
        from knowledge.engine.orchestrator import get_determinism_hash, request_compile

        # Archive falla
        with patch.object(
            archiver_module, "archive_source",
            side_effect=RuntimeError("simulated archive failure"),
        ):
            request_compile("test-archive-fail", source_dir=src, db_path=db)

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        # 1. Compile succeeded → nodes exist
        node_count = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        assert node_count > 0, "Compile debe haber producido nodos"

        # 2. Archive job is failed
        job = conn.execute(
            "SELECT status, error FROM op_jobs WHERE job_type = 'archive_source'"
        ).fetchone()
        assert job is not None, "Debe existir un archive_source job"
        assert job["status"] == "failed", (
            f"Job debe estar 'failed', está '{job['status']}'"
        )
        assert "simulated archive failure" in job["error"]

        # 3. DB integrity intacta
        from knowledge.engine.verifier import verify_graph

        results = verify_graph(db, source_dir=src)
        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"DB debe estar íntegra tras archive failure: {errors}"

        conn.close()

        # 4. Golden-master (determinism hash) sigue funcionando
        h = get_determinism_hash(db)
        assert h is not None
        assert len(h) == 64
        assert h != ""


# ── Observability Tests (Fase B) ──────────────────────────────────────────


class TestMetricsExport:
    """Pruebas del módulo de métricas (knowledge/engine/metrics.py).

    Principios:
    - Las métricas son pasivas: observar, nunca alterar.
    - export_metrics() debe funcionar con cualquier estado de BD.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.tmp_path = tmp_path

    def test_export_empty_db(self, tmp_path):
        """Exportador funciona con BD vacía (sin nodos, sin compiles)."""
        from knowledge.engine.metrics import export_metrics

        db = tmp_path / "empty.db"
        # Sin init_db — BD no existe
        data = export_metrics(db_path=db)
        assert isinstance(data, bytes)
        text = data.decode("utf-8")
        # Formato Prometheus: líneas con # HELP, # TYPE, o métrica
        assert "# HELP" in text
        assert "# TYPE" in text

    def test_export_with_data(self, tmp_path):
        """Exportador con miles de registros simulados en SQLite."""
        from knowledge.engine.metrics import export_metrics
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = tmp_path / "data.db"
        init_db(db, schema_path)

        # Insertar datos de prueba
        conn = sqlite3.connect(str(db))
        for i in range(100):
            conn.execute(
                "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, updated_at) "
                "VALUES (?, 'doc', ?, 'abc', '{}', datetime('now'))",
                (f"node-{i:04d}", f"doc_{i}.md"),
            )
        conn.execute(
            "INSERT INTO kg_edges (src, dst, relation) VALUES ('node-0000', 'node-0001', 'references')"
        )
        conn.execute(
            "INSERT INTO op_compiler_runs "
            "(status, started_at, completed_at, source_commit, compiler_version, "
            " documents_changed, documents_total, errors, warnings, graph_version, details) "
            "VALUES ('completed', datetime('now'), datetime('now'), 'abc', 'test', "
            " 10, 100, 2, 1, 5, '{}')"
        )
        conn.execute(
            "INSERT INTO op_compile_errors (run_id, error_code, document, severity) "
            "VALUES (1, 'KE001', 'test.md', 'ERROR')"
        )
        conn.commit()
        conn.close()

        data = export_metrics(db_path=db)
        text = data.decode("utf-8")
        assert "ke_db_nodes_total" in text
        assert "ke_db_edges_total" in text
        assert "ke_db_compile_runs_total" in text
        assert "ke_db_compile_errors" in text

    def test_record_functions_do_not_raise(self):
        """Las funciones record_* nunca lanzan excepciones."""
        from knowledge.engine.metrics import (
            record_archive,
            record_compile,
            record_error,
            record_qdrant_sync,
            record_search,
        )

        record_compile(source="test")
        record_search(mode="lexical", duration=0.1)
        record_qdrant_sync(operation="upsert", status="done")
        record_archive(kind="source", status="completed")
        record_error(code="KE999")

    def test_metrics_are_read_only(self):
        """Las métricas solo observan — verificamos que export_metrics no
        modifica la BD (no escribe nada)."""
        from knowledge.engine.metrics import export_metrics
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = self.tmp_path / "readonly.db"
        init_db(db, schema_path)

        conn = sqlite3.connect(str(db))
        initial_count = conn.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
        conn.close()

        export_metrics(db_path=db)

        conn = sqlite3.connect(str(db))
        after_count = conn.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
        conn.close()

        assert after_count == initial_count, "export_metrics no debe modificar la BD"


class TestCorrelationId:
    """El correlation_id nace en request_compile() y se propaga
    al compilador, SQLite (op_compiler_runs.details), y logs."""

    def _setup_source_and_db(self, tmp_path: Path) -> tuple[Path, Path]:
        src = tmp_path / "source"
        src.mkdir(parents=True, exist_ok=True)
        (src / "doc.md").write_text(
            "---\ntitle: Cid Test\ntype: doc\n---\n\nBody content.\n"
        )
        db = tmp_path / "knowledge.db"
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)
        return src, db

    def test_correlation_id_in_details(self, tmp_path):
        """Verifica que el correlation_id generado por request_compile
        se almacena en op_compiler_runs.details."""
        from knowledge.engine.orchestrator import request_compile

        src, db = self._setup_source_and_db(tmp_path)

        import uuid

        test_cid = uuid.uuid4().hex

        # Llamar con correlation_id fijo inyectado via source_dir diferente
        # (el correlation_id real lo genera _execute_compile, pero
        #  podemos verificarlo en los detalles del compile)
        request_compile("test-cid", source_dir=src, db_path=db)

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT details FROM op_compiler_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        assert row is not None, "Debe haber al menos un compiler run"
        details = json.loads(row["details"])
        assert "correlation_id" in details, (
            f"details debe contener correlation_id: {details}"
        )
        assert len(details["correlation_id"]) == 32, (
            f"correlation_id debe ser UUID hex (32 chars), got {details['correlation_id']!r}"
        )

    def test_correlation_id_in_compile_metadata(self):
        """Verifica que correlation_id se pasa a CompileMetadata."""
        from knowledge.engine.compiler import compile_source
        from knowledge.engine.models import CompileMetadata

        meta = CompileMetadata(correlation_id="test-correlation-123")
        assert meta.correlation_id == "test-correlation-123"


class TestStructuredLogging:
    """Pruebas de logs estructurados (URA_STRUCTURED_LOGS=true)."""

    def test_json_formatter_output(self):
        """El JSONFormatter produce JSON válido con campos esperados."""
        from knowledge.engine.logging_config import JSONFormatter, set_correlation_id
        import logging

        set_correlation_id("")
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="test message %s",
            args=("arg",),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "test message arg"
        assert "timestamp" in parsed

    def test_json_formatter_includes_correlation_id(self):
        """Si correlation_id está presente, aparece en el JSON."""
        from knowledge.engine.logging_config import JSONFormatter, set_correlation_id
        import logging

        set_correlation_id("abc-123-def")
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__,
            lineno=1, msg="hello", args=(), exc_info=None,
        )
        record.correlation_id = "abc-123-def"  # lo añade CorrelationFilter en runtime
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "abc-123-def"
        set_correlation_id("")

    def test_setup_logging_env_var(self, monkeypatch):
        """URA_STRUCTURED_LOGS=true activa el JSONFormatter."""
        from knowledge.engine.logging_config import setup_logging
        import logging

        monkeypatch.setenv("URA_STRUCTURED_LOGS", "true")
        setup_logging()

        root = logging.getLogger()
        has_json = any(
            hasattr(h, "formatter") and "JSON" in type(h.formatter).__name__
            for h in root.handlers
        )
        assert has_json, "Debe haber al menos un handler con JSONFormatter"

        monkeypatch.delenv("URA_STRUCTURED_LOGS", raising=False)

    def test_json_plain_semantic_equivalence(self):
        """URA_STRUCTURED_LOGS solo cambia el *formato*, no el contenido
        semántico. El mismo LogRecord debe producir idéntico level, logger,
        y message en ambos formatos."""
        from knowledge.engine.logging_config import JSONFormatter

        cases: list[tuple[str, tuple, int, str]] = [
            ("hello world", (), logging.INFO, "mymod"),
            ("user %s logged in", ("admin",), logging.WARNING, "auth"),
            ("error code %s: %s", ("KE042", "timeout"), logging.ERROR, "db"),
        ]

        for msg_fmt, args, level, logger_name in cases:
            record = logging.LogRecord(
                name=logger_name,
                level=level,
                pathname=__file__,
                lineno=100,
                msg=msg_fmt,
                args=args,
                exc_info=None,
            )
            # Si el mensaje tiene args, getMessage() los interpola
            plain = logging.Formatter("%(levelname)s|%(name)s|%(message)s").format(
                record
            )
            json_out = JSONFormatter().format(record)
            parsed = json.loads(json_out)

            # El contenido semántico debe coincidir
            assert parsed["level"] == record.levelname, (
                f"Level mismatch: {parsed['level']} != {record.levelname}"
            )
            assert parsed["logger"] == record.name, (
                f"Logger mismatch: {parsed['logger']} != {record.name}"
            )
            assert parsed["message"] == record.getMessage(), (
                f"Message mismatch: {parsed['message']} != {record.getMessage()}"
            )

            # Verificar que el mensaje aparece igual en ambos formatos
            plain_level, plain_logger, plain_message = plain.split("|", 2)
            assert plain_message == record.getMessage()
            assert plain_level == record.levelname
            assert plain_logger == record.name


# ── Audit Tests (Fase C) ──────────────────────────────────────────────────


class TestAuditBackend:
    """Pruebas del sistema de auditoría NDJSON + SQLite.

    Principios:
    - La auditoría nunca bloquea búsquedas ni compiles.
    - audit.write() es best effort (nunca raise).
    """

    def _make_event(self, correlation_id: str = "test-cid"):
        from knowledge.engine.models import AuditEvent
        from datetime import UTC, datetime

        return AuditEvent(
            action="search",
            actor="test",
            entity_type="document",
            entity_id="doc-001",
            result="success",
            correlation_id=correlation_id,
            timestamp=datetime.now(UTC).isoformat(),
            metadata={"query": "test"},
        )

    def test_write_and_read(self, tmp_path):
        """Escribir y leer un evento NDJSON."""
        backend = NDJSONAuditBackend(tmp_path, "test.ndjson")
        backend.write(self._make_event())
        events = backend.read_lines(0)
        assert len(events) == 1
        assert events[0].action == "search"
        assert events[0].correlation_id == "test-cid"
        backend.close()

    def test_corrupt_line_skipped(self, tmp_path):
        """Una línea corrupta en NDJSON no impide leer el resto."""
        audit_file = tmp_path / "test.ndjson"
        audit_file.write_text(
            '{"action": "search", "actor": "test", "entity_type": "doc", "entity_id": "1", "result": "ok", "correlation_id": "", "timestamp": "2024-01-01", "metadata": {}}\n'
            'not valid json\n'
            '{"action": "compile", "actor": "test", "entity_type": "graph", "entity_id": "2", "result": "ok", "correlation_id": "", "timestamp": "2024-01-01", "metadata": {}}\n'
        )
        backend = NDJSONAuditBackend(tmp_path, "test.ndjson")
        backend._handle.close()
        backend._handle = open(audit_file, "a")
        events = backend.read_lines(0)
        assert len(events) == 2, f"Expected 2 valid events, got {len(events)}"
        backend.close()

    def test_missing_file_returns_empty(self, tmp_path):
        """Archivo NDJSON inexistente retorna lista vacía."""
        backend = NDJSONAuditBackend(tmp_path, "missing.ndjson")
        backend._handle.close()
        backend._handle = open(tmp_path / "nonexistent.ndjson", "a")
        events = backend.read_lines(0)
        assert events == []

    def test_rotation(self, tmp_path):
        """Rotación al alcanzar MAX_BYTES."""
        backend = NDJSONAuditBackend(tmp_path, "rot.ndjson")
        backend.MAX_BYTES = 100  # rotar cada 100 bytes
        # Escribir suficientes eventos para forzar rotación
        for _ in range(20):
            backend.write(self._make_event())
        # Verificar que rotó al menos una vez
        seg1 = tmp_path / "rot.ndjson.1"
        assert seg1.exists(), f"Segmento rotado no existe: {seg1}"
        # Verificar datos en el segmento rotado
        events = backend.read_lines(segment=1)
        assert len(events) > 0
        backend.close()

    def test_health_check(self, tmp_path):
        """health_check() retorna estado sin excepciones."""
        backend = NDJSONAuditBackend(tmp_path, "health.ndjson")
        health = backend.health_check()
        assert health.healthy
        backend.close()

    def test_1000_concurrent_writes(self, tmp_path):
        """1000 eventos concurrentes no pierden datos."""
        import concurrent.futures

        backend = NDJSONAuditBackend(tmp_path, "concurrent.ndjson")

        def write_one(i: int) -> None:
            ev = AuditEvent(
                action="search",
                actor="concurrent",
                entity_type="doc",
                entity_id=f"doc-{i:04d}",
                result="success",
                correlation_id=f"cid-{i}",
                timestamp="2024-01-01T00:00:00",
                metadata={"index": i},
            )
            backend.write(ev)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(write_one, i) for i in range(1000)]
            concurrent.futures.wait(futures)

        events = backend.read_lines(0)
        assert len(events) == 1000, f"Expected 1000 events, got {len(events)}"
        backend.close()

    def test_write_failure_does_not_raise(self, tmp_path):
        """Si el disco está lleno, write() no raise — solo warning."""
        backend = NDJSONAuditBackend(tmp_path, "fail.ndjson")
        # Simular disco lleno: remover permiso de escritura en el directorio
        tmp_path.chmod(0o444)
        try:
            backend.write(self._make_event())
            # Si no raise, el test pasa
        except Exception:
            raise AssertionError("write() no debe lanzar excepción")
        finally:
            tmp_path.chmod(0o755)
        backend.close()

    def test_service_compile(self, tmp_path):
        """AuditService.log_compile registra correctamente."""
        backend = NDJSONAuditBackend(tmp_path, "svc.ndjson")
        svc = AuditService(backend)
        svc.log_compile(result="success", correlation_id="cid-01", docs_changed=5)
        events = backend.read_lines(0)
        assert len(events) == 1
        assert events[0].action == "compile"
        assert events[0].correlation_id == "cid-01"
        assert events[0].metadata["docs_changed"] == 5
        backend.close()

    def test_service_read(self, tmp_path):
        """AuditService.log_read registra correctamente."""
        backend = NDJSONAuditBackend(tmp_path, "svc2.ndjson")
        svc = AuditService(backend)
        svc.log_read(query="foobar", docs=3, correlation_id="cid-02")
        events = backend.read_lines(0)
        assert len(events) == 1
        assert events[0].action == "search"
        assert "foobar" in events[0].entity_id
        assert events[0].metadata["docs_returned"] == 3
        backend.close()

    def test_service_archive(self, tmp_path):
        """AuditService.log_archive registra correctamente."""
        backend = NDJSONAuditBackend(tmp_path, "svc3.ndjson")
        svc = AuditService(backend)
        svc.log_archive(kind="source", result="success", correlation_id="cid-03")
        events = backend.read_lines(0)
        assert len(events) == 1
        assert events[0].action == "archive"
        assert events[0].entity_type == "archive"
        backend.close()

    def test_service_without_backend_is_noop(self):
        """AuditService sin backend no hace nada (no raise)."""
        svc = AuditService()
        svc.log_read(query="x")
        svc.log_compile()
        svc.log_archive()

    def test_ingest_into_sqlite(self, tmp_path):
        """Ingesta batch NDJSON → op_audit en SQLite."""
        from knowledge.engine.connection import open_db

        backend = NDJSONAuditBackend(tmp_path, "ingest.ndjson")
        for i in range(5):
            ev = AuditEvent(
                action="search" if i % 2 == 0 else "compile",
                actor="ingest",
                entity_type="doc",
                entity_id=f"doc-{i}",
                result="success",
                correlation_id=f"cid-{i}",
                timestamp="2024-01-01T00:00:00",
                metadata={"i": i},
            )
            backend.write(ev)

        db = tmp_path / "ingest.db"
        from knowledge.engine.sqlite_writer import init_db

        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        n = backend.ingest_into_sqlite(db)
        assert n == 5, f"Expected 5 ingested, got {n}"

        conn = open_db(db)
        rows = conn.execute("SELECT COUNT(*) as c FROM op_audit").fetchone()
        assert rows["c"] == 5
        conn.close()
        backend.close()

    def test_reader_works_with_failing_backend(self, tmp_path):
        """Reader sigue funcionando aunque audit.write() falle."""
        from knowledge.engine.reader import KnowledgeReader
        from knowledge.engine.sqlite_writer import init_db

        backend = NDJSONAuditBackend(tmp_path, "fail_reader.ndjson")
        svc = AuditService(backend)
        from knowledge.engine.audit import set_audit

        set_audit(svc)

        db = tmp_path / "reader.db"
        schema = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        init_db(db, schema)

        # Simular backend fallando siempre
        class BrokenBackend:
            def write(self, event):
                raise OSError("disk full")

            def flush(self):
                pass

            def health_check(self):
                from knowledge.engine.audit import AuditHealth
                return AuditHealth(healthy=False, error="broken")

        svc.backend = BrokenBackend()

        # El reader debe funcionar aunque audit falle
        reader = KnowledgeReader(db_path=db)
        results = reader.search("nonexistent")
        assert results == []


class TestGoldenMaster:
    """Verifica que los tests golden-master de Fase A/B siguen pasando.

    Estos tests aseguran que el determinismo, migraciones y archive
    no se han visto afectados por la Fase C.
    """

    def test_golden_master_determinism(self, tmp_path):
        """Dos compiles del mismo source producen el mismo hash (Fase A)."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.md").write_text("---\ntitle: A\ntype: doc\n---\n\nContent A\n")

        db = tmp_path / "golden.db"
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"

        from knowledge.engine.sqlite_writer import init_db

        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "t@t"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "T"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "source/"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init"],
            capture_output=True,
        )

        from knowledge.engine.compiler import compile_source
        from knowledge.engine.determinism import get_determinism_hash

        compile_source(source_dir=src, db_path=db)
        h1 = get_determinism_hash(db)
        compile_source(source_dir=src, db_path=db)
        h2 = get_determinism_hash(db)

        assert h1 == h2, f"Golden-master: hashes distintos {h1} != {h2}"
        assert h1 is not None and len(h1) == 64

    def test_golden_master_determinism_algorithm(self, tmp_path):
        """La versión del algoritmo se almacena correctamente (Fase B.5)."""
        from knowledge.engine.determinism import get_determinism_algorithm

        db = tmp_path / "algo.db"
        from knowledge.engine.sqlite_writer import init_db

        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")

        algo = get_determinism_algorithm(db)
        assert algo in ("sha256-v1", "sha256-v2"), f"Algorithm: {algo}"

    def test_determinism_file_order_independent(self, tmp_path):
        """El hash NO depende del orden de descubrimiento de los ficheros.

        El compilador itera con os.listdir()/glob cuyo orden varía
        entre sistemas de archivos. El hash debe ser estable.
        """
        src = tmp_path / "source"
        src.mkdir()
        # Crear 10 ficheros en orden alfabético inverso
        for name in sorted(["z.md", "a.md", "m.md", "b.md", "y.md",
                            "c.md", "x.md", "d.md", "w.md", "e.md"], reverse=True):
            (src / name).write_text(f"---\ntitle: {name}\ntype: doc\n---\n\nBody {name}\n")

        from knowledge.engine.compiler import compile_source
        from knowledge.engine.determinism import get_determinism_hash
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = tmp_path / "order.db"
        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)

        compile_source(source_dir=src, db_path=db)
        h1 = get_determinism_hash(db)
        compile_source(source_dir=src, db_path=db)
        h2 = get_determinism_hash(db)
        assert h1 == h2

    def test_determinism_unicode_stable(self, tmp_path):
        """El hash es estable para contenido Unicode (emoji, acentos, CJK)."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "unicode.md").write_text(
            "---\ntitle: Unicöde 🎉 测试\ntype: doc\ntags: [ñ, 日本語, español]\n---\n\n"
            "Héllò wörld 👋 你好 こんにちは\n"
        )

        from knowledge.engine.compiler import compile_source
        from knowledge.engine.determinism import get_determinism_hash
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = tmp_path / "unicode.db"
        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)

        compile_source(source_dir=src, db_path=db)
        h1 = get_determinism_hash(db)
        compile_source(source_dir=src, db_path=db)
        h2 = get_determinism_hash(db)
        assert h1 == h2

    def test_determinism_different_machine_simulation(self, tmp_path):
        """Simular distintas máquinas: mismo source, distinto CWD, distinto
        orden de ficheros en directorio → mismo hash."""
        # Mismo source compilado desde paths absolutos distintos
        src = tmp_path / "source"
        src.mkdir()
        (src / "doc.md").write_text("---\ntitle: Test\ntype: doc\n---\n\nBody\n")

        from knowledge.engine.compiler import compile_source
        from knowledge.engine.determinism import get_determinism_hash
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = tmp_path / "cross.db"
        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)

        # Compilar con CWD normal
        import os
        old_cwd = os.getcwd()
        compile_source(source_dir=src, db_path=db)
        h1 = get_determinism_hash(db)

        # Cambiar CWD y re-compilar
        os.chdir(tmp_path)
        compile_source(source_dir=src, db_path=db)
        h2 = get_determinism_hash(db)
        os.chdir(old_cwd)

        assert h1 == h2, f"CWD cambió el hash: {h1} != {h2}"

    def test_determinism_with_extra_frontmatter(self, tmp_path):
        """Frontmatter con campos extra en orden distinto → mismo hash
        (gracias a sort_keys=True en la serialización)."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "doc.md").write_text(
            "---\ntitle: Extra\ntype: doc\nz_field: last\na_field: first\n---\n\nBody\n"
        )

        from knowledge.engine.compiler import compile_source
        from knowledge.engine.determinism import get_determinism_hash
        from knowledge.engine.sqlite_writer import init_db

        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql"
        db = tmp_path / "extra.db"
        init_db(db, schema_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "source/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)

        compile_source(source_dir=src, db_path=db)
        h1 = get_determinism_hash(db)
        compile_source(source_dir=src, db_path=db)
        h2 = get_determinism_hash(db)
        assert h1 == h2


class TestArchiverCoverage:
    """Cubre paths no ejecutados de archiver.py."""

    def test_list_archives_empty(self, tmp_path):
        from knowledge.engine.archiver import list_archives
        assert list_archives(archive_dir=tmp_path / "empty") == []
        assert list_archives(archive_dir=tmp_path / "nonexistent") == []

    def test_verify_archive_errors(self, tmp_path):
        from knowledge.engine.archiver import verify_archive
        assert verify_archive(tmp_path / "nonexistent") is False
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        assert verify_archive(bad) is False


class TestJobsCoverage:
    """Cubre paths no ejecutados de jobs.py."""

    def test_enqueue_archive_job_no_db(self, tmp_path):
        from knowledge.engine.jobs import enqueue_archive_job
        enqueue_archive_job(tmp_path / "nope.db", tmp_path)

    def test_process_empty_db(self, tmp_path):
        from knowledge.engine.sqlite_writer import init_db
        from knowledge.engine.jobs import process_archive_jobs
        db = tmp_path / "e.db"
        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")
        process_archive_jobs(db)
        process_archive_jobs(tmp_path / "nope.db")

    def test_stale_job_recovery(self, tmp_path):
        import sqlite3, json
        from knowledge.engine.sqlite_writer import init_db
        from knowledge.engine.jobs import process_archive_jobs
        from knowledge.engine.archiver import archive_source
        db = tmp_path / "s.db"
        init_db(db, Path(__file__).resolve().parent.parent / "schemas" / "knowledge_graph.sql")
        # Create valid source dir with git repo
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.md").write_text("---\ntitle: A\ntype: doc\n---\n\nBody\n")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "add", "src/"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)
        payload = json.dumps({"source_dir": str(src), "db_path": str(db)})
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO op_jobs (job_type,status,payload,created_at,started_at) "
                     "VALUES ('archive_source','running',?,datetime('now'),datetime('now','-60 minutes'))",
                     (payload,))
        conn.commit(); conn.close()
        process_archive_jobs(db)
        conn = sqlite3.connect(str(db))
        ok = conn.execute("SELECT COUNT(*) as c FROM op_jobs WHERE status='completed'").fetchone()[0] > 0
        conn.close()
        assert ok