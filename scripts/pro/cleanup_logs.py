#!/usr/bin/env python3
"""Elimina logs de motor/observability/logs/ mayores a 30 dias."""
import os
import time
from pathlib import Path

LOG_DIR = Path.home() / "URA" / "ura_ia_1972" / "motor" / "observability" / "logs"
DAYS = 30
CUTOFF = time.time() - (DAYS * 86400)

def cleanup():
    if not LOG_DIR.exists():
        print(f"Log dir no existe: {LOG_DIR}")
        return 0
    removed = 0
    for f in LOG_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < CUTOFF:
            f.unlink()
            removed += 1
    print(f"Eliminados {removed} logs > {DAYS} dias")
    return removed

if __name__ == "__main__":
    cleanup()
