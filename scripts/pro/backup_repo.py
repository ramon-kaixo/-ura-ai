#!/usr/bin/env python3
"""Backup semanal del repo completo (tar.gz) en .nervioso/backups/"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path("/home/ramon/URA/ura_ia_1972")
BACKUP_DIR = Path.home() / ".nervioso" / "backups"
KEEP_COPIES = 4

def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    dest = BACKUP_DIR / f"repo_{ts}.tar.gz"

    print(f"Creando backup: {dest}")

    subprocess.run(
        ["tar", "-czf", str(dest),
         "--exclude=__pycache__", "--exclude=.git", "--exclude=.nervioso",
         "--exclude=node_modules", "--exclude=.venv",
         "-C", str(REPO.parent), REPO.name],
        check=True, timeout=300,
    )

    size_mb = round(dest.stat().st_size / 1e6, 1)
    print(f"Backup: {size_mb} MB → {dest}")

    # Clean old
    files = sorted(BACKUP_DIR.glob("repo_*.tar.gz"))
    for f in files[:-KEEP_COPIES]:
        f.unlink()
        print(f"Deleted old: {f.name}")

    print("Backup repo completo ✓")
    return 0

if __name__ == "__main__":
    sys.exit(main())
