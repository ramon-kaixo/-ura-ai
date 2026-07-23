#!/usr/bin/env python3
"""Ejecuta VACUUM en las bases SQLite documentadas."""

import sqlite3
from pathlib import Path

BASES = [
    "knowledge/knowledge.db",
]


def vacuum():
    for db_path in BASES:
        p = Path(db_path)
        if not p.exists():
            print(f"Skip: {db_path} no existe")
            continue
        try:
            conn = sqlite3.connect(str(p))
            conn.execute("VACUUM")
            conn.close()
            print(f"VACUUM OK: {db_path}")
        except Exception as e:
            print(f"VACUUM FAIL {db_path}: {e}")


if __name__ == "__main__":
    vacuum()
