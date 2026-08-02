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
import shutil
import subprocess
import time as _time
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
            msg = f"{label}: {path} (resuelto: {parent}) está fuera de {allowed}"
            raise PathTraversalError(msg)

    if not str(resolved).startswith(str(allowed.resolve())):
        msg = f"{label}: {path} (resuelto: {resolved}) está fuera de {allowed}"
        raise PathTraversalError(msg)
    return resolved


def _validate_source_dir(source_dir: Path, allowed_root: Path | None = None) -> Path:
    """Valida que source_dir esté dentro de *allowed_root*.

    Si allowed_root es None, solo verifica que el path sea absoluto
    y no contenga '..' (resolve ya lo maneja).
    """
    resolved = source_dir.resolve()
    if allowed_root is not None and not str(resolved).startswith(str(allowed_root.resolve())):
        msg = f"source_dir: {source_dir} (resuelto: {resolved}) está fuera de {allowed_root}"
        raise PathTraversalError(msg)
    return resolved


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _git_cmd(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    git_path = shutil.which("git") or "/usr/bin/git"
    return subprocess.run(
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
    _t0 = _time.monotonic()
    if source_dir is None:
        source_dir = _PROJECT_ROOT / "source"
    source_dir = _validate_source_dir(source_dir)  # allowed_root=None → solo abs

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    archive_dir = _ensure_dir(archive_dir or _DEFAULT_ARCHIVE_DIR)

    commit = _verificar_git_commit(source_dir)
    file_count = _contar_tracked(source_dir)

    bundle_path = _archive_path(archive_dir, "source", timestamp)
    compressed_size = _crear_bundle(source_dir, bundle_path)
    content_sha256 = _calcular_sha256(bundle_path)

    manifest = _construir_manifest(
        commit,
        timestamp,
        bundle_path,
        compressed_size,
        content_sha256,
        file_count,
        retention_days,
    )

    manifest_path = _escribir_manifest(manifest)

    if db_path:
        _registrar_en_db(db_path, manifest, manifest_path, bundle_path, compressed_size)

    _registrar_audit_y_metricas(commit, file_count, compressed_size, _t0)
    return manifest


def _verificar_git_commit(source_dir: Path) -> str:
    """Verifica que es repo git y devuelve el commit actual."""
    result = _git_cmd("rev-parse", "HEAD", cwd=source_dir)
    if result.returncode != 0:
        msg = f"source_dir no es un repositorio git: {source_dir}\nstderr: {result.stderr.strip()}"
        raise ValueError(msg)
    return result.stdout.strip()


def _contar_tracked(source_dir: Path) -> int:
    result = _git_cmd("ls-files", cwd=source_dir)
    return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0


def _crear_bundle(source_dir: Path, bundle_path: Path) -> int:
    result = _git_cmd(
        "bundle",
        "create",
        str(bundle_path),
        "--all",
        "--quiet",
        cwd=source_dir,
    )
    if result.returncode != 0:
        msg = f"Error creando git bundle: {result.stderr.strip()}"
        raise RuntimeError(msg)
    return bundle_path.stat().st_size


def _calcular_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def _construir_manifest(
    commit: str,
    timestamp: str,
    bundle_path: Path,
    compressed_size: int,
    content_sha256: str,
    file_count: int,
    retention_days: int | None,
) -> ArchiveManifest:
    return ArchiveManifest(
        kind="source",
        source_commit=commit,
        created_at=timestamp,
        archive_path=str(bundle_path),
        compressed_size=compressed_size,
        content_sha256=content_sha256,
        file_count=file_count,
        retention_days=retention_days or ARCHIVE_RETENTION_DAYS.get("source", 90),
    )


def _escribir_manifest(manifest: ArchiveManifest) -> Path:
    manifest_path = _manifest_path(Path(manifest.archive_path).parent, "source", manifest.created_at)
    with manifest_path.open("w") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
    log.info(
        "Source archived: commit=%s bundle=%s size=%d files=%d sha256=%s",
        manifest.source_commit[:12],
        Path(manifest.archive_path).name,
        manifest.compressed_size,
        manifest.file_count,
        manifest.content_sha256[:16],
    )
    return manifest_path


def _registrar_en_db(
    db_path: Path,
    manifest: ArchiveManifest,
    manifest_path: Path,
    bundle_path: Path,
    compressed_size: int,
) -> None:
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
                manifest.source_commit,
                str(manifest_path),
                str(bundle_path),
                compressed_size,
                manifest.content_sha256,
                manifest.retention_days,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.warning("No se pudo registrar en op_archives: %s", exc)


def _registrar_audit_y_metricas(commit: str, file_count: int, compressed_size: int, _t0: float) -> None:
    try:
        from knowledge.engine.audit import get_audit

        get_audit().log_archive(
            kind="source",
            result="success",
            commit=commit[:12],
            file_count=file_count,
            size_bytes=compressed_size,
        )
    except Exception:  # noqa: S110
        pass

    try:
        from knowledge.engine.metrics import archive_duration_seconds

        archive_duration_seconds.observe(_time.monotonic() - _t0)
    except Exception:  # noqa: S110
        pass


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
    manifest_path = _resolver_dentro(allowed, Path(manifest_path), "manifest_path")
    if manifest_path is None or not manifest_path.exists():
        log.error("Manifest no encontrado: %s", manifest_path)
        return False

    manifest = _cargar_manifest_archivo(manifest_path)
    if manifest is None:
        return False

    archive = _resolver_dentro(allowed, Path(manifest.archive_path), "archive_path")
    if archive is None or not archive.exists():
        log.error("Archive no encontrado: %s", archive)
        return False

    actual_hash = _calcular_sha256(archive)
    if actual_hash != manifest.content_sha256:
        log.error(
            "SHA-256 mismatch: esperado=%s real=%s",
            manifest.content_sha256[:16],
            actual_hash[:16],
        )
        return False

    log.info("Archive verified: %s sha256=%s", archive.name, actual_hash[:16])
    return True


def _resolver_dentro(allowed: Path, path: Path, nombre: str) -> Path | None:
    try:
        return _resolve_within(path, allowed, nombre)
    except PathTraversalError as exc:
        log.exception("Path traversal denegado: %s", exc)
        return None


def _cargar_manifest_archivo(manifest_path: Path) -> ArchiveManifest | None:
    try:
        raw = manifest_path.read_text()
        return ArchiveManifest.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        log.exception("Manifest inválido: %s", exc)
        return None


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
    manifest_path = _resolver_dentro(allowed, Path(manifest_path), "manifest_path")
    if manifest_path is None:
        msg = f"Path traversal denegado en manifest: {manifest_path}"
        raise ValueError(msg)

    if not verify_archive(manifest_path, archive_dir=allowed):
        msg = f"Archive no pasó verificación: {manifest_path}"
        raise ValueError(msg)

    manifest = _cargar_manifest_archivo(manifest_path)
    if manifest is None:
        msg = f"Manifest inválido: {manifest_path}"
        raise ValueError(msg)

    if dest_dir is None:
        dest_dir = _PROJECT_ROOT / "source"
    dest_dir = _validate_source_dir(dest_dir)

    bundle_path = _resolver_dentro(allowed, Path(manifest.archive_path), "archive_path")
    if bundle_path is None:
        msg = f"Path traversal denegado en archive_path del manifest: {bundle_path}"
        raise ValueError(msg)

    if not bundle_path.exists():
        msg = f"Bundle no encontrado: {bundle_path}"
        raise FileNotFoundError(msg)

    _clonar_bundle(bundle_path, dest_dir, manifest.source_commit)

    log.info(
        "Source restored: commit=%s bundle=%s dest=%s",
        manifest.source_commit[:12] if manifest.source_commit else "none",
        bundle_path.name,
        dest_dir,
    )
    return manifest.source_commit


def _clonar_bundle(bundle_path: Path, dest_dir: Path, source_commit: str | None) -> None:
    """Clona desde bundle y hace checkout del commit archivado."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", str(bundle_path), str(dest_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"Error restaurando desde bundle: {result.stderr.strip()}"
        raise RuntimeError(msg)

    if source_commit:
        result = _git_cmd("checkout", source_commit, cwd=dest_dir)
        if result.returncode != 0:
            msg = f"Error haciendo checkout de {source_commit}: {result.stderr.strip()}"
            raise RuntimeError(msg)


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
            "FROM op_archives ORDER BY archived_at DESC",
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.debug("Error leyendo op_archives: %s", exc)
        return []
