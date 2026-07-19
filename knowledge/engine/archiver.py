"""Archiver — backup y restore de source + vectores del Knowledge Engine.

Principios:
- El grafo (kg_*) NO se archiva. Se regenera desde source vía ke compile.
- Source se archiva como git bundle (reproducible, comprimido por git).
- Vectores se archivan como dump de la colección Qdrant.
- Restore = checkout del bundle + ke compile (+ restore de vectores si aplica).

Tiering:
  hot:  knowledge.db + Qdrant vivo      (indefinido)
  warm: git bundle + Qdrant dump         (90 días por defecto)
  cold: tar.gz remoto (Mac/Hetzner)      (365 días)
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.engine.models import (
    ARCHIVE_RETENTION_DAYS,
    ArchiveManifest,
)

log = logging.getLogger("ura.knowledge.archiver")

_DEFAULT_ARCHIVE_DIR = Path.home() / "URA" / "archives"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Path validation ────────────────────────────────────────────────────────────


class PathTraversalError(ValueError):
    """El path proporcionado está fuera del directorio permitido."""


def _resolve_within(path: Path, allowed: Path, label: str = "path") -> Path:
    """Resuelve *path* y verifica que esté dentro de *allowed*.

    Raises PathTraversalError si no.
    """
    resolved = path.resolve()

    # Verificar que *algo* del path existe para poder resolverlo
    # Si no existe, resolve() falla o resuelve basado en CWD, lo cual es peligroso.
    # En ese caso, al menos verificamos que el path dado no contenga '..' malicioso
    # resolviendo su padre primero.
    if not resolved.exists():
        parent = Path(path).parent.resolve()
        if not str(parent).startswith(str(allowed.resolve())):
            raise PathTraversalError(f"{label}: {path} (resuelto: {parent}) está fuera de {allowed}")

    if not str(resolved).startswith(str(allowed.resolve())):
        raise PathTraversalError(f"{label}: {path} (resuelto: {resolved}) está fuera de {allowed}")
    return resolved


def _validate_source_dir(source_dir: Path, allowed_root: Path | None = None) -> Path:
    """Valida que source_dir esté dentro de *allowed_root*.

    Si allowed_root es None, solo verifica que el path sea absoluto
    y no contenga '..' (resolve ya lo maneja).
    """
    resolved = source_dir.resolve()
    if allowed_root is not None and not str(resolved).startswith(str(allowed_root.resolve())):
        raise PathTraversalError(f"source_dir: {source_dir} (resuelto: {resolved}) está fuera de {allowed_root}")
    return resolved


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _git_cmd(*args: str, cwd: Path) -> subprocess.CompletedProcess:  # noqa: S603,S607
    import shutil

    git_path = shutil.which("git") or "/usr/bin/git"
    return subprocess.run(  # noqa: S603  -- git wrapper interno, args desde callers del módulo
        [git_path, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def _manifest_path(archive_dir: Path, kind: str, timestamp: str) -> Path:
    return archive_dir / f"{kind}-{timestamp}.manifest.json"


def _archive_path(archive_dir: Path, kind: str, timestamp: str) -> Path:
    return archive_dir / f"{kind}-{timestamp}.bundle"


# ── API pública ────────────────────────────────────────────────────────────────


def archive_source(
    source_dir: Path | None = None,
    archive_dir: Path | None = None,
    db_path: Path | None = None,
    retention_days: int | None = None,
) -> ArchiveManifest:
    """Crea un git bundle del directorio source/.

    El bundle incluye todo el historial de git (--all).
    Si source_dir no es un repo git, la operación falla.
    """
    import time as _time

    _t0 = _time.monotonic()
    if source_dir is None:
        source_dir = _PROJECT_ROOT / "source"
    source_dir = _validate_source_dir(source_dir)  # allowed_root=None → solo abs

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    archive_dir = _ensure_dir(archive_dir or _DEFAULT_ARCHIVE_DIR)

    # 1. Verificar que es un repo git y obtener el commit actual
    result = _git_cmd("rev-parse", "HEAD", cwd=source_dir)
    if result.returncode != 0:
        raise ValueError(f"source_dir no es un repositorio git: {source_dir}\nstderr: {result.stderr.strip()}")
    commit = result.stdout.strip()

    # 2. Contar archivos tracked
    result = _git_cmd("ls-files", cwd=source_dir)
    file_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    # 3. Crear bundle
    bundle_path = _archive_path(archive_dir, "source", timestamp)
    result = _git_cmd(
        "bundle",
        "create",
        str(bundle_path),
        "--all",
        "--quiet",
        cwd=source_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error creando git bundle: {result.stderr.strip()}")

    compressed_size = bundle_path.stat().st_size

    # 4. Calcular SHA-256 del bundle
    sha256 = hashlib.sha256()
    with bundle_path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    content_sha256 = sha256.hexdigest()

    # 5. Construir manifest
    manifest = ArchiveManifest(
        kind="source",
        source_commit=commit,
        created_at=timestamp,
        archive_path=str(bundle_path),
        compressed_size=compressed_size,
        content_sha256=content_sha256,
        file_count=file_count,
        retention_days=retention_days or ARCHIVE_RETENTION_DAYS.get("source", 90),
    )

    # 6. Escribir manifest
    manifest_path = _manifest_path(archive_dir, "source", timestamp)
    with manifest_path.open("w") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
    log.info(
        "Source archived: commit=%s bundle=%s size=%d files=%d sha256=%s",
        commit[:12],
        bundle_path.name,
        compressed_size,
        file_count,
        content_sha256[:16],
    )

    # 7. Registrar en op_archives
    if db_path:
        try:
            from knowledge.engine.connection import begin_immediate, open_db

            conn = open_db(db_path)
            begin_immediate(conn)
            conn.execute(
                "INSERT INTO op_archives "
                "(kind, source_commit, manifest_path, archive_path, "
                " compressed_size, content_sha256, retention_days) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "source",
                    commit,
                    str(manifest_path),
                    str(bundle_path),
                    compressed_size,
                    content_sha256,
                    manifest.retention_days,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning("No se pudo registrar en op_archives: %s", exc)

    try:
        from knowledge.engine.audit import get_audit

        get_audit().log_archive(
            kind="source",
            result="success",
            commit=commit[:12],
            file_count=file_count,
            size_bytes=compressed_size,
        )
    except Exception:
        pass  # noqa: S110

    try:
        from knowledge.engine.metrics import archive_duration_seconds

        archive_duration_seconds.observe(_time.monotonic() - _t0)
    except Exception:
        pass  # noqa: S110
    return manifest


def verify_archive(
    manifest_path: str | Path,
    archive_dir: Path | None = None,
) -> bool:
    """Verifica la integridad de un archive contra su manifest.

    Comprueba:
    - El archivo existe
    - Su SHA-256 coincide con el del manifest
    - El manifest está bien formado

    Args:
        manifest_path: Ruta al archivo .manifest.json.
        archive_dir: Directorio permitido para el manifest y bundle.
                     Si es None, usa el directorio padre del manifest.

    Retorna True si todo es correcto.
    """
    allowed = archive_dir or _DEFAULT_ARCHIVE_DIR
    try:
        manifest_path = _resolve_within(Path(manifest_path), allowed, "manifest_path")
    except PathTraversalError as exc:
        log.error("Path traversal denegado: %s", exc)
        return False

    if not manifest_path.exists():
        log.error("Manifest no encontrado: %s", manifest_path)
        return False

    try:
        raw = manifest_path.read_text()
        data = json.loads(raw)
        manifest = ArchiveManifest.from_dict(data)
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("Manifest inválido: %s", exc)
        return False

    try:
        archive = _resolve_within(Path(manifest.archive_path), allowed, "archive_path")
    except PathTraversalError as exc:
        log.error("Path traversal denegado en archive_path del manifest: %s", exc)
        return False

    if not archive.exists():
        log.error("Archive no encontrado: %s", archive)
        return False

    # Verificar SHA-256 del archivo
    sha256 = hashlib.sha256()
    with archive.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()

    if actual_hash != manifest.content_sha256:
        log.error(
            "SHA-256 mismatch: esperado=%s real=%s",
            manifest.content_sha256[:16],
            actual_hash[:16],
        )
        return False

    log.info("Archive verified: %s sha256=%s", archive.name, actual_hash[:16])
    return True


def restore_source(
    manifest_path: str | Path,
    dest_dir: Path | None = None,
    db_path: Path | None = None,
    archive_dir: Path | None = None,
) -> str:
    """Restaura source desde un archive verificando integridad primero.

    Retorna el commit restaurado.
    Requiere que verify_archive() pase primero.
    """
    allowed = archive_dir or _DEFAULT_ARCHIVE_DIR
    try:
        manifest_path = _resolve_within(Path(manifest_path), allowed, "manifest_path")
    except PathTraversalError as exc:
        raise ValueError(f"Path traversal denegado en manifest: {exc}") from exc

    if not verify_archive(manifest_path, archive_dir=allowed):
        raise ValueError(f"Archive no pasó verificación: {manifest_path}")

    raw = manifest_path.read_text()
    data = json.loads(raw)
    manifest = ArchiveManifest.from_dict(data)

    if dest_dir is None:
        dest_dir = _PROJECT_ROOT / "source"
    dest_dir = _validate_source_dir(dest_dir)

    try:
        bundle_path = _resolve_within(Path(manifest.archive_path), allowed, "archive_path")
    except PathTraversalError as exc:
        raise ValueError(f"Path traversal denegado en archive_path del manifest: {exc}") from exc

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle no encontrado: {bundle_path}")

    # Clonar desde bundle
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(  # noqa: S603,S607
        ["git", "clone", str(bundle_path), str(dest_dir)],  # noqa: S607  -- paths validados con _resolve_within
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error restaurando desde bundle: {result.stderr.strip()}")

    # Hacer checkout exacto del commit archivado
    if manifest.source_commit:
        result = _git_cmd("checkout", manifest.source_commit, cwd=dest_dir)
        if result.returncode != 0:
            raise RuntimeError(f"Error haciendo checkout de {manifest.source_commit}: {result.stderr.strip()}")

    log.info(
        "Source restored: commit=%s bundle=%s dest=%s",
        manifest.source_commit[:12] if manifest.source_commit else "none",
        bundle_path.name,
        dest_dir,
    )
    return manifest.source_commit


def list_archives(archive_dir: Path | None = None) -> list[ArchiveManifest]:
    """Lista todos los manifests disponibles en el directorio de archives."""
    archive_dir = archive_dir or _DEFAULT_ARCHIVE_DIR
    if not archive_dir.is_dir():
        return []

    manifests: list[ArchiveManifest] = []
    for path in sorted(archive_dir.glob("*.manifest.json"), reverse=True):
        try:
            raw = path.read_text()
            data = json.loads(raw)
            manifests.append(ArchiveManifest.from_dict(data))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Saltando manifest corrupto %s: %s", path.name, exc)
            continue
    return manifests


def list_archives_from_db(db_path: Path) -> list[dict[str, Any]]:
    """Lista archives registrados en op_archives."""
    try:
        from knowledge.engine.connection import open_db

        conn = open_db(db_path)
        rows = conn.execute(
            "SELECT id, kind, source_commit, manifest_path, archive_path, "
            "       compressed_size, content_sha256, archived_at, retention_days "
            "FROM op_archives ORDER BY archived_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.debug("Error leyendo op_archives: %s", exc)
        return []
