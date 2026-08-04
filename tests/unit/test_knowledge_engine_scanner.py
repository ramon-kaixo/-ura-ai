"""Tests para knowledge/engine/scanner.py — descubrimiento de SourceObjects.

Usa filesystem real en tmp_path; parchea MAX_PARSE_SIZE para no crear
archivos de 10MB.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.models import CompileError, SourceObject
from knowledge.engine.scanner import scan_incremental, scan_source, scan_source_stream, take_snapshot


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    d = tmp_path / "source"
    d.mkdir()
    (d / "a.md").write_text("---\ntitle: A\n---\ncontenido a")
    (d / "b.md").write_text("---\ntitle: B\n---\ncontenido b")
    sub = d / "sub"
    sub.mkdir()
    (sub / "c.json").write_text('{"x": 1}')
    (d / "vacio.md").write_text("")
    return d


class TestScanSource:
    def test_encuentra_archivos(self, source_dir: Path) -> None:
        sources, skipped = scan_source(source_dir)
        assert len(sources) == 3
        assert {s.path for s in sources} == {"a.md", "b.md", "sub/c.json"}
        assert skipped == []

    def test_kind_por_extension(self, source_dir: Path) -> None:
        sources, _ = scan_source(source_dir)
        kinds = {s.path: s.kind for s in sources}
        assert kinds["a.md"] == "markdown"
        assert kinds["sub/c.json"] == "json"

    def test_content_y_sha(self, source_dir: Path) -> None:
        sources, _ = scan_source(source_dir)
        s = next(x for x in sources if x.path == "a.md")
        assert s.content.startswith(b"---")
        assert len(s.content_sha256) == 64

    def test_symlink_omitido(self, source_dir: Path) -> None:
        (source_dir / "link.md").symlink_to(source_dir / "a.md")
        _sources, skipped = scan_source(source_dir)
        assert any(e.code == "KE210" for e in skipped)

    def test_archivo_grande_omitido(self, source_dir: Path) -> None:
        with mock.patch("knowledge.engine.scanner.MAX_PARSE_SIZE", 5):
            sources, skipped = scan_source(source_dir)
        assert any(e.code == "KE205" for e in skipped)
        assert len(sources) < 3

    def test_dir_no_existe(self, tmp_path: Path) -> None:
        sources, skipped = scan_source(tmp_path / "nope")
        assert sources == []
        assert skipped == []


class TestScanSourceStream:
    def test_generador(self, source_dir: Path) -> None:
        items = list(scan_source_stream(source_dir))
        assert len(items) == 3
        assert all(isinstance(i, SourceObject) for i in items)

    def test_symlink_omitido(self, source_dir: Path) -> None:
        (source_dir / "link.md").symlink_to(source_dir / "a.md")
        items = list(scan_source_stream(source_dir))
        assert len(items) == 3

    def test_yield_error_tamanio(self, source_dir: Path) -> None:
        with mock.patch("knowledge.engine.scanner.MAX_PARSE_SIZE", 5):
            items = list(scan_source_stream(source_dir))
        assert any(isinstance(i, CompileError) and i.code == "KE205" for i in items)

    def test_dir_no_existe(self, tmp_path: Path) -> None:
        assert list(scan_source_stream(tmp_path / "nope")) == []


class TestTakeSnapshot:
    def test_snapshot_sin_content(self, source_dir: Path) -> None:
        snap = take_snapshot(source_dir)
        assert len(snap.sources) == 3
        assert all(s.content == b"" for s in snap.sources)
        assert snap.taken_at

    def test_snapshot_dir_no_existe(self, tmp_path: Path) -> None:
        snap = take_snapshot(tmp_path / "nope")
        assert snap.sources == ()

    def test_snapshot_omite_symlink(self, source_dir: Path) -> None:
        (source_dir / "link.md").symlink_to(source_dir / "a.md")
        snap = take_snapshot(source_dir)
        assert len(snap.sources) == 3


class TestScanIncremental:
    def test_sin_previo_escanea_todo(self, source_dir: Path) -> None:
        changed, snap, _skipped, deleted = scan_incremental(None, source_dir)
        assert len(changed) == 3
        assert len(snap.sources) == 3
        assert deleted == []

    def test_sin_cambios(self, source_dir: Path) -> None:
        _changed, snap, _skipped, _deleted = scan_incremental(None, source_dir)
        changed2, _snap2, _, deleted2 = scan_incremental(snap, source_dir)
        assert changed2 == []
        assert deleted2 == []

    def test_detecta_cambio(self, source_dir: Path) -> None:
        _prev, snap, _, _ = scan_incremental(None, source_dir)
        (source_dir / "a.md").write_text("---\ntitle: A2\n---\nnuevo contenido")
        changed, _, _, _ = scan_incremental(snap, source_dir)
        assert [s.path for s in changed] == ["a.md"]

    def test_detecta_borrado(self, source_dir: Path) -> None:
        _prev, snap, _, _ = scan_incremental(None, source_dir)
        (source_dir / "b.md").unlink()
        _, _, _, deleted = scan_incremental(snap, source_dir)
        assert [s.path for s in deleted] == ["b.md"]

    def test_archivo_nuevo(self, source_dir: Path) -> None:
        _prev, snap, _, _ = scan_incremental(None, source_dir)
        (source_dir / "nuevo.md").write_text("nuevo")
        changed, _, _, _ = scan_incremental(snap, source_dir)
        assert [s.path for s in changed] == ["nuevo.md"]
