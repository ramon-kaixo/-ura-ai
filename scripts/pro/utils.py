"""Utilidades compartidas para scripts del pipeline.

Uso:
    from scripts.pro.utils import log, scan_project
"""  # noqa: EXE002, INP001

import os
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
EXCLUDE_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    "backups",
    "site-packages",
    "scripts_eliminados",
    ".sandbox_packages",
    ".nervioso",
    "audit_reports",
}


def log(msg: str) -> None:
    """Volcado a terminal con timestamp."""


def scan_project(suffix: str = ".py") -> list[Path]:
    """Devuelve todos los archivos del proyecto excluyendo directorios del sistema."""
    files = []
    for f in sorted(URA_ROOT.rglob(f"*{suffix}")):
        parts = f.relative_to(URA_ROOT).parts
        if any(excl in parts for excl in EXCLUDE_DIRS):
            continue
        files.append(f)
    return files
