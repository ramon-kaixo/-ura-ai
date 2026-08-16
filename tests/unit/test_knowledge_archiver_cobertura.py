"""Cobertura 100x100 de knowledge/engine/archiver.py (TASK-20260815-003).

Cubre el archivado de source (git bundle, manifests, retention): flujos
felices, errores de git, path traversal, manifiestos corruptos, registro en
BD (mocks FakeConn) y auditoría/métricas con dobles.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine import archiver
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
from knowledge.engine.models import ARCHIVE_RETENTION_DAYS, ArchiveManifest


class FakeResult:
    """Resultado falso de subprocess.run/CompletedProcess."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self) -> str:
        return f"FakeResult(rc={self.returncode})"


class FakeGit:
    """Sustituye a archiver._git_cmd devolviendo resultados según los args."""

    def __init__(self, table: dict[str, FakeResult] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.table = table or {}
        self.default = FakeResult(0, "")

    def __call__(self, *args: str, cwd: Path) -> FakeResult:
        self.calls.append(args)
        for prefix, result in self.table.items():
            words = tuple(prefix.split())
            if args[: len(words)] == words:
                return result
        return self.default


class FakeConn:
    """Conexión sqlite falsa para op_archives."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.committed = False
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> FakeConn:
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def _write_manifest(tmp_path: Path, archive_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    manifest = archive_dir / name
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


class TestPathValidation:
    def test_resolve_within_existente_dentro(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        archivo = allowed / "a.txt"
        archivo.write_text("x", encoding="utf-8")
        result = _resolve_within(archivo, allowed, "path")
        assert result == archivo.resolve()

    def test_resolve_within_no_existe_dentro(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        result = _resolve_within(allowed / "sub" / "nuevo.txt", allowed, "path")
        assert result == (allowed / "sub" / "nuevo.txt").resolve()

    def test_resolve_within_existente_fuera(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        fuera = tmp_path / "fuera.txt"
        fuera.write_text("x", encoding="utf-8")
        with pytest.raises(PathTraversalError):
            _resolve_within(fuera, allowed, "path")

    def test_resolve_within_no_existe_fuera(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        with pytest.raises(PathTraversalError):
            _resolve_within(tmp_path / "otro" / "x.txt", allowed, "path")

    def test_validate_source_dir_con_root_dentro(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        result = _validate_source_dir(root / "sub", root)
        assert result == (root / "sub").resolve()

    def test_validate_source_dir_con_root_fuera(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        fuera = tmp_path / "fuera"
        fuera.mkdir()
        with pytest.raises(PathTraversalError):
            _validate_source_dir(fuera, root)

    def test_validate_source_dir_sin_root(self, tmp_path: Path) -> None:
        resultado = _validate_source_dir(tmp_path)
        assert resultado == tmp_path.resolve()


class TestHelpers:
    def test_ensure_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "a" / "b"
        assert _ensure_dir(d) == d
        assert d.is_dir()

    def test_git_cmd_con_which(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/git")

        def fake_run(*args: Any, **kwargs: Any) -> FakeResult:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return FakeResult(0, "out", "err")

        monkeypatch.setattr(archiver.subprocess, "run", fake_run)
        result = _git_cmd("rev-parse", "HEAD", cwd=tmp_path)
        assert result.returncode == 0
        assert captured["args"][0][0] == "/usr/bin/git"
        assert captured["kwargs"]["cwd"] == tmp_path

    def test_git_cmd_sin_which(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        captured: dict[str, Any] = {}

        def fake_run(*args: Any, **kwargs: Any) -> FakeResult:
            captured["args"] = args
            return FakeResult(1, "", "boom")

        monkeypatch.setattr(archiver.subprocess, "run", fake_run)
        result = _git_cmd("status", cwd=tmp_path)
        assert captured["args"][0][0] == "/usr/bin/git"
        assert result.returncode == 1

    def test_manifest_path(self, tmp_path: Path) -> None:
        assert _manifest_path(tmp_path, "source", "t1") == tmp_path / "source-t1.manifest.json"

    def test_archive_path(self, tmp_path: Path) -> None:
        assert _archive_path(tmp_path, "source", "t1") == tmp_path / "source-t1.bundle"


class TestVerificarGitCommit:
    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        git = FakeGit({"rev-parse": FakeResult(0, "abc123\n")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        assert _verificar_git_commit(tmp_path) == "abc123"

    def test_no_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        git = FakeGit({"rev-parse": FakeResult(128, "", "fatal: not a git repository")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        with pytest.raises(ValueError, match="no es un repositorio"):
            _verificar_git_commit(tmp_path)


class TestContarTracked:
    def test_con_archivos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        git = FakeGit({"ls-files": FakeResult(0, "a.py\nb.py\n")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        assert _contar_tracked(Path("/tmp/x")) == 2

    def test_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        git = FakeGit({"ls-files": FakeResult(0, "")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        assert _contar_tracked(Path("/tmp/x")) == 0


class TestCrearBundle:
    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "source-1.bundle"
        bundle.write_bytes(b"bundle-content")
        git = FakeGit({"bundle create": FakeResult(0)})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        size = _crear_bundle(tmp_path, bundle)
        assert size == bundle.stat().st_size
        assert git.calls[0][:2] == ("bundle", "create")

    def test_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "source-1.bundle"
        git = FakeGit({"bundle create": FakeResult(1, "", "bundle failed")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        with pytest.raises(RuntimeError, match="bundle failed"):
            _crear_bundle(tmp_path, bundle)


class TestCalcularSha256:
    def test_un_chunk(self, tmp_path: Path) -> None:
        f = tmp_path / "x.bin"
        f.write_bytes(b"hola")
        assert _calcular_sha256(f) == archiver.hashlib.sha256(b"hola").hexdigest()

    def test_multi_chunk(self, tmp_path: Path) -> None:
        f = tmp_path / "big.bin"
        f.write_bytes(b"a" * 200_000)
        assert _calcular_sha256(f) == archiver.hashlib.sha256(b"a" * 200_000).hexdigest()


class TestConstruirManifest:
    def test_retention_por_defecto(self) -> None:
        m = _construir_manifest("c1", "t1", Path("/a/source-t1.bundle"), 42, "sha", 3, None)
        assert m.retention_days == ARCHIVE_RETENTION_DAYS.get("source", 90)

    def test_retention_explicita(self) -> None:
        m = _construir_manifest("c1", "t1", Path("/a/source-t1.bundle"), 42, "sha", 3, 7)
        assert m.retention_days == 7


class TestEscribirManifest:
    def test_escribe_y_loguea(self, tmp_path: Path) -> None:
        manifest = ArchiveManifest(
            kind="source",
            source_commit="abcdef123456",
            created_at="20260815_120000_000000",
            archive_path=str(tmp_path / "source-20260815_120000_000000.bundle"),
            compressed_size=42,
            content_sha256="sha123",
            file_count=3,
            retention_days=90,
        )
        path = _escribir_manifest(manifest)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source_commit"] == "abcdef123456"
        assert data["retention_days"] == 90


class TestRegistrarEnDb:
    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn()

        def fake_open_db(_path: Path) -> FakeConn:
            return conn

        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", lambda _c: None)
        monkeypatch.setattr("knowledge.engine.connection.open_db", fake_open_db)
        manifest = ArchiveManifest(
            source_commit="abc",
            created_at="t1",
            archive_path=str(tmp_path / "s.bundle"),
            content_sha256="sha",
            retention_days=90,
        )
        _registrar_en_db(tmp_path / "db.sqlite", manifest, tmp_path / "m.json", tmp_path / "s.bundle", 42)
        assert conn.committed
        assert conn.closed

    def test_error_loguea_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_open_db(_path: Path) -> None:
            raise RuntimeError("db rota")

        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", lambda _c: None)
        monkeypatch.setattr("knowledge.engine.connection.open_db", fake_open_db)
        manifest = ArchiveManifest(source_commit="abc", created_at="t1", archive_path="s.bundle")
        _registrar_en_db(tmp_path / "db.sqlite", manifest, tmp_path / "m.json", tmp_path / "s.bundle", 1)


class TestRegistrarAuditYMetricas:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        audit_logged: list[dict[str, Any]] = []

        def fake_get_audit() -> Any:
            return SimpleNamespace(log_archive=lambda **kw: audit_logged.append(kw))

        monkeypatch.setattr("knowledge.engine.audit.get_audit", fake_get_audit)
        monkeypatch.setattr(
            "knowledge.engine.metrics.archive_duration_seconds",
            SimpleNamespace(observe=lambda _v: None),
        )
        _registrar_audit_y_metricas("abcdef123456", 3, 42, 0.0)
        assert audit_logged[0]["commit"] == "abcdef123456"

    def test_audit_falla_metricas_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get_audit() -> Any:
            raise RuntimeError("audit caido")

        monkeypatch.setattr("knowledge.engine.audit.get_audit", fake_get_audit)
        monkeypatch.setattr(
            "knowledge.engine.metrics.archive_duration_seconds",
            SimpleNamespace(observe=lambda _v: None),
        )
        _registrar_audit_y_metricas("abc", 3, 42, 0.0)

    def test_metricas_fallan(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get_audit() -> Any:
            return SimpleNamespace(log_archive=lambda **kw: None)

        monkeypatch.setattr("knowledge.engine.audit.get_audit", fake_get_audit)

        def fake_observe(_v: float) -> None:
            raise RuntimeError("metrics caido")

        monkeypatch.setattr(
            "knowledge.engine.metrics.archive_duration_seconds",
            SimpleNamespace(observe=fake_observe),
        )
        _registrar_audit_y_metricas("abc", 3, 42, 0.0)


class TestArchiveSource:
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[FakeGit, Path, Path]:
        source = tmp_path / "source"
        source.mkdir()
        archive_dir = tmp_path / "archives"
        git = FakeGit(
            {
                "rev-parse": FakeResult(0, "deadbeef123\n"),
                "ls-files": FakeResult(0, "a.py\nb.py\nc.py\n"),
            }
        )
        monkeypatch.setattr(archiver, "_git_cmd", git)
        monkeypatch.setattr(
            "knowledge.engine.audit.get_audit",
            lambda: SimpleNamespace(log_archive=lambda **kw: None),
        )
        monkeypatch.setattr(
            "knowledge.engine.metrics.archive_duration_seconds",
            SimpleNamespace(observe=lambda _v: None),
        )
        return git, source, archive_dir

    def test_flujo_completo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        git, source, archive_dir = self._setup(tmp_path, monkeypatch)

        def fake_crear_bundle(_src: Path, bundle_path: Path) -> int:
            bundle_path.write_bytes(b"bundle-bytes")
            return bundle_path.stat().st_size

        monkeypatch.setattr(archiver, "_crear_bundle", fake_crear_bundle)
        manifest = archive_source(source_dir=source, archive_dir=archive_dir, db_path=None)
        assert manifest.source_commit == "deadbeef123"
        assert manifest.file_count == 3
        assert manifest.retention_days == ARCHIVE_RETENTION_DAYS.get("source", 90)
        assert (archive_dir / f"source-{manifest.created_at}.manifest.json").exists()
        assert (archive_dir / f"source-{manifest.created_at}.bundle").exists()
        assert git.calls[0] == ("rev-parse", "HEAD")

    def test_con_db_y_retention(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _, source, archive_dir = self._setup(tmp_path, monkeypatch)
        conn = FakeConn()
        monkeypatch.setattr(archiver, "_crear_bundle", lambda _s, p: (p.write_bytes(b"x"), p.stat().st_size)[1])
        monkeypatch.setattr("knowledge.engine.connection.begin_immediate", lambda _c: None)
        monkeypatch.setattr("knowledge.engine.connection.open_db", lambda _p: conn)
        manifest = archive_source(
            source_dir=source,
            archive_dir=archive_dir,
            db_path=tmp_path / "ke.sqlite",
            retention_days=5,
        )
        assert manifest.retention_days == 5
        assert conn.committed

    def test_source_dir_por_defecto(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _, _, archive_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(archiver, "_crear_bundle", lambda _s, p: (p.write_bytes(b"x"), 1)[1])
        monkeypatch.setattr(archiver, "_validate_source_dir", lambda p, **kw: Path("/proj/source"))
        manifest = archive_source(archive_dir=archive_dir)
        assert manifest.file_count == 3

    def test_falla_si_no_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "source"
        source.mkdir()
        git = FakeGit({"rev-parse": FakeResult(128, "", "not a repo")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        with pytest.raises(ValueError, match="no es un repositorio"):
            archive_source(source_dir=source, archive_dir=tmp_path / "arch")


class TestCargarManifest:
    def test_valido(self, tmp_path: Path) -> None:
        path = _write_manifest(tmp_path, tmp_path, "s.manifest.json", {"kind": "source", "file_count": 5})
        manifest = _cargar_manifest_archivo(path)
        assert manifest is not None
        assert manifest.file_count == 5

    def test_json_invalido(self, tmp_path: Path) -> None:
        path = tmp_path / "s.manifest.json"
        path.write_text("{not json", encoding="utf-8")
        assert _cargar_manifest_archivo(path) is None

    def test_type_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _write_manifest(tmp_path, tmp_path, "s.manifest.json", {"kind": "source"})

        def fake_from_dict(_data: dict) -> ArchiveManifest:
            raise TypeError("campo raro")

        monkeypatch.setattr(ArchiveManifest, "from_dict", classmethod(fake_from_dict))
        assert _cargar_manifest_archivo(path) is None


class TestResolverDentro:
    def test_ok(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        f = allowed / "x.txt"
        f.write_text("x", encoding="utf-8")
        assert _resolver_dentro(allowed, f, "x") == f.resolve()

    def test_traversal_devuelve_none(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        assert _resolver_dentro(allowed, tmp_path / "fuera.txt", "x") is None


class TestVerifyArchive:
    def test_ok(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        bundle = allowed / "source-1.bundle"
        bundle.write_bytes(b"data")
        sha = _calcular_sha256(bundle)
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "source-1.manifest.json",
            {
                "kind": "source",
                "archive_path": str(bundle),
                "content_sha256": sha,
                "created_at": "t1",
            },
        )
        assert verify_archive(manifest, archive_dir=allowed) is True

    def test_manifest_no_existe(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        assert verify_archive(tmp_path / "none.manifest.json", archive_dir=allowed) is False

    def test_manifest_invalido(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        path = allowed / "bad.manifest.json"
        path.write_text("{broken", encoding="utf-8")
        assert verify_archive(path, archive_dir=allowed) is False

    def test_archive_no_existe(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "s.manifest.json",
            {"archive_path": str(allowed / "missing.bundle"), "content_sha256": "sha"},
        )
        assert verify_archive(manifest, archive_dir=allowed) is False

    def test_sha_mismatch(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        bundle = allowed / "source-1.bundle"
        bundle.write_bytes(b"datos")
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "source-1.manifest.json",
            {"archive_path": str(bundle), "content_sha256": "0" * 64, "created_at": "t1"},
        )
        assert verify_archive(manifest, archive_dir=allowed) is False

    def test_traversal_en_manifest(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        fuera = tmp_path / "fuera.manifest.json"
        fuera.write_text("{}", encoding="utf-8")
        assert verify_archive(fuera, archive_dir=allowed) is False

    def test_archive_dir_por_defecto(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        default_dir = tmp_path / "default"
        default_dir.mkdir()
        monkeypatch.setattr(archiver, "_DEFAULT_ARCHIVE_DIR", default_dir)
        bundle = default_dir / "s.bundle"
        bundle.write_bytes(b"x")
        sha = _calcular_sha256(bundle)
        manifest = _write_manifest(
            tmp_path,
            default_dir,
            "s.manifest.json",
            {"archive_path": str(bundle), "content_sha256": sha},
        )
        assert verify_archive(manifest) is True


class TestClonarBundle:
    def test_error_clone(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "s.bundle"
        bundle.write_bytes(b"x")
        dest = tmp_path / "dest"
        monkeypatch.setattr(
            archiver.subprocess,
            "run",
            lambda *a, **kw: FakeResult(1, "", "clone failed"),
        )
        with pytest.raises(RuntimeError, match="clone failed"):
            _clonar_bundle(bundle, dest, "abc")

    def test_ok_sin_commit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "s.bundle"
        bundle.write_bytes(b"x")
        dest = tmp_path / "dest"
        git = FakeGit()
        monkeypatch.setattr(archiver, "_git_cmd", git)
        monkeypatch.setattr(
            archiver.subprocess,
            "run",
            lambda *a, **kw: FakeResult(0),
        )
        _clonar_bundle(bundle, dest, None)
        assert dest.is_dir()
        assert git.calls == []

    def test_error_checkout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "s.bundle"
        bundle.write_bytes(b"x")
        dest = tmp_path / "dest"
        git = FakeGit({"checkout": FakeResult(1, "", "checkout failed")})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        monkeypatch.setattr(
            archiver.subprocess,
            "run",
            lambda *a, **kw: FakeResult(0),
        )
        with pytest.raises(RuntimeError, match="checkout failed"):
            _clonar_bundle(bundle, dest, "abc123")

    def test_ok_con_checkout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = tmp_path / "s.bundle"
        bundle.write_bytes(b"x")
        dest = tmp_path / "dest"
        git = FakeGit({"checkout": FakeResult(0)})
        monkeypatch.setattr(archiver, "_git_cmd", git)
        monkeypatch.setattr(
            archiver.subprocess,
            "run",
            lambda *a, **kw: FakeResult(0),
        )
        _clonar_bundle(bundle, dest, "abc123")
        assert git.calls[0] == ("checkout", "abc123")


class TestRestoreSource:
    def _manifest_valido(self, tmp_path: Path, allowed: Path) -> tuple[Path, Path]:
        bundle = allowed / "source-1.bundle"
        bundle.write_bytes(b"bundle-data")
        sha = _calcular_sha256(bundle)
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "source-1.manifest.json",
            {
                "kind": "source",
                "source_commit": "commit-abc",
                "archive_path": str(bundle),
                "content_sha256": sha,
                "created_at": "t1",
            },
        )
        return manifest, bundle

    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest, _ = self._manifest_valido(tmp_path, allowed)
        dest = tmp_path / "restored"
        clonado: list[tuple] = []
        monkeypatch.setattr(archiver, "_clonar_bundle", lambda b, d, c: clonado.append((b, d, c)))
        commit = restore_source(manifest, dest_dir=dest, archive_dir=allowed)
        assert commit == "commit-abc"
        assert clonado[0][1] == dest.resolve()

    def test_traversal_manifest(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        fuera = tmp_path / "fuera.manifest.json"
        fuera.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Path traversal"):
            restore_source(fuera, archive_dir=allowed)

    def test_verificacion_falla(self, tmp_path: Path) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest = _write_manifest(
            tmp_path, allowed, "s.manifest.json", {"archive_path": str(allowed / "missing.bundle")}
        )
        with pytest.raises(ValueError, match="no pasó verificación"):
            restore_source(manifest, archive_dir=allowed)

    def test_manifest_invalido(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest = allowed / "bad.manifest.json"
        manifest.write_text("{broken", encoding="utf-8")
        monkeypatch.setattr(archiver, "verify_archive", lambda *a, **kw: True)
        with pytest.raises(ValueError, match="Manifest inválido"):
            restore_source(manifest, archive_dir=allowed)

    def test_bundle_no_encontrado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "s.manifest.json",
            {
                "source_commit": "c",
                "archive_path": str(allowed / "ausente.bundle"),
                "content_sha256": "sha",
                "created_at": "t1",
            },
        )
        monkeypatch.setattr(archiver, "verify_archive", lambda *a, **kw: True)
        with pytest.raises(FileNotFoundError, match="Bundle no encontrado"):
            restore_source(manifest, archive_dir=allowed)

    def test_traversal_en_archive_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        fuera = tmp_path / "fuera.bundle"
        fuera.write_bytes(b"x")
        manifest = _write_manifest(
            tmp_path,
            allowed,
            "s.manifest.json",
            {
                "source_commit": "c",
                "archive_path": str(fuera),
                "content_sha256": "sha",
                "created_at": "t1",
            },
        )
        monkeypatch.setattr(archiver, "verify_archive", lambda *a, **kw: True)
        with pytest.raises(ValueError, match="Path traversal denegado en archive_path"):
            restore_source(manifest, archive_dir=allowed)

    def test_dest_por_defecto(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        allowed = tmp_path / "archives"
        allowed.mkdir()
        manifest, _ = self._manifest_valido(tmp_path, allowed)
        default_dest = tmp_path / "source"
        monkeypatch.setattr(archiver, "_PROJECT_ROOT", tmp_path)
        clonado: list[tuple] = []
        monkeypatch.setattr(archiver, "_clonar_bundle", lambda b, d, c: clonado.append((b, d, c)))
        commit = restore_source(manifest, archive_dir=allowed)
        assert commit == "commit-abc"
        assert clonado[0][1] == default_dest.resolve()


class TestListArchives:
    def test_dir_no_existe(self, tmp_path: Path) -> None:
        assert list_archives(tmp_path / "noexiste") == []

    def test_manifests_validos(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, tmp_path, "a.manifest.json", {"kind": "source", "file_count": 1})
        _write_manifest(tmp_path, tmp_path, "b.manifest.json", {"kind": "source", "file_count": 2})
        manifests = list_archives(tmp_path)
        assert [m.file_count for m in manifests] == [2, 1]

    def test_manifiesto_corrupto(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, tmp_path, "a.manifest.json", {"kind": "source", "file_count": 1})
        (tmp_path / "bad.manifest.json").write_text("{rotto", encoding="utf-8")
        manifests = list_archives(tmp_path)
        assert len(manifests) == 1

    def test_error_oserror(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, tmp_path, "a.manifest.json", {"kind": "source", "file_count": 1})
        (tmp_path / "dir.manifest.json").mkdir()
        manifests = list_archives(tmp_path)
        assert len(manifests) == 1

    def test_default_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        default_dir = tmp_path / "default"
        default_dir.mkdir()
        monkeypatch.setattr(archiver, "_DEFAULT_ARCHIVE_DIR", default_dir)
        assert list_archives() == []


class TestListArchivesFromDb:
    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        rows = [
            {
                "id": 1,
                "kind": "source",
                "source_commit": "abc",
                "manifest_path": "/m",
                "archive_path": "/a",
                "compressed_size": 3,
                "content_sha256": "s",
                "archived_at": "2026-01-01",
                "retention_days": 90,
            }
        ]
        monkeypatch.setattr("knowledge.engine.connection.open_db", lambda _p: FakeConn(rows))
        result = list_archives_from_db(tmp_path / "ke.sqlite")
        assert result == rows

    def test_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_open_db(_p: Path) -> None:
            raise RuntimeError("db caida")

        monkeypatch.setattr("knowledge.engine.connection.open_db", fake_open_db)
        assert list_archives_from_db(tmp_path / "ke.sqlite") == []
