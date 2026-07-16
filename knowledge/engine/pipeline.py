"""Pipeline DAG — orquestación determinista de etapas del Knowledge Engine.

Etapas:
  1. snapshot  — Scanner: descubre archivos fuente, calcula snapshot
  2. compile   — Compiler: parsea, valida, escribe en SQLite
  3. verify    — Verifier: integridad del grafo post-compile
  4. archive   — Archiver: git bundle + manifest (si retention lo requiere)
  5. qdrant    — QdrantSync: sincronización semántica
  6. rule_eval — RuleEvaluator: reglas de calidad R001-R005

Principios:
  - Cada etapa es una función pura (entrada → resultado, sin side effects ocultos).
  - El pipeline es determinista: mismas entradas → mismas salidas.
  - Las etapas fallan independientemente (no cascada).
  - No modifica el núcleo: usa interfaces existentes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from knowledge.engine._compat import StrEnum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("ura.knowledge.pipeline")


class Stage(StrEnum):
    SNAPSHOT = "snapshot"
    COMPILE = "compile"
    VERIFY = "verify"
    ARCHIVE = "archive"
    QDRANT = "qdrant"
    RULE_EVAL = "rule_eval"
    CI = "ci"


@dataclass(frozen=True)
class StageResult:
    """Resultado de una etapa del pipeline."""

    stage: Stage
    success: bool
    duration_ms: float
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class PipelineResult:
    """Resultado completo del pipeline."""

    stages: list[StageResult]
    total_duration_ms: float
    success: bool
    correlation_id: str = ""


# ── Stage runners ─────────────────────────────────────────────────────────


def _run_snapshot(
    source_dir: Path,
    previous_snapshot: Any = None,
) -> StageResult:
    """Stage 1: Scanner — descubre archivos y calcula cambios."""
    t0 = time.monotonic()
    try:
        from knowledge.engine.scanner import scan_incremental

        changed, snapshot, skipped, deleted = scan_incremental(previous_snapshot, source_dir)
        return StageResult(
            stage=Stage.SNAPSHOT,
            success=True,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={
                "changed": len(changed),
                "deleted": len(deleted),
                "snapshot": snapshot,
                "skipped": [str(s) for s in skipped],
            },
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.SNAPSHOT,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


def _run_compile(
    source_dir: Path,
    db_path: Path,
    correlation_id: str = "",
) -> StageResult:
    """Stage 2: Compiler."""
    t0 = time.monotonic()
    try:
        from knowledge.engine.compiler import compile_source

        result = compile_source(
            source_dir=source_dir,
            db_path=db_path,
            correlation_id=correlation_id,
        )
        return StageResult(
            stage=Stage.COMPILE,
            success=result.success,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={
                "documents_total": result.documents_total,
                "documents_changed": result.documents_changed,
                "errors": len(result.errors),
                "warnings": len(result.warnings),
                "graph_version": result.graph_version,
            },
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.COMPILE,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


def _run_verify(db_path: Path) -> StageResult:
    """Stage 3: Verifier — integridad del grafo."""
    t0 = time.monotonic()
    try:
        from knowledge.engine.verifier import verify_graph

        results = verify_graph(db_path)
        errors = [r for r in results if r[0] == "ERROR"]
        return StageResult(
            stage=Stage.VERIFY,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={"checks": len(results), "errors": len(errors)},
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.VERIFY,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


def _run_archive(source_dir: Path, db_path: Path, archive_dir: Path | None = None) -> StageResult:
    """Stage 4: Archiver — git bundle opcional."""
    t0 = time.monotonic()
    try:
        from knowledge.engine.archiver import archive_source

        manifest = archive_source(
            source_dir=source_dir,
            db_path=db_path,
            archive_dir=archive_dir,
        )
        return StageResult(
            stage=Stage.ARCHIVE,
            success=True,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={
                "commit": manifest.source_commit[:12] if manifest.source_commit else "",
                "files": manifest.file_count,
                "sha256": manifest.content_sha256[:16],
            },
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.ARCHIVE,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


def _run_qdrant(db_path: Path) -> StageResult:
    """Stage 5: Qdrant sync — graceful degradation.

    Nota: sync_documents requiere docs y deleted_ids (obtenidos del compile).
    El pipeline obtiene estos datos del resultado del compile stage.
    Si no hay datos de compile, intenta sync con lista vacía.
    """
    t0 = time.monotonic()
    try:
        from knowledge.engine.qdrant_sync import sync_documents

        # En un pipeline completo, estos vendrían del stage COMPILE.
        # Por ahora, intentamos sync sin datos (no-op controlado).
        synced = sync_documents(db_path=db_path, docs=[], deleted_ids=[])
        return StageResult(
            stage=Stage.QDRANT,
            success=True,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={"synced": synced},
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.QDRANT,
            success=True,  # graceful degradation
            duration_ms=(time.monotonic() - t0) * 1000,
            output={"synced": 0},
            error=f"Qdrant: {exc}" if exc else "",
        )


def _run_ci() -> StageResult:
    """Stage CI: ejecuta scripts/ci.sh y reporta resultados.

    Convierte el pipeline en un meta-evaluador: puede ejecutarse a sí mismo.
    """
    import subprocess

    t0 = time.monotonic()
    try:
        script = Path(__file__).resolve().parent.parent.parent / "scripts" / "ci.sh"
        if not script.exists():
            return StageResult(
                stage=Stage.CI,
                success=False,
                duration_ms=(time.monotonic() - t0) * 1000,
                error=f"CI script not found: {script}",
            )
        r = subprocess.run(  # noqa: S603  -- script desde CI config, no input externo
            ["bash", str(script)],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=300,
        )
        return StageResult(
            stage=Stage.CI,
            success=r.returncode == 0,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={"returncode": r.returncode, "stdout_preview": r.stdout[-300:]},
            error=r.stderr[-200:] if r.returncode != 0 else "",
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.CI,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


def _run_rule_eval(db_path: Path) -> StageResult:
    """Stage 6: Rule evaluation — calidad del conocimiento."""
    t0 = time.monotonic()
    try:
        from knowledge.engine.connection import open_db
        from knowledge.engine.rules import RuleEvaluator
        import json

        conn = open_db(db_path)
        rows = conn.execute("SELECT id, type, path, frontmatter, body FROM kg_nodes").fetchall()
        edges = conn.execute("SELECT src, dst FROM kg_edges").fetchall()
        conn.close()

        all_node_ids = {r["id"] for r in rows}
        all_targets = {e["dst"] for e in edges}
        documents = []
        for r in rows:
            fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
            documents.append(
                {
                    "id": r["id"],
                    "path": r["path"],
                    "title": fm.get("title", ""),
                    "tags": fm.get("tags", []),
                    "body": r["body"] or "",
                    "relations": [e["dst"] for e in edges if e["src"] == r["id"]],
                }
            )

        evaluator = RuleEvaluator()
        findings = evaluator.evaluate(documents, all_node_ids, all_targets)
        return StageResult(
            stage=Stage.RULE_EVAL,
            success=True,
            duration_ms=(time.monotonic() - t0) * 1000,
            output={
                "documents": len(documents),
                "findings": len(findings),
                "errors": len([f for f in findings if f.severity == "ERROR"]),
            },
        )
    except Exception as exc:
        return StageResult(
            stage=Stage.RULE_EVAL,
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000,
            error=str(exc),
        )


# ── Pipeline ──────────────────────────────────────────────────────────────


class Pipeline:
    """Pipeline DAG determinista.

    Uso:
        pipeline = Pipeline(source_dir=..., db_path=...)
        result = pipeline.run(stages=[Stage.COMPILE, Stage.RULE_EVAL])
    """

    def __init__(
        self,
        source_dir: Path | None = None,
        db_path: Path | None = None,
        archive_dir: Path | None = None,
    ):
        self._source_dir = source_dir or Path.cwd()
        self._db_path = db_path or Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"
        self._archive_dir = archive_dir

    def run(
        self,
        stages: list[Stage] | None = None,
        correlation_id: str = "",
    ) -> PipelineResult:
        """Ejecuta las etapas del pipeline en orden.

        Args:
            stages: Etapas a ejecutar. None = todas.
            correlation_id: ID de correlación para trazabilidad.

        Returns:
            Resultado completo del pipeline.
        """
        import uuid

        cid = correlation_id or uuid.uuid4().hex
        all_stages = stages or list(Stage)
        results: list[StageResult] = []
        t0 = time.monotonic()

        runners: dict[Stage, Callable] = {
            Stage.SNAPSHOT: lambda: _run_snapshot(self._source_dir),
            Stage.COMPILE: lambda: _run_compile(self._source_dir, self._db_path, cid),
            Stage.VERIFY: lambda: _run_verify(self._db_path),
            Stage.ARCHIVE: lambda: _run_archive(self._source_dir, self._db_path, self._archive_dir),
            Stage.QDRANT: lambda: _run_qdrant(self._db_path),
            Stage.RULE_EVAL: lambda: _run_rule_eval(self._db_path),
            Stage.CI: lambda: _run_ci(),
        }

        for stage in all_stages:
            runner = runners.get(stage)
            if runner is None:
                results.append(
                    StageResult(
                        stage=stage,
                        success=False,
                        duration_ms=0,
                        error=f"Unknown stage: {stage}",
                    )
                )
                continue
            log.info("Pipeline stage: %s", stage)
            result = runner()
            results.append(result)
            log.info(
                "Stage %s: %s (%dms)",
                stage,
                "OK" if result.success else "FAIL",
                result.duration_ms,
            )

        total = (time.monotonic() - t0) * 1000
        overall = all(r.success for r in results)
        return PipelineResult(
            stages=results,
            total_duration_ms=total,
            success=overall,
            correlation_id=cid,
        )

    def run_compile_chain(self) -> PipelineResult:
        """Ejecuta la cadena completa: compile → verify → rule_eval."""
        return self.run(stages=[Stage.COMPILE, Stage.VERIFY, Stage.RULE_EVAL])
