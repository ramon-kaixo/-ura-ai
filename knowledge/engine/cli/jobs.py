"""CLI: job-process."""

from pathlib import Path

from knowledge.engine.cli.main import _resolve_db_path
from knowledge.engine.orchestrator import compile_worker


def cmd_job_process(args) -> int:
    db_path = _resolve_db_path(args)
    source_dir = Path(args.source_dir) if hasattr(args, "source_dir") and args.source_dir else None
    compile_worker(db_path=db_path, source_dir=source_dir)
    return 0
