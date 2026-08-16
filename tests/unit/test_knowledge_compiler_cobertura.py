"""Cobertura 100x100 de knowledge/engine/compiler.py (TASK-20260815-003).

Cubre el pipeline DAG (scan → parse → validate → write → sync/audit) y
todas las ramas de los helpers internos usando mocks sqlite-free.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.compiler import (
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
    CompileContext,
    CompileError,
    CompileFeatures,
    CompileMetadata,
    CompileOptions,
    CompileResult,
    CompileStage,
    Document,
    Frontmatter,
    KnowledgeObject,
    Snapshot,
    SourceObject,
)

DB_PATH = "/tmp/db.sqlite"


def _source_object(path: str = "docs/a.md", content: bytes = b"# A") -> SourceObject:
    return SourceObject(
        id=path,
        path=path,
        kind="markdown",
        content_sha256="abc123",
        size=len(content),
        content=content,
    )


def _snapshot() -> Snapshot:
    return Snapshot(sources=(_source_object(),), taken_at="2026-01-01T00:00:00")


def _document() -> Document:
    return Document(
        doc_id="doc1",
        doc_type="note",
        path="docs/a.md",
        content_sha256="abc123",
        frontmatter=Frontmatter(title="A"),
        body="content",
    )


def _knowledge_object() -> KnowledgeObject:
    return KnowledgeObject(document=_document())


def _error() -> CompileError:
    return CompileError(code="KE001", document="docs/a.md", stage="compiler")


def _compile_result(success: bool = True) -> CompileResult:
    return CompileResult(
        success=success,
        graph_version=1,
        source_commit="HEAD",
        compiler_version="0.1.0",
        documents_total=1,
        documents_changed=1,
        run_id=7,
        stage=CompileStage.DONE.value if success else CompileStage.FAILED.value,
    )


def _metadata() -> CompileMetadata:
    return CompileMetadata(
        source_commit="HEAD",
        features=CompileFeatures(parser_version="0.1.0"),
        correlation_id="cid",
    )


def _options() -> CompileOptions:
    return CompileOptions(source_dir=".", db_path=DB_PATH)


class TestCompilarDefaults:
    def test_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: Path("/home/test"))
        src, db = _compilar_defaults(None, None)
        assert src.name == "source"
        assert db == Path("/home/test/URA/ura_ia_1972/knowledge/knowledge.db")

    def test_paths(self, tmp_path: Path) -> None:
        src, db = _compilar_defaults(tmp_path / "src", tmp_path / "k.db")
        assert src == tmp_path / "src"
        assert db == tmp_path / "k.db"


class TestEtapaScan:
    def test_early_return_sin_cambios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        snap = _snapshot()
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([], snap, [], []),
        )
        changed, snapshot, _errs, _warns, _deleted, early = _etapa_scan(
            _metadata(), _options(), snap, Path("src"), "0.1.0"
        )
        assert early is not None
        assert early.success is True
        assert early.documents_changed == 0
        assert early.stage == CompileStage.DONE.value
        assert changed == []
        assert snapshot is snap

    def test_con_cambios_y_deleted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        deleted_so = _source_object(path="docs/borrado.md")
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([_source_object()], _snapshot(), [_error()], [deleted_so]),
        )
        changed, _snap, errs, warns, deleted, early = _etapa_scan(
            _metadata(), _options(), None, Path("src"), "0.1.0"
        )
        assert early is None
        assert len(changed) == 1
        assert len(errs) == 1
        assert len(warns) == 1
        assert warns[0].code == "KE207"
        assert deleted == [deleted_so]

    def test_sin_previous_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([_source_object()], _snapshot(), [], []),
        )
        _, _snap, errs, warns, deleted, early = _etapa_scan(
            _metadata(), _options(), None, Path("src"), "0.1.0"
        )
        assert early is None
        assert errs == []
        assert warns == []
        assert deleted == []


class TestEtapaParsing:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source", lambda so: _knowledge_object()
        )
        objects = _etapa_parsing([_source_object()], [])
        assert objects == [_knowledge_object()]

    def test_parse_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = _error()
        monkeypatch.setattr("knowledge.engine.compiler.parse_source", lambda so: err)
        errors: list[CompileError] = []
        objects = _etapa_parsing([_source_object()], errors)
        assert objects == []
        assert errors == [err]


class TestEtapaValidacion:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch",
            lambda objs: ([_knowledge_object()], [_error()], [_error()]),
        )
        valid, errs, warns = _etapa_validacion([_knowledge_object()])
        assert valid == [_knowledge_object()]
        assert errs == [_error()]
        assert warns == [_error()]


class TestEtapaCompilacion:
    def test_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = _compile_result()
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source", lambda so: _knowledge_object()
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch",
            lambda objs: (objs, [], []),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile",
            lambda **kw: result,
        )
        meta = _metadata()
        opts = _options()
        snap = _snapshot()
        write_result, valid, deleted_ids = _etapa_compilacion(
            meta, opts, [_source_object()], [], [], [], snap, Path(DB_PATH), None
        )
        assert write_result is result
        assert valid == [_knowledge_object()]
        assert deleted_ids == []

    def test_con_deleted_y_previous(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = _compile_result()
        monkeypatch.setattr("knowledge.engine.compiler.parse_source", lambda so: _knowledge_object())
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch", lambda objs: (objs, [], [])
        )
        monkeypatch.setattr("knowledge.engine.compiler.apply_compile", lambda **kw: result)
        _, _, deleted_ids = _etapa_compilacion(
            _metadata(),
            _options(),
            [_source_object()],
            [],
            [],
            [_source_object(path="docs/d.md")],
            _snapshot(),
            Path(DB_PATH),
            _snapshot(),
        )
        assert len(deleted_ids) == 1
        assert len(deleted_ids[0]) == 12


class TestCompilarFinal:
    def test_success_sync_y_audit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy: list[str] = []
        monkeypatch.setattr(
            "knowledge.engine.compiler._sync_semantica", lambda *a, **k: spy.append("sync")
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._auditar", lambda *a, **k: spy.append("audit")
        )
        final = _compilar_final(
            _compile_result(True),
            _metadata(),
            valid_objects=[_knowledge_object()],
            deleted_ids=[],
            documents_total=1,
            source_dir=Path("src"),
            snapshot=_snapshot(),
            db_path=Path(DB_PATH),
            correlation_id="cid",
            duration=0.1,
        )
        assert final.success is True
        assert final.stage == CompileStage.DONE.value
        assert final.duration_ms == 100.0
        assert spy == ["sync", "audit"]

    def test_failure_solo_audit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy: list[str] = []
        monkeypatch.setattr(
            "knowledge.engine.compiler._sync_semantica", lambda *a, **k: spy.append("sync")
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._auditar", lambda *a, **k: spy.append("audit")
        )
        final = _compilar_final(
            _compile_result(False),
            _metadata(),
            valid_objects=[],
            deleted_ids=[],
            documents_total=0,
            source_dir=Path("src"),
            snapshot=_snapshot(),
            db_path=Path(DB_PATH),
            correlation_id="cid",
            duration=0.5,
        )
        assert final.success is False
        assert final.stage == CompileStage.FAILED.value
        assert spy == ["audit"]


class TestSyncSemantica:
    def test_synced_positivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents",
            lambda **kw: 3,
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout="abc123\n"),
        )
        calls: list[str] = []
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot",
            lambda snap, commit: calls.append(commit),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: calls.append("det")
        )
        _sync_semantica(
            Path(DB_PATH),
            [_knowledge_object()],
            [],
            _compile_result(True),
            _snapshot(),
            Path("src"),
        )
        assert calls == ["abc123", "det"]

    def test_synced_cero_sin_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 0
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout=""),
        )
        calls: list[str] = []
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot",
            lambda snap, commit: calls.append(commit),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: calls.append("det")
        )
        _sync_semantica(
            Path(DB_PATH), [], ["id1"], _compile_result(True), _snapshot(), Path("src")
        )
        assert calls == ["HEAD", "det"]

    def test_save_snapshot_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 0
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("git fail")),
        )
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot",
            lambda snap, commit: (_ for _ in ()).throw(RuntimeError("fs fail")),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None
        )
        _sync_semantica(
            Path(DB_PATH), [], [], _compile_result(True), _snapshot(), Path("src")
        )


class TestAuditar:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        logged: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(
                log_compile=lambda **kw: logged.append(kw),
            ),
        )
        _auditar(_compile_result(True), "cid", 0.25)
        assert logged[0]["result"] == "success"
        assert logged[0]["duration_ms"] == 250

    def test_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        logged: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_compile=lambda **kw: logged.append(kw)),
        )
        _auditar(_compile_result(False), "cid", 1.0)
        assert logged[0]["result"] == "failure"

    def test_exception_ignorada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: (_ for _ in ()).throw(RuntimeError("audit down")),
        )
        _auditar(_compile_result(True), "cid", 0.1)


class TestStreamParsear:
    def test_mixto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        err = _error()
        so_ok = _source_object(path="docs/ok.md")
        so_bad = _source_object(path="docs/bad.md")
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_source_stream",
            lambda src: iter([err, so_ok, so_bad]),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source",
            lambda so: _knowledge_object() if so.path == "docs/ok.md" else err,
        )
        errors: list[CompileError] = []
        objects, count = _stream_parsear(Path("src"), errors)
        assert count == 2
        assert objects == [_knowledge_object()]
        assert errors == [err, err]


class TestResultadoCompile:
    def test_success(self) -> None:
        r = _resultado_compile(
            _compile_result(True), _metadata(), "0.1.0", 5, 0.25
        )
        assert r.success is True
        assert r.documents_total == 5
        assert r.duration_ms == 250.0
        assert r.stage == CompileStage.DONE.value

    def test_failure(self) -> None:
        r = _resultado_compile(
            _compile_result(False), _metadata(), "0.1.0", 0, 0.5
        )
        assert r.success is False
        assert r.stage == CompileStage.FAILED.value


class TestResolveDeletedIds:
    def test_sin_previous(self) -> None:
        assert _resolve_deleted_ids([_source_object()], None) == []

    def test_sin_deleted(self) -> None:
        assert _resolve_deleted_ids([], _snapshot()) == []

    def test_ambos(self) -> None:
        ids = _resolve_deleted_ids([_source_object(path="docs/d.md")], _snapshot())
        assert len(ids) == 1
        assert len(ids[0]) == 12


class TestCtxStage:
    def test_snapshot(self) -> None:
        snap = _snapshot()
        ctx = _ctx_stage(_metadata(), _options(), CompileStage.PARSING, snap)
        assert ctx.stage == CompileStage.PARSING
        assert ctx.snapshot is snap

    def test_errores_warnings(self) -> None:
        errs = (_error(),)
        ctx = _ctx_stage(
            _metadata(), _options(), CompileStage.WRITING, errors=errs, warnings=()
        )
        assert ctx.stage == CompileStage.WRITING
        assert ctx.errors == errs
        assert ctx.warnings == ()


class TestWarningsDeletados:
    def test_vacio(self) -> None:
        assert _warnings_deletados([]) == []

    def test_con_deleted(self) -> None:
        warns = _warnings_deletados([_source_object(path="docs/borrado.md")])
        assert len(warns) == 1
        assert warns[0].code == "KE207"
        assert warns[0].category == "permanent"


class TestRecordDeterminismHash:
    def test_delega(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple] = []
        monkeypatch.setattr(
            "knowledge.engine.determinism.record_determinism_hash",
            lambda db, rid: calls.append((db, rid)),
        )
        _record_determinism_hash(Path(DB_PATH), 7)
        assert calls == [(Path(DB_PATH), 7)]


class TestCompileSource:
    def test_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([_source_object()], _snapshot(), [], []),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source", lambda so: _knowledge_object()
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch", lambda objs: (objs, [], [])
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(True)
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 1
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout="abc\n"),
        )
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot", lambda snap, commit: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None
        )
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_compile=lambda **kw: None),
        )
        result = compile_source(
            source_dir=Path("src"),
            db_path=Path(DB_PATH),
            compiler_version="0.1.0",
            correlation_id="cid",
        )
        assert result.success is True
        assert result.graph_version == 1
        assert result.documents_changed == 1
        assert result.duration_ms >= 0.0

    def test_early_sin_cambios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        snap = _snapshot()
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([], snap, [], []),
        )
        result = compile_source(
            source_dir=Path("src"),
            db_path=Path(DB_PATH),
            previous_snapshot=snap,
        )
        assert result.success is True
        assert result.documents_changed == 0
        assert result.stage == CompileStage.DONE.value

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: Path("/home/test"))
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([], _snapshot(), [], []),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(True)
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 0
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout=""),
        )
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot", lambda snap, commit: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None
        )
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_compile=lambda **kw: None),
        )
        result = compile_source(previous_snapshot=None)
        assert result.success is True


class TestCompileSourceStreaming:
    def test_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_source_stream",
            lambda src: iter([_source_object()]),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.take_snapshot_fn",
            lambda src: _snapshot(),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source", lambda so: _knowledge_object()
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch", lambda objs: (objs, [], [])
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(True)
        )
        result = compile_source_streaming(
            source_dir=Path("src"), db_path=Path(DB_PATH)
        )
        assert result.success is True
        assert result.documents_total == 1
        assert result.stage == CompileStage.DONE.value

    def test_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_source_stream",
            lambda src: iter([_error()]),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.take_snapshot_fn",
            lambda src: _snapshot(),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch", lambda objs: (objs, [], [])
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(False)
        )
        result = compile_source_streaming(
            source_dir=Path("src"), db_path=Path(DB_PATH)
        )
        assert result.success is False
        assert result.stage == CompileStage.FAILED.value


class TestCompileIncremental:
    def test_con_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        snap = _snapshot()
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.load_snapshot", lambda: snap
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([], snap, [], []),
        )
        result = compile_incremental(source_dir=Path("src"), db_path=Path(DB_PATH))
        assert result.success is True
        assert result.documents_changed == 0

    def test_sin_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.load_snapshot", lambda: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([_source_object()], _snapshot(), [], []),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.parse_source", lambda so: _knowledge_object()
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.validate_batch", lambda objs: (objs, [], [])
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(True)
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 0
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout=""),
        )
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot", lambda snap, commit: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None
        )
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_compile=lambda **kw: None),
        )
        result = compile_incremental(source_dir=Path("src"), db_path=Path(DB_PATH))
        assert result.success is True
        assert result.documents_changed == 1

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: Path("/home/test"))
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.load_snapshot", lambda: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.scan_incremental",
            lambda prev, src: ([], _snapshot(), [], []),
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.apply_compile", lambda **kw: _compile_result(True)
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.sync_documents", lambda **kw: 0
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout=""),
        )
        monkeypatch.setattr(
            "knowledge.engine.snapshot_store.save_snapshot", lambda snap, commit: None
        )
        monkeypatch.setattr(
            "knowledge.engine.compiler._record_determinism_hash", lambda *a, **k: None
        )
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_compile=lambda **kw: None),
        )
        result = compile_incremental()
        assert result.success is True


def test_ctx_compatible() -> None:
    """CompileContext construido por _ctx_stage es inmutable y usable."""
    ctx = _ctx_stage(_metadata(), _options(), CompileStage.DONE)
    assert isinstance(ctx, CompileContext)
    assert ctx.options.db_path == DB_PATH
