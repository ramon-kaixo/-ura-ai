#!/usr/bin/env python3
"""Backup del asistente conversacional — DBs y configuración."""
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKUP_DIR = Path("/home/ramon/URA/backups/assistant")
DATA_DIR = Path(os.environ.get("URA_DATA_DIR", str(Path.home() / ".ura")))


def backup() -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"assistant_{ts}"
    dest.mkdir(parents=True, exist_ok=True)

    if DATA_DIR.exists():
        for f in DATA_DIR.glob("*.db"):
            shutil.copy2(f, dest / f.name)
            print(f"  Backup: {f.name}")

    log = dest / "backup_log.txt"
    log.write_text(f"Backup completado: {ts}\nOrigen: {DATA_DIR}\n")
    print(f"Backup guardado en: {dest}")
    return str(dest)


def restore(backup_path: str) -> None:
    src = Path(backup_path)
    if not src.exists() or not src.is_dir():
        print(f"Error: {backup_path} no existe o no es un directorio")
        sys.exit(1)

    for f in src.glob("*.db"):
        shutil.copy2(f, DATA_DIR / f.name)
        print(f"  Restaurado: {f.name}")
    print(f"Restauración completada desde: {backup_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore(sys.argv[2])
    else:
        backup()
