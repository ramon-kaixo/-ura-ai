#!/usr/bin/env python3
"""Monitoriza progreso de errores F821 (undefined name) via ruff.

Uso:
  python3 f821_watch.py snapshot --label "antes-refactor"
  python3 f821_watch.py compare --target antes-refactor
  python3 f821_watch.py report
"""

PLUGIN = {
    "name": "f821_watch",
    "phase": "post",
    "timeout": 30,
    "blocking": False,
    "needs_file": False,
}

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SNAPSHOT_DIR = Path(os.environ.get("F821_SNAPSHOT_DIR", Path.home() / ".ura" / "f821_snapshots"))
URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))


def find_ruff():
    for candidate in (
        shutil.which("ruff"),
        Path(sys.executable).with_name("ruff"),
        Path.home() / ".local" / "bin" / "ruff",
        Path.home() / "URA" / "ura_ia_1972" / ".venv" / "bin" / "ruff",
    ):
        if candidate and Path(str(candidate)).exists():
            return str(candidate)
    return "ruff"


def run_ruff() -> list[dict]:
    ruff_bin = find_ruff()
    result = subprocess.run(
        [ruff_bin, "check", "--select", "F821", "--output-format", "json", str(URA_ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(URA_ROOT),
    )
    if result.returncode not in (0, 1):
        return []
    try:
        return json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return []


def snapshot(label: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    violations = run_ruff()

    counts: dict[str, int] = {}
    files: set[str] = set()
    for v in violations:
        fname = v.get("filename", "?")
        rel = os.path.relpath(fname, str(URA_ROOT))
        files.add(rel)
        counts[rel] = counts.get(rel, 0) + 1

    data = {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_violations": len(violations),
        "total_files": len(files),
        "file_counts": counts,
    }

    path = SNAPSHOT_DIR / f"{label}.json"
    path.write_text(json.dumps(data, indent=2))


def compare(target_label: str) -> None:
    target_path = SNAPSHOT_DIR / f"{target_label}.json"
    if not target_path.exists():
        sys.exit(f"Snapshot '{target_label}' no encontrado en {target_path}")

    target = json.loads(target_path.read_text())
    current = run_ruff()

    current_files: set[str] = set()
    current_counts: dict[str, int] = {}
    for v in current:
        rel = os.path.relpath(v.get("filename", "?"), str(URA_ROOT))
        current_files.add(rel)
        current_counts[rel] = current_counts.get(rel, 0) + 1

    prev_total = target["total_violations"]
    target["total_files"]
    curr_total = len(current)
    len(current_files)

    delta = prev_total - curr_total
    (delta / prev_total * 100) if prev_total > 0 else 0


    resolved = set(target.get("file_counts", {}).keys()) - current_files
    if resolved:
        for _f in sorted(resolved)[:10]:
            pass
        if len(resolved) > 10:
            pass

    new_files = current_files - set(target.get("file_counts", {}).keys())
    if new_files:
        for _f in sorted(new_files)[:10]:
            pass
        if len(new_files) > 10:
            pass


def report() -> None:
    violations = run_ruff()
    files: dict[str, int] = {}
    for v in violations:
        rel = os.path.relpath(v.get("filename", "?"), str(URA_ROOT))
        files[rel] = files.get(rel, 0) + 1


    by_count = sorted(files.items(), key=lambda x: -x[1])
    for _fname, _cnt in by_count[:20]:
        pass
    if len(by_count) > 20:
        pass


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    parser = argparse.ArgumentParser(description="F821 (undefined name) progress tracker")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("snapshot").add_argument("--label", required=True)
    comp = sub.add_parser("compare")
    comp.add_argument("--target", required=True)
    sub.add_parser("report")

    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "snapshot":
        snapshot(args.label)
    elif args.command == "compare":
        compare(args.target)
    elif args.command == "report":
        report()


if __name__ == "__main__":
    main()
