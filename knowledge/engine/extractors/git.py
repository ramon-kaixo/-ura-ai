"""GitExtractor — extrae metadatos de repositorios Git.

Dependencias:
  - git CLI (obligatorio)

Extrae:
  - commits recientes, autores, branches, tags
  - release_notes, changelog

No tiene MIME type asociado. Se invoca explícitamente por URL scheme
(git+https://, git+file://) o por directorio (.git/).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.engine.extractors.base import (
    ExtractionResult,
    get_registry,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

log = logging.getLogger("ura.knowledge.extractors.git")

_GIT_MIMES: list[str] = []

MAX_COMMITS = 50
MAX_CLONE_SIZE = 500 * 1024 * 1024
CLONE_TIMEOUT = 120

_HAS_GIT = shutil.which("git") is not None


class GitLimitError(ValueError):
    """El repositorio excede los límites establecidos."""


class GitExtractor:
    """Extractor para repositorios Git.

    Uso:
        extractor = GitExtractor()
        # Por URL remota
        result = extractor.extract(AssetSource("github", "https://github.com/user/repo"))
        # Por directorio local
        result = extractor.extract(AssetSource("filesystem", "/path/to/repo/.git"))
    """

    id: str = "git"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _GIT_MIMES
    cost: str = "O(n²)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        t0 = time.monotonic()
        location = source.location

        if not _HAS_GIT:
            return ExtractionResult(
                errors=["git CLI not available"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        if not location:
            return ExtractionResult(
                errors=["Empty location"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        try:
            work_dir: str | None = None
            is_temp = False

            if source.kind in ("github", "git", "api") or location.startswith(("http://", "https://", "git@")):
                # Clonar remoto
                tmp = tempfile.mkdtemp(prefix="ura_git_")
                work_dir = self._clone_repo(location, tmp)
                is_temp = True
            elif Path(location).exists():
                # Usar repositorio local
                git_dir = self._find_git_dir(location)
                if not git_dir:
                    return ExtractionResult(
                        errors=[f"Not a git repository: {location}"],
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )
                work_dir = str(Path(git_dir).parent)
            else:
                return ExtractionResult(
                    errors=[f"Location not found: {location}"],
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            try:
                now = datetime.now(UTC).isoformat()
                metadata = self._extract_git_metadata(work_dir)

                repo_size = self._repo_size(work_dir)
                if repo_size > MAX_CLONE_SIZE:
                    msg = f"Repository too large: {repo_size} bytes (max {MAX_CLONE_SIZE})"
                    raise GitLimitError(msg)

                metadata["size"] = repo_size
                metadata["_extractor"] = self.id
                metadata["_extractor_version"] = self.version
                metadata["wraps"] = f"source:{location}"
                metadata["extracted_at"] = now

                if is_temp:
                    metadata["cloned_from"] = location
                    metadata["clone_size"] = repo_size

                content_sha256 = self._hash_git_repo(metadata)
                metadata["content_sha256"] = content_sha256

                asset = KnowledgeAsset(
                    asset_id=content_sha256[:16],
                    asset_type=AssetType.GIT_REPO,
                    metadata=metadata,
                    source=source,
                    quality=_compute_git_quality(metadata),
                    created_at=now,
                    updated_at=now,
                )

                return ExtractionResult(
                    asset=asset,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            finally:
                if is_temp and work_dir:
                    shutil.rmtree(work_dir, ignore_errors=True)

        except Exception as exc:
            log.exception("Git extraction error for %s", location)
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    @staticmethod
    def _clone_repo(url: str, target: str) -> str:
        url_clean = _sanitize_git_url(url)
        cmd = ["git", "clone", "--depth", "1", "--single-branch", url_clean, target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=CLONE_TIMEOUT, check=False)
        if result.returncode != 0:
            msg = f"git clone failed for {url}: {result.stderr.strip()}"
            raise RuntimeError(msg)
        return target

    @staticmethod
    def _find_git_dir(location: str) -> str | None:
        p = Path(location)
        if (p / ".git").is_dir():
            return str(p / ".git")
        if p.name == ".git" and p.is_dir():
            return str(p)
        return None

    @staticmethod
    def _extract_git_metadata(repo_path: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        # Origin URL
        origin = _git_cmd(repo_path, ["config", "--get", "remote.origin.url"])
        if origin:
            metadata["origin_url"] = origin.strip()

        # Branch actual
        branch = _git_cmd(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if branch:
            metadata["current_branch"] = branch.strip()

        # Commits recientes
        log_output = _git_cmd(repo_path, ["log", f"--max-count={MAX_COMMITS}", "--format=%H|%an|%ae|%ai|%s"])
        if log_output:
            commits = []
            for line in log_output.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 4)
                    commits.append(
                        {
                            "hash": parts[0][:8],
                            "author": parts[1],
                            "email": parts[2],
                            "date": parts[3],
                            "message": parts[4] if len(parts) > 4 else "",
                        },
                    )
            metadata["commits"] = commits
            metadata["commit_count"] = len(commits)

        # Tags
        tags_output = _git_cmd(repo_path, ["tag", "--sort=-creatordate"])
        if tags_output:
            tags = [t.strip() for t in tags_output.strip().split("\n") if t.strip()]
            metadata["tags"] = tags
            metadata["tag_count"] = len(tags)

        # Branches
        branches_output = _git_cmd(repo_path, ["branch", "-a"])
        if branches_output:
            branches = [b.strip().replace("* ", "").strip() for b in branches_output.strip().split("\n") if b.strip()]
            metadata["branches"] = branches
            metadata["branch_count"] = len(branches)

        # Description (README preview)
        readme = _find_readme(repo_path)
        if readme:
            metadata["readme_preview"] = readme[:500]

        log.info(
            "Extracted git metadata from %s (%d commits, %d tags, %d branches)",
            repo_path,
            metadata.get("commit_count", 0),
            metadata.get("tag_count", 0),
            metadata.get("branch_count", 0),
        )

        return metadata

    @staticmethod
    def _hash_git_repo(metadata: dict[str, Any]) -> str:
        h = hashlib.sha256()
        commits = metadata.get("commits", [])
        for c in commits[:10]:
            h.update(c.get("hash", "").encode())
            h.update(c.get("message", "").encode())
        h.update(str(metadata.get("origin_url", "")).encode())
        h.update(str(metadata.get("tag_count", 0)).encode())
        h.update(str(metadata.get("branch_count", 0)).encode())
        return h.hexdigest()

    @staticmethod
    def _repo_size(repo_path: str) -> int:
        total = 0
        for dirpath, _dirnames, filenames in os.walk(repo_path):
            for f in filenames:
                fp = Path(dirpath) / f
                with contextlib.suppress(OSError):
                    total += fp.stat().st_size
        return total


def _git_cmd(repo_path: str, args: list[str]) -> str | None:
    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=repo_path,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        return None
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("git command failed: %s — %s", " ".join(cmd), exc)
        return None


def _sanitize_git_url(url: str) -> str:
    if url.startswith("git@") and ":" in url:
        return url
    if url.startswith("http://"):
        return url
    if url.startswith("https://"):
        return url
    return url


def _find_readme(repo_path: str) -> str | None:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        p = Path(repo_path) / name
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return None
    return None


def _compute_git_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("commit_count", 0) > 0:
        q += 0.2
    if metadata.get("tag_count", 0) > 0:
        q += 0.15
    if metadata.get("branch_count", 0) > 0:
        q += 0.1
    if metadata.get("origin_url"):
        q += 0.15
    if metadata.get("readme_preview"):
        q += 0.1
    if metadata.get("commit_count", 0) >= 10:
        q += 0.1
    return min(q, 1.0)


_registry = get_registry()
_registry.register(GitExtractor())
