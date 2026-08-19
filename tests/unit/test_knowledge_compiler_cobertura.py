"""Tests de cobertura para knowledge/engine/compiler.py."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from knowledge.engine.compiler import (
    CompileStage,
    _auditar,
    _compilar_defaults,
    _compilar_final,
    _ctx_stage,
    _etapa_compilacion,
    _etapa_parsing,
    _etapa_scan,
    _etapa_validacion,
    _record_determinism_hash,
    _resolve_deleted_ids,
    _resultado_compile,
    _stream_parsear,
    _sync_semantica,
    _warnings_deletados,
    compile_incremental,
    compile_source,
    compile_source_streaming,
)
from knowledge.engine.models import (
    CompileError,
    CompileFeatures,
    CompileMetadata,
    CompileOptions,
    CompileResult,
    Snapshot,
    SourceObject,
    doc_id_from_path,
)
from knowledge.engine.sqlite_writer import init_db

SCHEMA = Path("schemas/knowledge_graph.sql")


def _mk_source(tmp_path: Path, *names: str) -> Path:
    src = tmp_path / "source"
    docs = src / "docs"
    docs.mkdir(parents=True)
    for name in names:
        (docs / f"{name}.md").write_text(
            f"---\ntitle: {name}\ndoc_type: doc\n---\nContenido de prueba para {name}."
        )
    return src


def _mk_db(tmp_path: Path) -> Path:
    db = tmp_path / "k.db"
    init_db(db, SCHEMA)
    return db


# ── compile_source E2E ──────────────────────────────────────────────────────


def test_compile_source_ok(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa", "bbb")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    result = compile_source(source_dir=src, db_path=db, correlation_id="cid-e2e")
    assert result.success is True
    assert result.documents_total == 2
    assert result.stage == CompileStage.DONE.value
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
    conn.close()
    assert n == 2


def test_compile_source_con_errores(tmp_path, monkeypatch) -> None:
    src = tmp_path / "source"
    docs = src / "docs"
    docs.mkdir(parents=True)
    (docs / "ok.md").write_text("---\ntitle: OK\ndoc_type: doc\n---\nContenido ok.")
    (docs / "malo.md").write_text("---\ntitle: Malo\ndoc_type: tipo_inexistente_zz\n---\nContenido malo.")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    result = compile_source(source_dir=src, db_path=db)
    assert result.documents_total == 2
    assert any(e.code == "KE003" for e in result.errors)


def test_compile_source_incremental_sin_cambios(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    raw = src.joinpath("docs/aaa.md").read_bytes()
    prev = Snapshot(
        sources=(
            SourceObject(
                id="docs/aaa.md",
                path="docs/aaa.md",
                kind="markdown",
                content_sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
            ),
        ),
        taken_at="2026-01-01",
    )
    result = compile_source(source_dir=src, db_path=db, previous_snapshot=prev)
    assert result.success is True
    assert result.documents_total == 0
    assert result.stage == CompileStage.DONE.value


def test_compile_source_incremental_con_cambios(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    prev = Snapshot(
        sources=(
            SourceObject(id="old", path="docs/zzz-old.md", kind="markdown", content_sha256="h", size=1),
        ),
        taken_at="2026-01-01",
    )
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    result = compile_source(source_dir=src, db_path=db, previous_snapshot=prev)
    assert result.documents_total == 1
    assert any(w.code == "KE207" for w in result.warnings)


def test_compilar_defaults(tmp_path) -> None:
    source_dir, db_path = _compilar_defaults(None, None)
    assert source_dir.name == "source"
    assert db_path.name == "knowledge.db"
    assert _compilar_defaults(tmp_path, tmp_path) == (tmp_path, tmp_path)


# ── compile_source_streaming ────────────────────────────────────────────────


def test_compile_source_streaming_ok(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa", "bbb")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    result = compile_source_streaming(source_dir=src, db_path=db)
    assert result.success is True
    assert result.documents_total == 2


def test_stream_parsear_con_error(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    monkeypatch.setattr(
        "knowledge.engine.compiler.parse_source",
        lambda so: CompileError(code="KE999", document=so.path, stage="parser", message="x", category="permanent"),
    )
    errors: list[CompileError] = []
    objects, changed = _stream_parsear(src, errors)
    assert changed == 1
    assert objects == []
    assert errors[0].code == "KE999"


def test_resultado_compile_success_y_failure() -> None:
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    ok = CompileResult(success=True, graph_version=3, source_commit="HEAD", compiler_version="1", documents_total=5, documents_changed=5, stage="", )
    res = _resultado_compile(ok, meta, "1", 5, 0.1)
    assert res.stage == CompileStage.DONE.value
    fail = CompileResult(success=False, graph_version=0, source_commit="HEAD", compiler_version="1", documents_total=5, documents_changed=0, stage="", )
    res2 = _resultado_compile(fail, meta, "1", 5, 0.1)
    assert res2.stage == CompileStage.FAILED.value
    assert res2.duration_ms == 100


# ── Etapas internas ─────────────────────────────────────────────────────────


def test_etapa_scan_early(tmp_path) -> None:
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    opts = CompileOptions(source_dir=str(tmp_path), db_path="x", compiler_version="1")
    prev = Snapshot(sources=(), taken_at="2026-01-01")
    _, _, _, _, _, early = _etapa_scan(
        meta, opts, prev, tmp_path, "1"
    )
    assert early is not None
    assert early.documents_total == 0
    assert early.stage == CompileStage.DONE.value


def test_etapa_scan_con_cambios(tmp_path) -> None:
    src = _mk_source(tmp_path, "aaa")
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    opts = CompileOptions(source_dir=str(src), db_path="x", compiler_version="1")
    changed, _, _, _, deleted, early = _etapa_scan(
        meta, opts, None, src, "1"
    )
    assert early is None
    assert len(changed) == 1
    assert deleted == []


def test_etapa_parsing_y_validacion(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    raw = src.joinpath("docs/aaa.md").read_bytes()
    so = SourceObject(id="s1", path="docs/aaa.md", kind="markdown", content_sha256="h", size=len(raw), content=raw)
    errors: list[CompileError] = []
    objects = _etapa_parsing([so], errors)
    assert len(objects) == 1
    valid, _, _ = _etapa_validacion(objects)
    assert len(valid) == 1


def test_etapa_parsing_con_error(tmp_path, monkeypatch) -> None:
    so = SourceObject(id="s2", path="docs/malo.md", kind="markdown", content_sha256="h", size=17, content=b"---\nfrontmatter roto")
    errors: list[CompileError] = []
    objects = _etapa_parsing([so], errors)
    assert objects == []
    assert len(errors) == 1


def test_etapa_compilacion_ok(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    db = _mk_db(tmp_path)
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    opts = CompileOptions(source_dir=str(src), db_path=str(db), compiler_version="1")
    changed, snapshot, _, _, deleted, _ = _etapa_scan(meta, opts, None, src, "1")
    result, valid, _ = _etapa_compilacion(
        meta, opts, changed, [], [], deleted, snapshot, db, None
    )
    assert result.success is True
    assert len(valid) == 1


def test_ctx_stage_con_y_sin_errores() -> None:
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    opts = CompileOptions(source_dir="x", db_path="y", compiler_version="1")
    err = CompileError(code="KE1", document="d", stage="s", message="m", category="permanent")
    ctx = _ctx_stage(meta, opts, None, CompileStage.PARSING, errors=(err,), warnings=())
    assert ctx.errors == (err,)
    ctx2 = _ctx_stage(meta, opts, None, CompileStage.WRITING)
    assert ctx2.errors == ()
    assert ctx2.warnings == ()


def test_compilar_final_success_y_failure(tmp_path, monkeypatch) -> None:
    meta = CompileMetadata(source_commit="HEAD", features=CompileFeatures(parser_version="1"))
    monkeypatch.setattr("knowledge.engine.compiler._sync_semantica", lambda *a, **k: None)
    monkeypatch.setattr("knowledge.engine.compiler._auditar", lambda *a, **k: None)
    ok = CompileResult(success=True, graph_version=2, source_commit="HEAD", compiler_version="1", documents_total=1, documents_changed=1, stage="", run_id=7)
    res = _compilar_final(
        ok, meta, valid_objects=[], deleted_ids=[], documents_total=1,
        source_dir=tmp_path, snapshot=Snapshot(sources=(), taken_at="t"), db_path=tmp_path / "k.db",
        correlation_id="c", duration=0.5,
    )
    assert res.stage == CompileStage.DONE.value
    fail = CompileResult(success=False, graph_version=0, source_commit="HEAD", compiler_version="1", documents_total=1, documents_changed=0, stage="", )
    res2 = _compilar_final(
        fail, meta, valid_objects=[], deleted_ids=[], documents_total=1,
        source_dir=tmp_path, snapshot=Snapshot(sources=(), taken_at="t"), db_path=tmp_path / "k.db",
        correlation_id="c", duration=0.5,
    )
    assert res2.stage == CompileStage.FAILED.value


def test_warnings_deletados() -> None:
    so = SourceObject(id="s3", path="docs/viejo.md", kind="markdown", content_sha256="h", size=1, content=b"x")
    warnings = _warnings_deletados([so])
    assert warnings[0].code == "KE207"
    assert _warnings_deletados([]) == []


def test_resolve_deleted_ids() -> None:
    assert _resolve_deleted_ids(None, None) == []
    assert _resolve_deleted_ids([], Snapshot(sources=(), taken_at="t")) == []
    so = SourceObject(id="s4", path="docs/aa.md", kind="markdown", content_sha256="h", size=1, content=b"x")
    ids = _resolve_deleted_ids([so], Snapshot(sources=(), taken_at="2026-01-01"))
    assert ids == [doc_id_from_path("docs/aa.md")]


def test_sync_semantica_sin_docs(tmp_path, monkeypatch) -> None:
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    _sync_semantica(db, [], [], CompileResult(success=True, graph_version=1, source_commit="HEAD", compiler_version="1", documents_total=0, documents_changed=0, stage="", run_id=1), Snapshot(sources=(), taken_at="t"), tmp_path)


def test_sync_semantica_snapshot_falla(tmp_path, monkeypatch, caplog) -> None:
    import logging

    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 1)
    monkeypatch.setattr(
        "knowledge.engine.snapshot_store.save_snapshot",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("snapshot boom")),
    )
    monkeypatch.setattr("knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None)
    with caplog.at_level(logging.WARNING):
        _sync_semantica(db, [], [], CompileResult(success=True, graph_version=1, source_commit="HEAD", compiler_version="1", documents_total=0, documents_changed=0, stage="", run_id=1), Snapshot(sources=(), taken_at="t"), tmp_path)
    assert "No se pudo persistir snapshot" in caplog.text


def test_record_determinism_hash(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.determinism.record_determinism_hash", lambda *a, **k: calls.append(a))
    _record_determinism_hash(tmp_path / "k.db", 3)
    assert calls == [(tmp_path / "k.db", 3)]


def test_auditar_ok_y_falla(tmp_path, monkeypatch) -> None:
    calls: list[dict] = []

    def _fake_audit() -> object:
        def _log(_self: object, **kw: object) -> None:
            calls.append(kw)

        return type("A", (), {"log_compile": _log})()

    monkeypatch.setattr("knowledge.engine.audit.get_audit", _fake_audit)
    _auditar(CompileResult(success=True, graph_version=1, source_commit="HEAD", compiler_version="1", documents_total=2, documents_changed=2, stage="", ), "c", 0.25)
    assert calls[0]["result"] == "success"
    assert calls[0]["duration_ms"] == 250
    monkeypatch.setattr("knowledge.engine.audit.get_audit", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    _auditar(CompileResult(success=False, graph_version=0, source_commit="HEAD", compiler_version="1", documents_total=5, documents_changed=0, stage="", ), "c", 0.1)


def test_stream_scan_error_continua(tmp_path, monkeypatch) -> None:
    err = CompileError(code="KE700", document="x", stage="scanner", message="boom", category="permanent")
    monkeypatch.setattr("knowledge.engine.compiler.scan_source_stream", lambda *a, **k: iter([err]))
    db = _mk_db(tmp_path)
    result = compile_source_streaming(source_dir=tmp_path, db_path=db)
    assert any(e.code == "KE700" for e in result.errors)


def test_compile_incremental_defaults(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("knowledge.engine.snapshot_store.load_snapshot", lambda: None)
    ok = CompileResult(success=True, graph_version=1, source_commit="HEAD", compiler_version="1",
                       documents_total=0, documents_changed=0, stage="done")
    def _fake_compile(**kw: object) -> CompileResult:
        calls.append(kw)
        return ok

    monkeypatch.setattr("knowledge.engine.compiler.compile_source", _fake_compile)
    result = compile_incremental(source_dir=None, db_path=None)
    assert result is ok
    assert str(calls[0]["source_dir"]).endswith("source")
    assert str(calls[0]["db_path"]).endswith("knowledge.db")


def test_compile_incremental_sin_snapshot(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    db = _mk_db(tmp_path)
    monkeypatch.setattr("knowledge.engine.snapshot_store.load_snapshot", lambda: None)
    monkeypatch.setattr("knowledge.engine.snapshot_store.save_snapshot", lambda *a, **k: None)
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    result = compile_incremental(source_dir=src, db_path=db)
    assert result.success is True
    assert result.documents_total == 1


def test_compile_incremental_con_snapshot(tmp_path, monkeypatch) -> None:
    src = _mk_source(tmp_path, "aaa")
    db = _mk_db(tmp_path)
    raw = src.joinpath("docs/aaa.md").read_bytes()
    monkeypatch.setattr(
        "knowledge.engine.snapshot_store.load_snapshot",
        lambda: Snapshot(
            sources=(
                SourceObject(
                    id="docs/aaa.md", path="docs/aaa.md", kind="markdown",
                    content_sha256=hashlib.sha256(raw).hexdigest(), size=len(raw),
                ),
            ),
            taken_at="t",
        ),
    )
    monkeypatch.setattr("knowledge.engine.compiler.sync_documents", lambda **kw: 0)
    result = compile_incremental(source_dir=src, db_path=db)
    assert result.documents_total == 0
