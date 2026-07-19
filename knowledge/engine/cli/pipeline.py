"""CLI: pipeline run."""

from pathlib import Path

from knowledge.engine.cli.main import _resolve_db_path
from knowledge.engine.pipeline import Pipeline


def cmd_pipeline_run(args) -> int:
    db_path = _resolve_db_path(args) if not hasattr(args, "db_path") or not args.db_path else Path(args.db_path)
    source_dir = Path(args.source_dir).resolve() if hasattr(args, "source_dir") and args.source_dir else None
    archive_dir = Path(args.archive_dir) if hasattr(args, "archive_dir") and args.archive_dir else None

    pipeline = Pipeline(source_dir=source_dir, db_path=db_path or None, archive_dir=archive_dir)
    result = pipeline.run()

    for s in result.stages:
        f" — {s.error[:60]}" if s.error else ""
    return 0 if result.success else 1
