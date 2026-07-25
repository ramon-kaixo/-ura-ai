#!/usr/bin/env python3
"""CLI principal del pipeline tuneladora v7.0."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue
from scripts.pro.tuneladora.pipeline.runner import PipelineRunner
from scripts.pro.tuneladora.pipeline.tools.base import Status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("tuneladora.cli")


def _auto_fix_merge_conflicts() -> None:
    import re
    root = Path(__file__).resolve().parent.parent.parent.parent
    fixed = 0
    targets = [
        root / 'core', root / 'motor', root / 'scripts', root / 'tests',
        root / 'monitor', root / 'app', root / 'sandbox',
        root / 'pyproject.toml',
    ]
    for target in targets:
        if target.is_dir():
            files = list(target.rglob('*.py')) + list(target.rglob('*.toml'))
        elif target.is_file():
            files = [target]
        else:
            continue
        for fp in files:
            if any(x in str(fp) for x in ('__pycache__', '.tuneladora/', 'build/')):
                continue
            try:
                with open(fp) as f:
                    content = f.read()
                new_content = content
                has_conflicts = '<<<<<<<' in content
                needs_import_fix = ('from core.config import' in content
                                    and fp.name in ('config_manager.py', 'config.py'))
                if not has_conflicts and not needs_import_fix:
                    continue
                if has_conflicts:
                    for _ in range(10):
                        new_content = re.sub(r'<<<<<<< .*?\n', '', new_content)
                        new_content = re.sub(r'=======\n', '', new_content)
                        new_content = re.sub(r'>>>>>>> .*?\n', '', new_content)
                    new_content = re.sub(r'\n{3,}', '\n\n', new_content)
                if needs_import_fix:
                    new_content = new_content.replace(
                        'from core.config import',
                        'from motor.core.config import',
                    )
                if new_content != content:
                    with open(fp, 'w') as f:
                        f.write(new_content)
                    fixed += 1
            except (OSError, UnicodeDecodeError):
                pass
    if fixed:
        log.info("Auto-fixed %d files with merge conflicts or broken imports", fixed)


def cmd_pending(cfg: Configuration) -> None:
    queue = PendingQueue(cfg.knowledge_db)
    items = queue.list_pending()
    if not items:
        print("No pending fixes.")
        return
    print(f"{'ID':<5} {'Estado':<12} {'Herramienta':<10} {'Archivo':<30} {'Resumen':<40}")
    print("-" * 100)
    for item in items:
        summary = item.get("error_raw", "")[:40]
        print(f"{item['id']:<5} {item['estado']:<12} {item['herramienta']:<10} {item['archivo']:<30} {summary:<40}")


def cmd_stats(cfg: Configuration) -> None:
    queue = PendingQueue(cfg.knowledge_db)
    s = queue.stats()
    print(f"Pending fixes:  {s['pending_fixes']}")
    print(f"Total runs:     {s['total_runs']}")
    print(f"OK runs:        {s['ok_runs']}")
    print(f"FAIL runs:      {s['fail_runs']}")


def cmd_rollback(cfg: Configuration) -> None:
    from scripts.pro.tuneladora.pipeline.snapshot_manager import SnapshotManager
    sm = SnapshotManager(cfg.tuneladora_dir, log.info)
    latest = sm.latest()
    if not latest:
        print("No snapshots found.")
        return
    print(f"Restoring snapshot: {latest.name}")
    ok = sm.restore(latest)
    print("Restore OK" if ok else "Restore FAILED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tuneladora Pipeline v7.0 — CI/auto-fix pipeline for URA")
    parser.add_argument("--mode", choices=["check", "fix", "gate"], default="check",
                        help="Pipeline mode: check (validate), fix (auto-fix), gate (fix + commit)")
    parser.add_argument("--files", nargs="*", default=None,
                        help="Specific files to process (default: auto-detect via git diff)")
    parser.add_argument("--pending", action="store_true", help="List pending fixes")
    parser.add_argument("--stats", action="store_true", help="Show pipeline run statistics")
    parser.add_argument("--rollback", action="store_true", help="Restore the latest snapshot")
    args = parser.parse_args()

    cfg = Configuration()

    _auto_fix_merge_conflicts()

    if args.pending:
        cmd_pending(cfg); return
    if args.stats:
        cmd_stats(cfg); return
    if args.rollback:
        cmd_rollback(cfg); return

    runner = PipelineRunner(cfg, mode=args.mode, files=args.files)
    verdict = runner.run()

    if verdict == Status.FAIL:
        log.error("Pipeline FAILED")
        sys.exit(1)
    elif verdict == Status.WARN:
        log.warning("Pipeline passed with warnings")
        sys.exit(0)
    else:
        log.info("Pipeline OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
