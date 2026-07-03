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

    print(f"Pipeline: {'✅' if result.success else '❌'} ({result.total_duration_ms:.0f}ms)")
    for s in result.stages:
        icon = "✅" if s.success else "❌"
        err = f" — {s.error[:60]}" if s.error else ""
        print(f"  {icon} {s.stage.value}: {s.duration_ms:.0f}ms{err}")
    return 0 if result.success else 1
