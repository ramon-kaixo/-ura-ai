"""CLI: archive source, list, verify, restore."""

from pathlib import Path

from knowledge.engine.cli.main import _resolve_db_path


def cmd_archive_source(args) -> int:
    from knowledge.engine.archiver import archive_source

    source_dir = Path(args.source_dir) if hasattr(args, "source_dir") and args.source_dir else None
    archive_dir = Path(args.archive_dir) if hasattr(args, "archive_dir") and args.archive_dir else None
    retention = args.retention_days if hasattr(args, "retention_days") else None
    db_path = _resolve_db_path(args)
    archive_source(source_dir=source_dir, archive_dir=archive_dir, db_path=db_path, retention_days=retention)
    return 0


def cmd_archive_list(args) -> int:
    from knowledge.engine.archiver import list_archives

    archive_dir = Path(args.archive_dir) if hasattr(args, "archive_dir") and args.archive_dir else None
    manifests = list_archives(archive_dir=archive_dir)
    if not manifests:
        print("No archives found.")
        return 0
    for m in manifests:
        print(
            f"  {m.created_at} | {m.kind} | commit={m.source_commit[:12] if m.source_commit else 'N/A':12s} | {m.file_count} files | {m.compressed_size} bytes"
        )
    return 0


def cmd_archive_verify(args) -> int:
    from knowledge.engine.archiver import verify_archive

    archive_dir = Path(args.archive_dir) if hasattr(args, "archive_dir") and args.archive_dir else None
    ok = verify_archive(args.manifest, archive_dir=archive_dir)
    if ok:
        print("Archive verified: SHA-256 OK")
        return 0
    print("Archive verification FAILED", file=sys.stderr)
    return 1


def cmd_archive_restore(args) -> int:
    from knowledge.engine.archiver import restore_source

    db_path = _resolve_db_path(args)
    dest = Path(args.dest) if args.dest else None
    archive_dir = Path(args.archive_dir) if hasattr(args, "archive_dir") and args.archive_dir else None
    commit = restore_source(args.manifest, dest_dir=dest, db_path=db_path, archive_dir=archive_dir)
    print(f"Source restored: commit={commit[:12]}")
    return 0
