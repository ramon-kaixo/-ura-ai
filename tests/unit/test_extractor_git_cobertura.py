"""Cobertura 100x100 de knowledge/engine/extractors/git.py (TASK-20260815-003).

Cubre el GitExtractor completo: extracción por URL remota (clone) y por
directorio local, metadata de commits/tags/branches/README, hash del repo,
tamaño, calidad, límites (GitLimitError), degradación sin git CLI y todos
los fallos de subprocess (timeout, OSError, returncode != 0).

Las llamadas externas (subprocess.run a git, mkdtemp, rmtree) se aíslan con
monkeypatch; el comportamiento lógico (parsing, transformaciones, errores)
es el real del módulo.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.extractors import git as git_mod
from knowledge.engine.extractors.base import ExtractionResult, get_registry
from knowledge.engine.extractors.git import (
    CLONE_TIMEOUT,
    MAX_CLONE_SIZE,
    GitExtractor,
    GitLimitError,
    _compute_git_quality,
    _find_readme,
    _git_cmd,
    _sanitize_git_url,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset


def _canned_commits(n: int) -> str:
    """Genera n líneas de git log en el formato hash|author|email|date|msg."""
    return "".join(
        f"abcde{i:03d}1|Author {i}|author{i}@example.com|2026-01-01T10:00:00+00:00|Commit {i}\n"
        for i in range(n)
    )


_FULL_OUTPUTS: dict[str, str | None] = {
    "config": "https://github.com/user/repo.git\n",
    "rev-parse": "main\n",
    "log": _canned_commits(3),
    "tag": "v1.0.0\n\nv0.9.0\n",
    "branch": "* main\n  dev\n",
}


def _fake_git_cmd(outputs: dict[str, str | None]) -> Callable[[str, list[str]], str | None]:
    """Sustituto de _git_cmd: devuelve salidas fijas por subcomando git."""

    def _fake(repo_path: str, args: list[str]) -> str | None:
        return outputs.get(args[0])

    return _fake


def _recorder_rmtree(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Reemplaza shutil.rmtree por un registrador y devuelve las llamadas."""
    calls: list[tuple[Any, ...]] = []

    def _fake(*args: Any, **kwargs: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(git_mod.shutil, "rmtree", _fake)
    return calls


@pytest.fixture
def local_repo(tmp_path: Path) -> Path:
    """Repositorio local simulado: .git/ + README.md + un archivo de datos."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "README.md").write_text("# Test repo\n" * 40, encoding="utf-8")
    (repo / "data.txt").write_text("x" * 7, encoding="utf-8")
    return repo


class TestRegistry:
    """Registro automático del extractor en el registry global."""

    def test_git_extractor_registered(self) -> None:
        extractor = get_registry().get("git")
        assert isinstance(extractor, GitExtractor)
        assert extractor.id == "git"
        assert extractor.version == "1.0.0"
        assert extractor.supported_mime_types == []
        assert extractor.cost == "O(n²)"


class TestExtract:
    """Flujo completo de GitExtractor.extract."""

    def test_sin_git_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", False)
        result = GitExtractor().extract(AssetSource("github", "https://github.com/user/repo"))

        assert result.errors == ["git CLI not available"]
        assert result.asset is None
        assert result.duration_ms >= 0

    def test_location_vacia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        result = GitExtractor().extract(AssetSource("filesystem", ""))

        assert result.errors == ["Empty location"]
        assert result.asset is None

    def test_resolve_devuelve_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        monkeypatch.setattr(GitExtractor, "_resolve_work_dir", lambda self, source, location: "Not a git repository: /x")

        result = GitExtractor().extract(AssetSource("filesystem", "/x"))

        assert result.errors == ["Not a git repository: /x"]
        assert result.asset is None

    def test_exito_local_sin_limpieza(self, monkeypatch: pytest.MonkeyPatch, local_repo: Path) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        rmtree_calls = _recorder_rmtree(monkeypatch)

        result = GitExtractor().extract(AssetSource("filesystem", str(local_repo)))

        assert isinstance(result, ExtractionResult)
        assert result.errors == []
        asset = result.asset
        assert asset is not None
        assert len(asset.asset_id) == 16
        assert asset.asset_type is AssetType.GIT_REPO
        assert asset.source.kind == "filesystem"
        assert asset.quality == 1.0
        assert asset.created_at == asset.updated_at
        md = asset.metadata
        assert md["origin_url"] == "https://github.com/user/repo.git"
        assert md["current_branch"] == "main"
        assert md["commit_count"] == 3
        assert md["tag_count"] == 2
        assert md["branch_count"] == 2
        assert md["readme_preview"].startswith("# Test repo")
        assert md["size"] > 0
        assert md["_extractor"] == "git"
        assert md["_extractor_version"] == "1.0.0"
        assert md["wraps"] == f"source:{local_repo}"
        assert md["extracted_at"] == asset.created_at
        assert len(md["content_sha256"]) == 64
        assert md["content_sha256"][:16] == asset.asset_id
        assert "cloned_from" not in md
        assert rmtree_calls == []

    def test_exito_remoto_limpieza_temp(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        tmp_dir = tmp_path / "clone-target"
        tmp_dir.mkdir()
        monkeypatch.setattr(git_mod.tempfile, "mkdtemp", lambda **kw: str(tmp_dir))
        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(lambda url, target: target))
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        rmtree_calls = _recorder_rmtree(monkeypatch)

        location = "https://github.com/user/repo"
        result = GitExtractor().extract(AssetSource("github", location))

        assert result.errors == []
        assert result.asset is not None
        md = result.asset.metadata
        assert md["cloned_from"] == location
        assert md["clone_size"] == md["size"]
        assert rmtree_calls == [(str(tmp_dir),)]

    def test_excepcion_capturada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)

        def boom(self: GitExtractor, source: AssetSource, location: str) -> str:
            raise RuntimeError("boom")

        monkeypatch.setattr(GitExtractor, "_resolve_work_dir", boom)

        result = GitExtractor().extract(AssetSource("filesystem", "/x"))

        assert result.errors == ["Extraction error: boom"]
        assert result.asset is None

    def test_temp_sin_work_dir_no_limpia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        monkeypatch.setattr(GitExtractor, "_resolve_work_dir", lambda self, source, location: ("", True))
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        rmtree_calls = _recorder_rmtree(monkeypatch)

        result = GitExtractor().extract(AssetSource("github", "https://github.com/user/repo"))

        assert result.asset is not None
        assert rmtree_calls == []

    def test_limite_tamano_error(self, monkeypatch: pytest.MonkeyPatch, local_repo: Path) -> None:
        monkeypatch.setattr(git_mod, "_HAS_GIT", True)
        monkeypatch.setattr(GitExtractor, "_repo_size", staticmethod(lambda p: MAX_CLONE_SIZE + 1))

        result = GitExtractor().extract(AssetSource("filesystem", str(local_repo)))

        assert result.asset is None
        assert len(result.errors) == 1
        assert "Repository too large" in result.errors[0]


class TestResolveWorkDir:
    """Resolución del directorio de trabajo: remoto (clone) o local."""

    def test_remoto_kind_github(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        tmp_dir = tmp_path / "t"
        tmp_dir.mkdir()
        monkeypatch.setattr(git_mod.tempfile, "mkdtemp", lambda **kw: str(tmp_dir))
        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(lambda url, target: target))

        work = GitExtractor()._resolve_work_dir(AssetSource("github", "https://github.com/user/repo"), "x")

        assert work == (str(tmp_dir), True)

    def test_remoto_por_url_https(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        tmp_dir = tmp_path / "t"
        tmp_dir.mkdir()
        monkeypatch.setattr(git_mod.tempfile, "mkdtemp", lambda **kw: str(tmp_dir))
        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(lambda url, target: target))

        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", "https://example.com/r.git"), "https://example.com/r.git")

        assert work == (str(tmp_dir), True)

    def test_remoto_por_ssh(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        tmp_dir = tmp_path / "t"
        tmp_dir.mkdir()
        monkeypatch.setattr(git_mod.tempfile, "mkdtemp", lambda **kw: str(tmp_dir))
        monkeypatch.setattr(GitExtractor, "_clone_repo", staticmethod(lambda url, target: target))

        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", "git@github.com:u/r.git"), "git@github.com:u/r.git")

        assert work == (str(tmp_dir), True)

    def test_local_repo(self, local_repo: Path) -> None:
        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", str(local_repo)), str(local_repo))

        assert work == (str(local_repo), False)

    def test_local_directorio_dot_git(self, tmp_path: Path) -> None:
        git_dir = tmp_path / "repo" / ".git"
        git_dir.mkdir(parents=True)
        loc = str(git_dir)

        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", loc), loc)

        assert work == (str(git_dir.parent), False)

    def test_existe_sin_git(self, tmp_path: Path) -> None:
        loc = str(tmp_path / "plain")
        (tmp_path / "plain").mkdir()

        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", loc), loc)

        assert work == f"Not a git repository: {loc}"

    def test_location_no_encontrada(self) -> None:
        loc = "/no/such/dir-xyz"

        work = GitExtractor()._resolve_work_dir(AssetSource("filesystem", loc), loc)

        assert work == f"Location not found: {loc}"


class TestCloneRepo:
    """GitExtractor._clone_repo: clonado con git CLI."""

    def test_exito_devuelve_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=0, stderr=None))

        target = GitExtractor._clone_repo("git@github.com:user/repo.git", "/tmp/t")

        assert target == "/tmp/t"

    def test_fallo_raise_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            git_mod.subprocess,
            "run",
            lambda *args, **kw: SimpleNamespace(returncode=128, stdout="", stderr="fatal: boom\n"),
        )

        with pytest.raises(RuntimeError, match="fatal: boom"):
            GitExtractor._clone_repo("https://github.com/user/repo", "/tmp/t")

    def test_comando_y_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict[str, Any]] = []

        def fake_run(*args: Any, **kw: Any) -> Any:
            calls.append({**kw, "cmd": args[0]})
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(git_mod.subprocess, "run", fake_run)

        GitExtractor._clone_repo("https://github.com/user/repo", "/tmp/t")

        cmd = calls[0]["cmd"]
        assert cmd == ["git", "clone", "--depth", "1", "--single-branch", "https://github.com/user/repo", "/tmp/t"]
        assert calls[0]["timeout"] == CLONE_TIMEOUT
        assert calls[0]["check"] is False
        assert calls[0]["capture_output"] is True
        assert calls[0]["text"] is True


class TestFindGitDir:
    """GitExtractor._find_git_dir: detección del directorio .git."""

    def test_subdirectorio_dot_git(self, tmp_path: Path) -> None:
        p = tmp_path / "repo"
        (p / ".git").mkdir(parents=True)

        assert GitExtractor._find_git_dir(str(p)) == str(p / ".git")

    def test_propio_directorio_dot_git(self, tmp_path: Path) -> None:
        p = tmp_path / ".git"
        p.mkdir()

        assert GitExtractor._find_git_dir(str(p)) == str(p)

    def test_sin_git_retorna_none(self, tmp_path: Path) -> None:
        p = tmp_path / "plain"
        p.mkdir()

        assert GitExtractor._find_git_dir(str(p)) is None

    def test_dot_git_como_archivo(self, tmp_path: Path) -> None:
        p = tmp_path / "repo"
        p.mkdir()
        (p / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")

        assert GitExtractor._find_git_dir(str(p)) is None


class TestBuildGitAsset:
    """GitExtractor._build_git_asset: construcción del KnowledgeAsset."""

    def test_construccion_local(self, monkeypatch: pytest.MonkeyPatch, local_repo: Path) -> None:
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        now = "2026-08-15T10:00:00+00:00"
        source = AssetSource("filesystem", str(local_repo))

        asset = GitExtractor()._build_git_asset(source, str(local_repo), str(local_repo), False, now)

        assert isinstance(asset, KnowledgeAsset)
        assert asset.asset_id == asset.metadata["content_sha256"][:16]
        assert asset.asset_type is AssetType.GIT_REPO
        assert asset.quality == 1.0
        assert asset.created_at == now
        assert asset.updated_at == now
        assert asset.metadata["_extractor"] == "git"
        assert asset.metadata["_extractor_version"] == "1.0.0"
        assert asset.metadata["extracted_at"] == now
        assert asset.metadata["wraps"] == f"source:{local_repo}"
        assert "cloned_from" not in asset.metadata

    def test_temp_anade_clonado(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        source = AssetSource("github", "https://github.com/user/repo")

        asset = GitExtractor()._build_git_asset(source, "https://github.com/user/repo", str(work), True, "now")

        assert asset.metadata["cloned_from"] == "https://github.com/user/repo"
        assert asset.metadata["clone_size"] == asset.metadata["size"]

    def test_repo_demasiado_grande(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(_FULL_OUTPUTS))
        monkeypatch.setattr(GitExtractor, "_repo_size", staticmethod(lambda p: MAX_CLONE_SIZE + 1))
        source = AssetSource("filesystem", "/x")

        with pytest.raises(GitLimitError, match="Repository too large"):
            GitExtractor()._build_git_asset(source, "/x", "/x", False, "now")


class TestRepoSize:
    """GitExtractor._repo_size: tamaño del repo recorriendo el árbol."""

    def test_suma_archivos_y_subdirectorios(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"12345")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.bin").write_bytes(b"1234567")

        assert GitExtractor._repo_size(str(tmp_path)) == 12

    def test_symlink_roto_ignorado(self, tmp_path: Path) -> None:
        (tmp_path / "ok.txt").write_bytes(b"abc")
        (tmp_path / "broken").symlink_to(tmp_path / "missing-target")

        assert GitExtractor._repo_size(str(tmp_path)) == 3


class TestExtractGitMetadata:
    """GitExtractor._extract_git_metadata: parsing de salidas de git."""

    def test_completo(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("Hello", encoding="utf-8")
        outputs: dict[str, str | None] = {
            "config": "https://github.com/user/repo.git\n",
            "rev-parse": "main\n",
            "log": "aaabbb11|Alice|a@b.com|2026-01-01T00:00:00+00:00|First\n"
            "badline\n"
            "c|Bob|b@c.com|2026-01-02T00:00:00+00:00\n",
            "tag": "v2.0.0\n\nv1.0.0\n",
            "branch": "* main\n  dev\n",
        }
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(outputs))

        md = GitExtractor._extract_git_metadata(str(tmp_path))

        assert md["origin_url"] == "https://github.com/user/repo.git"
        assert md["current_branch"] == "main"
        assert md["commit_count"] == 2
        assert md["commits"][0] == {"hash": "aaabbb11", "author": "Alice", "email": "a@b.com", "date": "2026-01-01T00:00:00+00:00", "message": "First"}
        assert md["commits"][1]["message"] == ""
        assert md["tags"] == ["v2.0.0", "v1.0.0"]
        assert md["tag_count"] == 2
        assert md["branches"] == ["main", "dev"]
        assert md["branch_count"] == 2
        assert md["readme_preview"] == "Hello"

    def test_salidas_vacias(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        outputs = {"config": None, "rev-parse": None, "log": None, "tag": None, "branch": None}
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd(outputs))

        md = GitExtractor._extract_git_metadata(str(tmp_path))

        assert md == {}

    def test_comandos_git_emitidos(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        calls: list[tuple[str, list[str]]] = []

        def fake(repo_path: str, args: list[str]) -> str | None:
            calls.append((repo_path, args))
            return None

        monkeypatch.setattr(git_mod, "_git_cmd", fake)

        GitExtractor._extract_git_metadata(str(tmp_path))

        assert [args for _, args in calls] == [
            ["config", "--get", "remote.origin.url"],
            ["rev-parse", "--abbrev-ref", "HEAD"],
            ["log", f"--max-count={git_mod.MAX_COMMITS}", "--format=%H|%an|%ae|%ai|%s"],
            ["tag", "--sort=-creatordate"],
            ["branch", "-a"],
        ]

    def test_readme_recortado_a_500(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("a" * 600, encoding="utf-8")
        monkeypatch.setattr(git_mod, "_git_cmd", _fake_git_cmd({}))

        md = GitExtractor._extract_git_metadata(str(tmp_path))

        assert md["readme_preview"] == "a" * 500


class TestHashGitRepo:
    """GitExtractor._hash_git_repo: hash determinista del repo."""

    def test_determinista_y_sensible_a_cambios(self) -> None:
        md = {"commits": [{"hash": "aa", "message": "msg"}], "origin_url": "u", "tag_count": 2, "branch_count": 3}

        assert GitExtractor._hash_git_repo(md) == GitExtractor._hash_git_repo(dict(md))
        assert GitExtractor._hash_git_repo(md) != GitExtractor._hash_git_repo({**md, "origin_url": "other"})
        assert len(GitExtractor._hash_git_repo(md)) == 64

    def test_solo_primeros_10_commits(self) -> None:
        commits = [{"hash": f"h{i}", "message": f"m{i}"} for i in range(12)]

        assert GitExtractor._hash_git_repo({"commits": commits}) == GitExtractor._hash_git_repo({"commits": commits[:10]})

    def test_sin_commits_ni_claves(self) -> None:
        assert GitExtractor._hash_git_repo({}) == GitExtractor._hash_git_repo({"commits": [{"hash": "", "message": ""}]})


class TestGitCmd:
    """_git_cmd: ejecución de comandos git auxiliares."""

    def test_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=0, stdout="out\n", stderr=""))

        assert _git_cmd("/repo", ["config", "--get", "remote.origin.url"]) == "out\n"

    def test_stdout_vacio_retorna_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=0, stdout="   \n", stderr=""))

        assert _git_cmd("/repo", ["rev-parse", "HEAD"]) is None

    def test_returncode_no_cero_retorna_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(git_mod.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=1, stdout="", stderr="err"))

        assert _git_cmd("/repo", ["log"]) is None

    def test_timeout_retorna_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kw: Any) -> Any:
            raise subprocess.TimeoutExpired(["git"], 30)

        monkeypatch.setattr(git_mod.subprocess, "run", boom)

        assert _git_cmd("/repo", ["log"]) is None

    def test_oserror_retorna_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kw: Any) -> Any:
            raise OSError("no git")

        monkeypatch.setattr(git_mod.subprocess, "run", boom)

        assert _git_cmd("/repo", ["log"]) is None

    def test_comando_con_prefijo_git_y_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict[str, Any]] = []

        def fake(*args: Any, **kw: Any) -> Any:
            calls.append({**kw, "cmd": args[0]})
            return SimpleNamespace(returncode=0, stdout="x\n", stderr="")

        monkeypatch.setattr(git_mod.subprocess, "run", fake)

        _git_cmd("/repo", ["status", "--short"])

        assert calls[0]["cmd"] == ["git", "status", "--short"]
        assert calls[0]["cwd"] == "/repo"
        assert calls[0]["timeout"] == 30


class TestSanitizeGitUrl:
    """_sanitize_git_url: normalización de URLs de git."""

    def test_ssh_con_dos_puntos_inalterada(self) -> None:
        assert _sanitize_git_url("git@github.com:user/repo.git") == "git@github.com:user/repo.git"

    def test_http_inalterada(self) -> None:
        assert _sanitize_git_url("http://example.com/r.git") == "http://example.com/r.git"

    def test_https_inalterada(self) -> None:
        assert _sanitize_git_url("https://example.com/r.git") == "https://example.com/r.git"

    def test_ssh_sin_dos_puntos_inalterada(self) -> None:
        assert _sanitize_git_url("git@example.com") == "git@example.com"

    def test_otro_scheme_inalterado(self) -> None:
        assert _sanitize_git_url("file:///repo") == "file:///repo"


class TestFindReadme:
    """_find_readme: localización del README del repo."""

    @pytest.mark.parametrize("name", ["README.md", "README.rst", "README.txt", "README"])
    def test_encuentra_readme(self, tmp_path: Path, name: str) -> None:
        (tmp_path / name).write_text("contenido", encoding="utf-8")

        assert _find_readme(str(tmp_path)) == "contenido"

    def test_sin_readme_retorna_none(self, tmp_path: Path) -> None:
        assert _find_readme(str(tmp_path)) is None

    def test_error_de_lectura_retorna_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "README.md").write_text("x", encoding="utf-8")

        def boom(self: Path, **kw: Any) -> str:
            raise OSError("cannot read")

        monkeypatch.setattr(Path, "read_text", boom)

        assert _find_readme(str(tmp_path)) is None


class TestComputeGitQuality:
    """_compute_git_quality: puntuación de calidad del asset."""

    def test_vacio_retorna_base(self) -> None:
        assert _compute_git_quality({}) == 0.3

    def test_solo_commits_menos_de_10(self) -> None:
        assert _compute_git_quality({"commit_count": 5}) == 0.5

    def test_10_commits_suma_bonus(self) -> None:
        assert _compute_git_quality({"commit_count": 10}) == 0.6

    def test_completo_limitado_a_1(self) -> None:
        md = {"commit_count": 10, "tag_count": 1, "branch_count": 2, "origin_url": "u", "readme_preview": "r"}

        assert _compute_git_quality(md) == 1.0
