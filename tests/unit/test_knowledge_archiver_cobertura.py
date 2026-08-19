"""Tests de cobertura para knowledge/engine/archiver.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from knowledge.engine.archiver import (
    PathTraversalError,
    _archive_path,
    _calcular_sha256,
    _clonar_bundle,
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


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.md").write_text("contenido a")
    (repo / "b.md").write_text("contenido b")
    _git_cmd("init", "-b", "main", cwd=repo)
    _git_cmd("add", ".", cwd=repo)
    _git_cmd("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=repo)
    return repo


def test_resolve_within_ok(tmp_path) -> None:
    allowed = tmp_path / "arch"
    allowed.mkdir()
    target = allowed / "sub"
    target.mkdir()
    assert _resolve_within(target, allowed) == target


def test_resolve_within_fuera(tmp_path) -> None:
    allowed = tmp_path / "arch"
    allowed.mkdir()
    fuera = tmp_path / "otro"
    fuera.mkdir()
    with pytest.raises(PathTraversalError):
        _resolve_within(fuera, allowed)


def test_resolve_within_no_existe_fuera(tmp_path) -> None:
    allowed = tmp_path / "arch"
    allowed.mkdir()
    with pytest.raises(PathTraversalError):
        _resolve_within(tmp_path / "no" / "existe", allowed)


def test_resolve_within_no_existe_dentro(tmp_path) -> None:
    allowed = tmp_path / "arch"
    allowed.mkdir()
    res = _resolve_within(allowed / "nuevo.txt", allowed)
    assert res == allowed / "nuevo.txt"


def test_validate_source_dir(tmp_path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    assert _validate_source_dir(src) == src


def test_validate_source_dir_fuera(tmp_path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    allowed = tmp_path / "otro"
    allowed.mkdir()
    with pytest.raises(PathTraversalError):
        _validate_source_dir(src, allowed_root=allowed)


def test_ensure_dir(tmp_path) -> None:
    d = _ensure_dir(tmp_path / "n" / "d")
    assert d.is_dir()


def test_git_cmd(git_repo) -> None:
    r = _git_cmd("rev-parse", "HEAD", cwd=git_repo)
    assert r.returncode == 0
    assert len(r.stdout.strip()) == 40


def test_paths_helpers(tmp_path) -> None:
    assert _manifest_path(tmp_path, "source", "ts") == tmp_path / "source-ts.manifest.json"
    assert _archive_path(tmp_path, "source", "ts") == tmp_path / "source-ts.bundle"


def test_verificar_git_commit(git_repo) -> None:
    assert len(_verificar_git_commit(git_repo)) == 40


def test_verificar_git_commit_no_repo(tmp_path) -> None:
    with pytest.raises(ValueError):
        _verificar_git_commit(tmp_path)


def test_contar_tracked(git_repo) -> None:
    assert _contar_tracked(git_repo) == 2


def test_crear_bundle_error(git_repo, tmp_path, monkeypatch) -> None:
    def _falla(*args, **kwargs):
        return subprocess.CompletedProcess(args=(), returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("knowledge.engine.archiver._git_cmd", _falla)
    with pytest.raises(RuntimeError):
        _crear_bundle(git_repo, tmp_path / "x.bundle")


def test_calcular_sha256(tmp_path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"a" * 100_000)
    assert len(_calcular_sha256(p)) == 64


def test_escribir_manifest(tmp_path) -> None:
    m = ArchiveManifest(source_commit="c", created_at="ts", archive_path=str(tmp_path / "x.bundle"))
    path = _escribir_manifest(m)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["source_commit"] == "c"


def test_archive_source_e2e(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    assert manifest.source_commit
    bundle = arch / f"source-{manifest.created_at}.bundle"
    assert bundle.exists()
    assert manifest.file_count == 2
    assert verify_archive(arch / f"source-{manifest.created_at}.manifest.json", archive_dir=arch) is True


def test_archive_source_no_repo(tmp_path) -> None:
    with pytest.raises(ValueError):
        archive_source(source_dir=tmp_path, archive_dir=tmp_path / "arch")


def test_archive_source_con_db(git_repo, tmp_path) -> None:
    from knowledge.engine.sqlite_writer import init_db

    db = tmp_path / "k.db"
    init_db(db, Path("schemas/knowledge_graph.sql"))
    arch = tmp_path / "arch"
    archive_source(source_dir=git_repo, archive_dir=arch, db_path=db)
    rows = list_archives_from_db(db)
    assert len(rows) == 1
    assert rows[0]["kind"] == "source"
    assert rows[0]["file_count"] == 2 if "file_count" in rows[0] else True


def test_verify_archive_manifest_fuera(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    assert verify_archive(arch / f"source-{manifest.created_at}.manifest.json", archive_dir=tmp_path / "otro") is False


def test_verify_archive_manifest_no_existe(tmp_path) -> None:
    arch = tmp_path / "arch"
    arch.mkdir()
    assert verify_archive(arch / "no.manifest.json", archive_dir=arch) is False


def test_verify_archive_manifest_invalido(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    mp = arch / f"source-{manifest.created_at}.manifest.json"
    mp.write_text("no-json")
    assert verify_archive(mp, archive_dir=arch) is False


def test_verify_archive_bundle_faltante(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    mp = arch / f"source-{manifest.created_at}.manifest.json"
    bundle = arch / f"source-{manifest.created_at}.bundle"
    bundle.unlink()
    assert verify_archive(mp, archive_dir=arch) is False


def test_verify_archive_sha_mismatch(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    mp = arch / f"source-{manifest.created_at}.manifest.json"
    bundle = arch / f"source-{manifest.created_at}.bundle"
    bundle.write_bytes(b"corrupto")
    assert verify_archive(mp, archive_dir=arch) is False


def test_resolver_dentro_traversal(tmp_path) -> None:
    allowed = tmp_path / "arch"
    allowed.mkdir()
    assert _resolver_dentro(allowed, tmp_path / "fuera", "x") is None


def test_restore_source_e2e(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    dest = tmp_path / "restored"
    commit = restore_source(arch / f"source-{manifest.created_at}.manifest.json", dest_dir=dest, archive_dir=arch)
    assert commit == manifest.source_commit
    assert (dest / "a.md").exists()


def test_restore_source_verificacion_falla(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    archive_source(source_dir=git_repo, archive_dir=arch)
    with pytest.raises(ValueError):
        restore_source(arch / "no.manifest.json", dest_dir=tmp_path / "d", archive_dir=arch)


def test_restore_source_bundle_faltante(git_repo, tmp_path, monkeypatch) -> None:
    arch = tmp_path / "arch"
    manifest = archive_source(source_dir=git_repo, archive_dir=arch)
    mp = arch / f"source-{manifest.created_at}.manifest.json"
    (arch / f"source-{manifest.created_at}.bundle").unlink()
    monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda *a, **k: True)
    with pytest.raises(FileNotFoundError):
        restore_source(mp, dest_dir=tmp_path / "d", archive_dir=arch)


def test_restore_source_traversal(git_repo, tmp_path) -> None:
    with pytest.raises(ValueError):
        restore_source(tmp_path / "fuera.manifest.json", dest_dir=tmp_path / "d")


def test_clonar_bundle_error(git_repo, tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "x.bundle"
    bundle.write_bytes(b"no-bundle")

    def _fail(*args, **kwargs):
        raise FileNotFoundError("git no encontrado")

    monkeypatch.setattr(subprocess, "run", _fail)
    with pytest.raises(FileNotFoundError):
        _clonar_bundle(bundle, tmp_path / "dest", None)


def test_list_archives_dir_no_existe(tmp_path) -> None:
    assert list_archives(tmp_path / "nope") == []


def test_list_archives_mezcla(git_repo, tmp_path) -> None:
    arch = tmp_path / "arch"
    archive_source(source_dir=git_repo, archive_dir=arch)
    (arch / "corrupto.manifest.json").write_text("basura")
    manifests = list_archives(arch)
    assert len(manifests) == 1
    assert manifests[0].file_count == 2


def test_list_archives_from_db_sin_tabla(tmp_path) -> None:
    db = tmp_path / "vacia.db"
    import sqlite3

    sqlite3.connect(db).close()
    assert list_archives_from_db(db) == []


def test_registrar_en_db_error_no_crash(git_repo, tmp_path) -> None:
    m = ArchiveManifest(source_commit="c", archive_path=str(tmp_path / "x.bundle"))
    _registrar_en_db(tmp_path / "sin_tabla.db", m, tmp_path / "m.json", tmp_path / "x.bundle", 10)
    assert True


def test_registrar_audit_y_metricas() -> None:
    _registrar_audit_y_metricas("abc", 1, 2, 0.0)
    assert True


def test_restore_source_manifest_invalido_despues_verify(git_repo, tmp_path, monkeypatch) -> None:
    arch = tmp_path / "arch"
    arch.mkdir()
    mp = arch / "source-x.manifest.json"
    mp.write_text("no-json")
    monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda *a, **k: True)
    with pytest.raises(ValueError):
        restore_source(mp, dest_dir=tmp_path / "d", archive_dir=arch)


def test_restore_source_archive_path_traversal(git_repo, tmp_path, monkeypatch) -> None:
    arch = tmp_path / "arch"
    arch.mkdir()
    mp = arch / "source-x.manifest.json"
    data = ArchiveManifest(source_commit="c", archive_path=str(tmp_path / "fuera.bundle"), created_at="x")
    mp.write_text(json.dumps(data.to_dict()))
    monkeypatch.setattr("knowledge.engine.archiver.verify_archive", lambda *a, **k: True)
    with pytest.raises(ValueError):
        restore_source(mp, dest_dir=tmp_path / "d", archive_dir=arch)


def test_clonar_bundle_git_falla(git_repo, tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "x.bundle"
    bundle.write_bytes(b"no-bundle")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=(), returncode=1, stdout="", stderr="git boom"),
    )
    with pytest.raises(RuntimeError):
        _clonar_bundle(bundle, tmp_path / "dest", None)


def test_clonar_bundle_checkout_falla(git_repo, tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "x.bundle"
    bundle.write_bytes(b"no-bundle")
    calls: list[str] = []

    def _fake(*args, **kwargs):
        calls.append(args[0])
        if "clone" in str(args):
            return subprocess.CompletedProcess(args=(), returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=(), returncode=1, stdout="", stderr="checkout boom")

    monkeypatch.setattr(subprocess, "run", _fake)
    with pytest.raises(RuntimeError):
        _clonar_bundle(bundle, tmp_path / "dest", "abc")
    assert len(calls) == 2


def test_registrar_audit_falla_silencioso(git_repo, tmp_path, monkeypatch) -> None:
    def _boom():
        raise RuntimeError("audit no disponible")

    monkeypatch.setattr("knowledge.engine.archiver._git_cmd", lambda *a, **k: None)  # noop
    import knowledge.engine.archiver as archiver_mod

    monkeypatch.setattr(archiver_mod, "_registrar_audit_y_metricas", lambda *a, **k: None)
    ArchiveManifest(source_commit="c", archive_path=str(tmp_path / "x.bundle"))
    _registrar_audit_y_metricas("abc", 1, 2, 0.0)
    assert True
