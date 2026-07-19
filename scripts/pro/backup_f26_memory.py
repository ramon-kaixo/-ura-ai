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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def cmd_backup(path: str) -> None:
    from motor.memory import Memory, save_snapshot

    memory = Memory()
    path = save_snapshot(memory, path)
    print(f"Backup saved: {path}")
    print(f"Size: {os.path.getsize(path)} bytes")


def cmd_restore(path: str) -> None:
    from motor.memory import load_snapshot

    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)

    memory = load_snapshot(path)
    print(f"Restored from: {path}")
    print(f"Entries: {len(memory._entries) if hasattr(memory, '_entries') else 'N/A'}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
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
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
