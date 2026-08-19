"""Tests de cobertura para knowledge/engine/extractors/git.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from knowledge.engine.extractors import git as git_mod
from knowledge.engine.extractors.git import (
    GitExtractor,
    GitLimitError,
    _compute_git_quality,
    _find_readme,
    _sanitize_git_url,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.es"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "README.md").write_text("# Proyecto\n\nDescripcion larga." * 10)
    for i in range(3):
        (repo / f"f{i}.txt").write_text(f"contenido {i}")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", f"commit {i}"],
            check=True,
        )
    subprocess.run(["git", "-C", str(repo), "tag", "v1.0.0"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/u/r.git"], check=True)
    return repo


@pytest.fixture
def extractor() -> GitExtractor:
    return GitExtractor()


# ── extract() E2E ───────────────────────────────────────────────────────


def test_extract_repo_local(repo_dir: Path, extractor) -> None:
    source = AssetSource(kind="filesystem", location=str(repo_dir), fetched_at="")
    result = extractor.extract(source)
    assert result.errors == []
    assert result.asset is not None
    assert result.asset.asset_type == AssetType.GIT_REPO
    meta = result.asset.metadata
    assert meta["commit_count"] == 3
    assert meta["tag_count"] == 1
    assert meta["branch_count"] >= 1
    assert meta["origin_url"] == "https://github.com/u/r.git"
    assert "readme_preview" in meta
    assert meta["content_sha256"]
    assert result.duration_ms >= 0


def test_extract_location_no_existe(extractor) -> None:
    source = AssetSource(kind="filesystem", location="/no/existe", fetched_at="")
    result = extractor.extract(source)
    assert result.errors == ["Location not found: /no/existe"]
    assert result.asset is None


def test_extract_sin_git_dir(tmp_path, extractor) -> None:
    d = tmp_path / "sin_git"
    d.mkdir()
    source = AssetSource(kind="filesystem", location=str(d), fetched_at="")
    result = extractor.extract(source)
    assert result.errors == [f"Not a git repository: {d}"]


def test_extract_location_vacia(extractor) -> None:
    source = AssetSource(kind="filesystem", location="", fetched_at="")
    result = extractor.extract(source)
    assert result.errors == ["Empty location"]


def test_extract_sin_git_cli(extractor, monkeypatch) -> None:
    monkeypatch.setattr(git_mod, "_HAS_GIT", False)
    source = AssetSource(kind="filesystem", location="/x", fetched_at="")
    result = extractor.extract(source)
    assert result.errors == ["git CLI not available"]


def test_extract_remoto_clone_falla(extractor, monkeypatch) -> None:
    def boom(url: str, target: str) -> str:
        raise RuntimeError("clone failed for x")

    monkeypatch.setattr(extractor, "_clone_repo", boom)
    source = AssetSource(kind="github", location="https://github.com/u/r", fetched_at="")
    result = extractor.extract(source)
    assert result.errors and "Extraction error" in result.errors[0]


def test_extract_remoto_ok(repo_dir, extractor, monkeypatch) -> None:
    def fake_clone(url: str, target: str) -> str:
        return str(repo_dir)

    monkeypatch.setattr(extractor, "_clone_repo", fake_clone)
    source = AssetSource(kind="github", location="https://github.com/u/r", fetched_at="")
    result = extractor.extract(source)
    assert result.errors == []
    assert result.asset is not None
    assert result.asset.metadata["cloned_from"] == "https://github.com/u/r"


# ── Límites ─────────────────────────────────────────────────────────────


def test_repo_demasiado_grande(repo_dir, extractor, monkeypatch) -> None:
    monkeypatch.setattr(git_mod, "MAX_CLONE_SIZE", 0)
    source = AssetSource(kind="filesystem", location=str(repo_dir), fetched_at="")
    result = extractor.extract(source)
    assert result.errors and "Repository too large" in result.errors[0]
    assert result.asset is None


def test_git_limit_error_es_valueerror() -> None:
    assert issubclass(GitLimitError, ValueError)


# ── Helpers ─────────────────────────────────────────────────────────────


def test_resolve_work_dir_remoto(extractor, monkeypatch, repo_dir) -> None:
    monkeypatch.setattr(extractor, "_clone_repo", lambda url, target: str(repo_dir))
    source = AssetSource(kind="github", location="https://github.com/u/r", fetched_at="")
    work, is_temp = extractor._resolve_work_dir(source, "https://github.com/u/r")
    assert is_temp is True
    assert work == str(repo_dir)


def test_resolve_work_dir_local(repo_dir, extractor) -> None:
    source = AssetSource(kind="filesystem", location=str(repo_dir), fetched_at="")
    work, is_temp = extractor._resolve_work_dir(source, str(repo_dir))
    assert is_temp is False
    assert Path(work) == repo_dir


def test_find_git_dir(repo_dir, extractor) -> None:
    assert extractor._find_git_dir(str(repo_dir)) == str(repo_dir / ".git")
    assert extractor._find_git_dir(str(repo_dir / ".git")) == str(repo_dir / ".git")
    assert extractor._find_git_dir("/no/existe") is None


def test_sanitize_git_url() -> None:
    assert _sanitize_git_url("git@github.com:u/r.git") == "git@github.com:u/r.git"
    assert _sanitize_git_url("http://x") == "http://x"
    assert _sanitize_git_url("https://x") == "https://x"
    assert _sanitize_git_url("ftp://x") == "ftp://x"


def test_find_readme(repo_dir) -> None:
    content = _find_readme(str(repo_dir))
    assert content is not None
    assert "# Proyecto" in content
    assert _find_readme("/no/existe") is None


def test_compute_git_quality() -> None:
    assert _compute_git_quality({}) == 0.3
    q = _compute_git_quality(
        {"commit_count": 3, "tag_count": 1, "branch_count": 1, "origin_url": "x", "readme_preview": "y"}
    )
    assert q == pytest.approx(1.0)


def test_hash_git_repo() -> None:
    h1 = GitExtractor._hash_git_repo({"commits": [{"hash": "a", "message": "m"}], "origin_url": "x", "tag_count": 1, "branch_count": 1})
    h2 = GitExtractor._hash_git_repo({"commits": [{"hash": "b", "message": "m"}], "origin_url": "x", "tag_count": 1, "branch_count": 1})
    assert len(h1) == 64
    assert h1 != h2


def test_repo_size(repo_dir, extractor) -> None:
    size = extractor._repo_size(str(repo_dir))
    assert size > 0


def test_git_cmd_ok(repo_dir) -> None:
    out = git_mod._git_cmd(str(repo_dir), ["config", "--get", "user.email"])
    assert out is not None
    assert out.strip() == "t@t.es"


def test_git_cmd_fallo() -> None:
    assert git_mod._git_cmd("/no/existe", ["status"]) is None


def test_metadata_git_cmd_directo(repo_dir) -> None:
    meta = GitExtractor._extract_git_metadata(str(repo_dir))
    assert meta["commit_count"] == 3
    assert meta["commits"][0]["hash"]
    assert meta["tags"] == ["v1.0.0"]


def test_registro_registry() -> None:
    reg = git_mod.get_registry()
    assert reg.get("git") is not None
