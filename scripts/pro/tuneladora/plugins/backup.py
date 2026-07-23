"""BackupPlugin — backup y rollback del sistema."""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class BackupPlugin:
    """Backup de codigo, base de datos y rollback."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine
        self.repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.backup_dir = Path.home() / ".nervioso" / "backups"

    def backup_code(self, label: str = "auto") -> dict[str, Any]:
        """Crea un tag de git antes de cambios. Retorna hash del commit."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"backup_{label}_{ts}"
        try:
            # Stash cambios no commiteados
            stash = subprocess.run(
                ["git", "stash", "push", "-m", f"backup_{ts}"],
                capture_output=True, text=True, timeout=30, cwd=str(self.repo_root),
            )
            stashed = stash.returncode == 0
            # Tag
            tag_result = subprocess.run(
                ["git", "tag", tag],
                capture_output=True, text=True, timeout=10, cwd=str(self.repo_root),
            )
            tagged = tag_result.returncode == 0
            self.engine.log.info("Backup code: tag=%s stashed=%s", tag, stashed)
            return {"tag": tag, "stashed": stashed, "ok": tagged}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def backup_database(self) -> dict[str, Any]:
        """Copia knowledge/db/*.db a backups/."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        copied = 0
        for db in Path("knowledge").rglob("*.db"):
            try:
                dest = self.backup_dir / f"{db.stem}_{ts}.db"
                shutil.copy2(str(db), str(dest))
                copied += 1
                self.engine.log.info("Backup DB: %s -> %s", db.name, dest.name)
            except Exception as e:
                self.engine.log.warning("Backup DB fallo %s: %s", db.name, e)
        return {"copied": copied, "backup_dir": str(self.backup_dir)}

    def rollback(self) -> dict[str, Any]:
        """Deshace cambios locales. git stash pop o restore."""
        try:
            # Intentar stash pop primero
            r = subprocess.run(
                ["git", "stash", "pop"],
                capture_output=True, text=True, timeout=30, cwd=str(self.repo_root),
            )
            if r.returncode == 0:
                self.engine.log.info("Rollback: stash pop OK")
                return {"method": "stash_pop", "ok": True}
            # Si no hay stash, hacer checkout
            r2 = subprocess.run(
                ["git", "checkout", "."],
                capture_output=True, text=True, timeout=30, cwd=str(self.repo_root),
            )
            self.engine.log.info("Rollback: checkout OK")
            return {"method": "checkout", "ok": r2.returncode == 0}
        except Exception as e:
            return {"error": str(e), "ok": False}
