"""Compiler — source/ → KnowledgeObject → SQLite.

Coordina el pipeline DAG:
  scanner → parser → validator → writer

Nunca parsea directamente.
Nunca escribe SQL directamente.

Protección contra race conditions:
  1. Scanner toma snapshot (hash + content bytes) de todo source/
  2. Parser + validator trabajan sobre datos en memoria (source.content)
  3. Antes de writer, verifica que el snapshot no haya cambiado
  4. Si cambió → compile inválido, reencolar
  5. Writer ejecuta BEGIN IMMEDIATE…COMMIT

Máquina de estados: CompileStage (DISCOVERING → PARSING → VALIDATING → WRITING → DONE/FAILED)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from knowledge.engine.models import (
    CompileContext,
    CompileError,
    CompileFeatures,
    CompileMetadata,
    CompileOptions,
    CompileResult,
    CompileStage,
    KnowledgeObject,
    Snapshot,
    SourceObject,
    doc_id_from_path,
)
from knowledge.engine.parser import parse_source
from knowledge.engine.qdrant_sync import sync_documents
from knowledge.engine.scanner import scan_incremental, scan_source_stream
from knowledge.engine.scanner import take_snapshot as take_snapshot_fn
from knowledge.engine.sqlite_writer import apply_compile
from knowledge.engine.validator import validate_batch

log = logging.getLogger("ura.knowledge.compiler")


def compile_source(
    source_dir: Path | None = None,
    db_path: Path | None = None,
    compiler_version: str = "0.1.0",
    previous_snapshot: Snapshot | None = None,
    max_parse_size: int = 10_485_760,
    correlation_id: str = "",
) -> CompileResult:
    """Compila source/ → knowledge.db.

    Pipeline DAG:
      1. Scanner: toma snapshot + descubre SourceObjects (con content bytes)
      2. Parser: Markdown → KnowledgeObject (sin tocar el filesystem)
      3. Validator: valida contra tipos, calidad, relaciones rotas
      4. Writer: BEGIN IMMEDIATE → escribe nodos/edges/errores → COMMIT

    Si previous_snapshot se proporciona, solo procesa los archivos cambiados.
    """
    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    if db_path is None:
        db_path = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"

    opts = CompileOptions(
        source_dir=str(source_dir),
        db_path=str(db_path),
        compiler_version=compiler_version,
        incremental=previous_snapshot is not None,
        max_parse_size=max_parse_size,
    )
    features = CompileFeatures(parser_version=compiler_version)
    meta = CompileMetadata(
        source_commit="HEAD",
        features=features,
        correlation_id=correlation_id,
    )

    # ── Stage 1: DISCOVERING ─────────────────────────────────────────────
    ctx = CompileContext(
        metadata=meta,
        options=opts,
        stage=CompileStage.DISCOVERING,
    )
    t0 = time.monotonic()

    changed, snapshot, scanner_skipped, deleted = scan_incremental(previous_snapshot, source_dir)

    if previous_snapshot and not changed and not deleted:
        return CompileResult(
            success=True,
            graph_version=0,
            source_commit=meta.source_commit,
            compiler_version=compiler_version,
            documents_total=0,
            documents_changed=0,
            stage=CompileStage.DONE.value,
        )

    all_errors: list[CompileError] = list(scanner_skipped)
    all_warnings: list[CompileError] = []

    # Register deletions as INFO
    for d in deleted:
        all_warnings.append(
            CompileError(
                code="KE207",
                document=d.path,
                stage="compiler",
                message=f"Documento eliminado: {d.path}",
                category="permanent",
            )
        )

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        snapshot=snapshot,
        stage=CompileStage.PARSING,
    )

    # ── Stage 2: PARSING ────────────────────────────────────────────────
    objects: list[KnowledgeObject] = []
    for so in changed:
        result = parse_source(so)
        if isinstance(result, CompileError):
            all_errors.append(result)
        else:
            objects.append(result)

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        snapshot=snapshot,
        stage=CompileStage.VALIDATING,
    )

    # ── Stage 3: VALIDATING ─────────────────────────────────────────────
    valid_objects, validate_errors, validate_warnings = validate_batch(objects)
    all_errors.extend(validate_errors)
    all_warnings.extend(validate_warnings)

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        snapshot=snapshot,
        stage=CompileStage.WRITING,
        errors=tuple(all_errors),
        warnings=tuple(all_warnings),
    )

    # ── Stage 4: WRITING ────────────────────────────────────────────────
    deleted_ids = _resolve_deleted_ids(deleted, previous_snapshot)
    result = apply_compile(
        db_path=db_path,
        objects=valid_objects,
        ctx=ctx,
        errors=all_errors,
        warnings=all_warnings,
        deleted_ids=deleted_ids,
    )

    duration = time.monotonic() - t0
    final_stage = CompileStage.DONE if result.success else CompileStage.FAILED

    # Stage 5: SEMANTIC SYNC (post-commit, graceful degradation)
    if result.success:
        docs = [ko.document for ko in valid_objects] if valid_objects else []
        synced = sync_documents(db_path=db_path, docs=docs, deleted_ids=deleted_ids, run_id=result.run_id)
        if synced > 0:
            log.info("Sincronización semántica: %d operaciones (run %d)", synced, result.run_id)

        # Persistir snapshot para compilación incremental
        try:
            from knowledge.engine.snapshot_store import save_snapshot
            import subprocess

            commit = subprocess.run(  # noqa: S603,S607
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=source_dir, check=False,
            ).stdout.strip() or "HEAD"
            save_snapshot(snapshot, commit)
        except Exception as exc:
            log.warning("No se pudo persistir snapshot: %s", exc)

        # Determinism hash (post-commit, graba en kg_active_version)
        _record_determinism_hash(db_path, result.run_id)

    # Auditoría (best effort, tanto success como failure)
    try:
        from knowledge.engine.audit import get_audit

        get_audit().log_compile(
            result="success" if result.success else "failure",
            correlation_id=correlation_id,
            docs_changed=getattr(result, "documents_changed", 0),
            errors=len(result.errors) if hasattr(result, "errors") else 0,
            duration_ms=round(duration * 1000),
        )
    except Exception:
        pass

    return CompileResult(
        success=result.success,
        graph_version=result.graph_version,
        source_commit=meta.source_commit,
        compiler_version=compiler_version,
        documents_total=len(changed),
        documents_changed=result.documents_changed,
        errors=result.errors,
        warnings=result.warnings,
        duration_ms=duration * 1000,
        stage=final_stage.value,
    )


def compile_source_streaming(
    source_dir: Path | None = None,
    db_path: Path | None = None,
    compiler_version: str = "0.1.0",
    max_parse_size: int = 10_485_760,
    correlation_id: str = "",
) -> CompileResult:
    """Compilación streaming — no acumula SourceObjects en RAM.

    Scanner → yield → Parser → collect KnowledgeObjects → Validator → Writer.
    Los content bytes se liberan tras cada parseo.
    Adecuado para >1000 documentos donde la RAM es crítica.
    """
    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    if db_path is None:
        db_path = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"

    opts = CompileOptions(
        source_dir=str(source_dir),
        db_path=str(db_path),
        compiler_version=compiler_version,
        max_parse_size=max_parse_size,
    )
    features = CompileFeatures(parser_version=compiler_version)
    meta = CompileMetadata(
        source_commit="HEAD",
        features=features,
        correlation_id=correlation_id,
    )

    all_errors: list[CompileError] = []
    all_warnings: list[CompileError] = []
    objects: list[KnowledgeObject] = []
    changed_count = 0

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        stage=CompileStage.DISCOVERING,
    )

    t0 = time.monotonic()

    # Stream: yield → parse → free → collect
    for item in scan_source_stream(source_dir):
        if isinstance(item, CompileError):
            all_errors.append(item)
            continue
        changed_count += 1
        result = parse_source(item)
        if isinstance(result, CompileError):
            all_errors.append(result)
        else:
            objects.append(result)
        # item (SourceObject con content bytes) sale de scope → GC libera

    snapshot = take_snapshot_fn(source_dir)

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        snapshot=snapshot,
        stage=CompileStage.VALIDATING,
    )
    valid_objects, validate_errors, validate_warnings = validate_batch(objects)
    all_errors.extend(validate_errors)
    all_warnings.extend(validate_warnings)

    ctx = CompileContext(
        metadata=meta,
        options=opts,
        snapshot=snapshot,
        stage=CompileStage.WRITING,
        errors=tuple(all_errors),
        warnings=tuple(all_warnings),
    )

    result = apply_compile(
        db_path=db_path,
        objects=valid_objects,
        ctx=ctx,
        errors=all_errors,
        warnings=all_warnings,
        deleted_ids=[],
    )

    duration = time.monotonic() - t0
    final_stage = CompileStage.DONE if result.success else CompileStage.FAILED

    return CompileResult(
        success=result.success,
        graph_version=result.graph_version,
        source_commit=meta.source_commit,
        compiler_version=compiler_version,
        documents_total=changed_count,
        documents_changed=result.documents_changed,
        errors=result.errors,
        warnings=result.warnings,
        duration_ms=duration * 1000,
        stage=final_stage.value,
    )


def _resolve_deleted_ids(
    deleted: list[SourceObject] | None,
    previous_snapshot: Snapshot | None,
) -> list[str]:
    """Resuelve los doc_ids de los archivos eliminados."""
    if not previous_snapshot or not deleted:
        return []
    return [doc_id_from_path(d.path) for d in deleted]


def _record_determinism_hash(db_path: Path, run_id: int) -> None:
    """Calcula y persiste el hash de determinismo + versionado del algoritmo.

    Delega en determinism.py para evitar duplicación y garantizar
    que determinism_algorithm se escriba correctamente.
    """
    from knowledge.engine.determinism import record_determinism_hash

    record_determinism_hash(db_path, run_id)


def compile_incremental(
    source_dir: Path | None = None,
    db_path: Path | None = None,
    compiler_version: str = "0.1.0",
    correlation_id: str = "",
) -> CompileResult:
    """Compilación incremental: solo procesa documentos modificados.

    Carga el snapshot anterior, lo pasa a compile_source() como
    previous_snapshot para skip de archivos no modificados.
    compile_source() se encarga de persistir el nuevo snapshot.

    Returns:
        CompileResult con documents_changed = 0 si no hay cambios.
    """
    from knowledge.engine.snapshot_store import load_snapshot

    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    if db_path is None:
        db_path = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"

    previous_snapshot = load_snapshot()
    log.info(
        "Incremental: %s",
        "con snapshot" if previous_snapshot else "sin snapshot (compile completo)",
    )

    return compile_source(
        source_dir=source_dir,
        db_path=db_path,
        compiler_version=compiler_version,
        previous_snapshot=previous_snapshot,
        correlation_id=correlation_id,
    )
