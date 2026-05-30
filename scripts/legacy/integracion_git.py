#!/usr/bin/env python3
"""Integración Git Completa URA"""

import json
import subprocess
from pathlib import Path

CODE_DIR = Path(__file__).parent.parent / "core"
DB_PATH = Path(__file__).parent.parent / "board.db"


class IntegracionGit:
    def __init__(self):
        self.code_dir = CODE_DIR
        self.db_path = DB_PATH

    def crear_commit_automatico(self, archivo: str, mensaje: str, metadata: dict = None) -> bool:
        try:
            subprocess.run(
                ["git", "add", str(archivo)], cwd=self.code_dir, check=True, capture_output=True
            )
            commit_msg = mensaje + (f"\n\nMetadata: {json.dumps(metadata)}" if metadata else "")
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.code_dir,
                check=True,
                capture_output=True,
            )
            return True
        except:
            return False

    def obtener_estado_git(self) -> dict:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.code_dir,
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.code_dir, capture_output=True, text=True
            )
            modified = len([l for l in result.stdout.split("\n") if l])
            return {"branch": branch, "modified": modified}
        except:
            return {"error": "Git no disponible"}


if __name__ == "__main__":
    git = IntegracionGit()
    estado = git.obtener_estado_git()
    print(f"Estado Git: {estado}")
