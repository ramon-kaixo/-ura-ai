#!/usr/bin/env python3
"""F29 B4 — Backup + Restore para F26 Memory.

Uso:
  python3 scripts/pro/backup_f26_memory.py backup [--path /tmp/memory_backup.json]
  python3 scripts/pro/backup_f26_memory.py restore [--path /tmp/memory_backup.json]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(Path(__file__).parent, "..", ".."))  # noqa: PTH118


def cmd_backup(path: str) -> None:
    from motor.memory import Memory, save_snapshot

    memory = Memory()
    path = save_snapshot(memory, path)


def cmd_restore(path: str) -> None:
    from motor.memory import load_snapshot

    if not Path(path).exists():
        sys.exit(1)

    load_snapshot(path)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    command = sys.argv[1]
    path = (
        sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--path" else f"/tmp/memory_backup_{int(time.time())}.json"
    )

    if command == "backup":
        cmd_backup(path)
    elif command == "restore":
        cmd_restore(path)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
