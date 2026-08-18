"""Tests de cobertura de knowledge/engine/archiver.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from knowledge.engine.archiver import (
    PathTraversalError,
    _archive_path,
    _calcular_sha256,
    _cargar_manifest_archivo,
    _clonar_bundle,
    _construir_manifest,
    _contar_tracked,
    _crear_bundle,
    _ensure_dir,
    _escribir_manifest,
    _git_cmd,
    _manifest_path,
    _registrar_audit_y_metricas,
    _registrar_en_db,
    _resolve_within,
    _resolver_dentro,
    _validate_source_dir,
    _verificar_git_commit,
    archive_source,
    list_archives,
    list_archives_from_db,
    restore_source,
    verify_archive,
)
from knowledge.engine.models import ArchiveManifest


def _git_repo(tmp_path: Path, filename: str = "f.txt", content: str = "hola") -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / filename).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def _arch_db(tmp_path: Path) -> Path:
    db = tmp_path / "ke.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE op_archives (id INTEGER PRIMARY KEY, kind TEXT, source_commit TEXT, "
        "manifest_path TEXT, archive_path TEXT, compressed_size INTEGER, content_sha256 TEXT, "
        "retention_days INTEGER, archived_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    return db


class TestPathValidation:
    def test_resolve_dentro(self, tmp_path) -> None:
        ok = _resolve_within(tmp_path / "a", tmp_path)
        assert ok == (tmp_path / "a").resolve()

    def test_resolve_fuera_existente(self, tmp_path) -> None:
        outside = tmp_path / ".." / "x"
        with pytest.raises(PathTraversalError):
            _resolve_within(outside, tmp_path)

    def test_resolve_fuera_no_existente(self, tmp_path) -> None:
        with pytest.raises(PathTraversalError):
            _resolve_within(tmp_path / ".." / "nope", tmp_path)

    def test_validate_source_dir_ok(self, tmp_path) -> None:
        d = tmp_path / "s"
        d.mkdir()
        assert _validate_source_dir(d) == d.resolve()

    def test_validate_source_dir_fuera(self, tmp_path) -> None:
        allowed = tmp_path / "root"
        allowed.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        with pytest.raises(PathTraversalError):
            _validate_source_dir(other, allowed_root=allowed)


class TestHelpers:
    def test_ensure_dir(self, tmp_path) -> None:
        d = tmp_path / "nuevo" / "nivel"
        assert _ensure_dir(d) == d
        assert d.is_dir()

    def test_git_cmd(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.archiver.shutil.which", lambda x: "/usr/bin/git")
        r = _git_cmd("--version", cwd=tmp_path)
        assert r.returncode == 0

    def test_manifest_path(self, tmp_path) -> None:
        assert _manifest_path(tmp_path, "source", "T1").name == "source-T1.manifest.json"

    def test_archive_path(self, tmp_path) -> None:
        assert _archive_path(tmp_path, "source", "T1").name == "source-T1.bundle"

    def test_sha256(self, tmp_path) -> None:
        f = tmp_path / "f"
        f.write_bytes(b"abc")
        assert _calcular_sha256(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class TestArchiveSource:
    def test_e2e(self, tmp_path) -> None:
        repo = _git_repo(tmp_path)
        arch_dir = tmp_path / "arch"
        db = _arch_db(tmp_path)
        manifest = archive_source(source_dir=repo, archive_dir=arch_dir, db_path=db)
        assert manifest.kind == "source"
        assert (arch_dir / f"source-{manifest.created_at}.bundle").exists()
        assert (arch_dir / f"source-{manifest.created_at}.manifest.json").exists()
        rows = list_archives_from_db(db)
        assert len(rows) == 1
        assert rows[0]["kind"] == "source"

    def test_no_es_repo(self, tmp_path) -> None:
        norepo = tmp_path / "norepo"
        norepo.mkdir()
        with pytest.raises(ValueError, match="no es un repositorio git"):
            archive_source(source_dir=norepo, archive_dir=tmp_path / "a")

    def test_verificar_git_commit(self, tmp_path) -> None:
        assert len(_verificar_git_commit(_git_repo(tmp_path))) == 40

    def test_contar_tracked(self, tmp_path) -> None:
        repo = _git_repo(tmp_path)
        assert _contar_tracked(repo) == 1

    def test_crear_bundle_error(self, tmp_path, monkeypatch) -> None:
        def _bad(*a, **k):
            return mock.Mock(returncode=1, stderr="boom")

        monkeypatch.setattr("knowledge.engine.archiver._git_cmd", _bad)
        with pytest.raises(RuntimeError, match="Error creando git bundle"):
            _crear_bundle(tmp_path, tmp_path / "x.bundle")

    def test_construir_manifest_default_retention(self) -> None:
        m = _construir_manifest("c" * 40, "T", Path("/x.bundle"), 10, "s" * 64, 1, None)
        assert m.retention_days == 90

    def test_escribir_manifest(self, tmp_path) -> None:
        m = _construir_manifest("c" * 40, "T2", tmp_path / "x.bundle", 10, "s" * 64, 1, 7)
        p = _escribir_manifest(m)
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["retention_days"] == 7

    def test_registrar_db_error_no_propaga(self, tmp_path, caplog) -> None:
        m = ArchiveManifest()
        with caplog.at_level("WARNING", logger="ura.knowledge.archiver"):
            _registrar_en_db(tmp_path / "no.db", m, tmp_path / "m.json", tmp_path / "b", 1)
        assert any("No se pudo registrar" in r.message for r in caplog.records)

    def test_audit_y_metricas_ok(self, monkeypatch) -> None:
        audit = mock.Mock()
        audit.log_archive = mock.Mock()
        monkeypatch.setitem(
            __import__("sys").modules, "knowledge.engine.audit", mock.Mock(get_audit=lambda: audit)
        )
        metric = mock.Mock()
        metric.observe = mock.Mock()
        monkeypatch.setitem(
            __import__("sys").modules, "knowledge.engine.metrics", mock.Mock(archive_duration_seconds=metric)
        )
        _registrar_audit_y_metricas("c" * 40, 1, 10, 0.0)
        audit.log_archive.assert_called_once()

    def test_audit_y_metricas_fallan(self, monkeypatch, caplog) -> None:
        monkeypatch.setitem(__import__("sys").modules, "knowledge.engine.audit", None)
        monkeypatch.setitem(__import__("sys").modules, "knowledge.engine.metrics", None)
        _registrar_audit_y_metricas("c" * 40, 1, 10, 0.0)  # no lanza


class TestVerifyArchive:
    def _manifest_ok(self, tmp_path: Path, arch_dir: Path) -> tuple[Path, ArchiveManifest]:
        bundle = arch_dir / "source-T.bundle"
        bundle.write_bytes(b"data")
        m = ArchiveManifest(
            kind="source",
            source_commit="c",
            created_at="T",
            archive_path=str(bundle),
            compressed_size=4,
            content_sha256=_calcular_sha256(bundle),
            file_count=1,
            retention_days=90,
        )
        mpath = _escribir_manifest(m)
        return mpath, m

    def test_ok(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        mpath, _ = self._manifest_ok(tmp_path, arch)
        assert verify_archive(mpath, archive_dir=arch) is True

    def test_manifest_no_existe(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        assert verify_archive(arch / "nope.manifest.json", archive_dir=arch) is False

    def test_manifest_invalido(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        bad = arch / "bad.manifest.json"
        bad.write_text("{not json")
        assert verify_archive(bad, archive_dir=arch) is False

    def test_archive_no_existe(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        m = ArchiveManifest(created_at="T", archive_path=str(arch / "ghost.bundle"), content_sha256="s")
        mpath = _escribir_manifest(m)
        assert verify_archive(mpath, archive_dir=arch) is False

    def test_sha_mismatch(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        mpath, _ = self._manifest_ok(tmp_path, arch)
        raw = json.loads(mpath.read_text())
        raw["content_sha256"] = "0" * 64
        mpath.write_text(json.dumps(raw))
        assert verify_archive(mpath, archive_dir=arch) is False

    def test_traversal_denegado(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        assert _resolver_dentro(arch, tmp_path / ".." / "evil", "x") is None

    def test_cargar_manifest_invalido(self, tmp_path) -> None:
        f = tmp_path / "m.json"
        f.write_text("nope")
        assert _cargar_manifest_archivo(f) is None


class TestRestore:
    def test_manifest_invalido(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        bad = arch / "bad.manifest.json"
        bad.write_text("{nope")
        with pytest.raises(ValueError, match="no pasó verificación"):
            restore_source(bad, archive_dir=arch)

    def test_verify_fail(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        m = ArchiveManifest(created_at="T", archive_path=str(arch / "ghost.bundle"), content_sha256="s")
        mpath = _escribir_manifest(m)
        with pytest.raises(ValueError, match="no pasó verificación"):
            restore_source(mpath, archive_dir=arch)

    def test_bundle_no_existe(self, tmp_path, monkeypatch) -> None:
        # La rama FileNotFoundError (bundle borrado entre verify y restore) es
        # inalcanzable en single-thread: verify comprueba exists() antes.
        arch = tmp_path / "arch"
        arch.mkdir()
        bundle = arch / "source-T.bundle"
        bundle.write_bytes(b"data")
        m = ArchiveManifest(created_at="T", archive_path=str(bundle), content_sha256=_calcular_sha256(bundle))
        mpath = _escribir_manifest(m)
        monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda *a, **k: True)
        bundle.unlink()
        with pytest.raises(FileNotFoundError):
            restore_source(mpath, archive_dir=arch)

    def test_traversal_manifest(self, tmp_path) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        with pytest.raises(ValueError, match="Path traversal"):
            restore_source(tmp_path / ".." / "evil.json", archive_dir=arch)

    def test_e2e(self, tmp_path) -> None:
        repo = _git_repo(tmp_path, content="original")
        arch = tmp_path / "arch"
        m = archive_source(source_dir=repo, archive_dir=arch)
        dest = tmp_path / "restored"
        commit = restore_source(
            arch / f"source-{m.created_at}.manifest.json",
            dest_dir=dest,
            archive_dir=arch,
        )
        assert commit == m.source_commit
        assert (dest / "f.txt").read_text() == "original"

    def test_clonar_bundle_error(self, tmp_path, monkeypatch) -> None:
        bundle = tmp_path / "b.bundle"
        bundle.write_bytes(b"x")
        monkeypatch.setattr(
            "knowledge.engine.archiver.subprocess.run",
            lambda *a, **k: mock.Mock(returncode=1, stderr="clone boom"),
        )
        with pytest.raises(RuntimeError, match="Error restaurando desde bundle"):
            _clonar_bundle(bundle, tmp_path / "dest", None)

    def test_checkout_error(self, tmp_path, monkeypatch) -> None:
        bundle = tmp_path / "b.bundle"
        bundle.write_bytes(b"x")
        dest = tmp_path / "dest"
        dest.mkdir()
        monkeypatch.setattr(
            "knowledge.engine.archiver.subprocess.run",
            lambda *a, **k: mock.Mock(returncode=0, stderr=""),
        )
        monkeypatch.setattr(
            "knowledge.engine.archiver._git_cmd",
            lambda *a, **k: mock.Mock(returncode=1, stderr="checkout boom"),
        )
        with pytest.raises(RuntimeError, match="Error haciendo checkout"):
            _clonar_bundle(bundle, dest, "c" * 40)


class TestList:
    def test_dir_no_existe(self, tmp_path) -> None:
        assert list_archives(tmp_path / "ghost") == []

    def test_manifests_ok_y_corruptos(self, tmp_path, caplog) -> None:
        arch = tmp_path / "arch"
        arch.mkdir()
        bundle = arch / "source-T.bundle"
        bundle.write_bytes(b"x")
        m = ArchiveManifest(created_at="T", archive_path=str(bundle), content_sha256="s")
        _escribir_manifest(m)
        (arch / "corrupto.manifest.json").write_text("no")
        with caplog.at_level("WARNING", logger="ura.knowledge.archiver"):
            items = list_archives(arch)
        assert len(items) == 1
        assert any("corrupto" in r.message for r in caplog.records)

    def test_from_db_sin_tabla(self, tmp_path) -> None:
        assert list_archives_from_db(tmp_path / "no.db") == []
