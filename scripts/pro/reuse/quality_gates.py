"""Quality Gates — disparadores para ejecutar las tuneladoras.

No se ejecutan solo por tiempo, sino por evolución del proyecto:
  - Cada N commits
  - Cada M líneas modificadas
  - Antes de crear un tag
  - Antes de fusionar a main
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


class QualityGates:
    """Evalúa si se debe ejecutar el pipeline completo según la actividad."""

    def __init__(self, repo_root: str | Path = "") -> None:
        self._root = Path(repo_root or Path.cwd())

    def commit_count_since_last_tag(self) -> int:
        """Cuenta commits desde el último tag."""
        try:
            last_tag = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._root),
                check=False,
            ).stdout.strip()
            if not last_tag:
                return 0
            count = subprocess.run(
                ["git", "rev-list", f"{last_tag}..HEAD", "--count"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._root),
                check=False,
            ).stdout.strip()
            return int(count) if count else 0
        except Exception:
            return 0

    def lines_changed_since_last_tag(self) -> int:
        """Cuenta líneas modificadas desde el último tag."""
        try:
            last_tag = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._root),
                check=False,
            ).stdout.strip()
            if not last_tag:
                return 0
            diff = subprocess.run(
                ["git", "diff", f"{last_tag}..HEAD", "--stat"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._root),
                check=False,
            ).stdout.strip()
            nums = re.findall(r"(\d+) insertions?\(\+\)", diff)
            return sum(int(n) for n in nums) if nums else 0
        except Exception:
            return 0

    def should_run_maintenance(self, commit_threshold: int = 10, lines_threshold: int = 2000) -> dict[str, Any]:
        """Determina si el pipeline debe ejecutarse según la actividad."""
        commits = self.commit_count_since_last_tag()
        lines = self.lines_changed_since_last_tag()
        reasons = []

        if commits >= commit_threshold:
            reasons.append(f"{commits} commits desde último tag (umbral: {commit_threshold})")
        if lines >= lines_threshold:
            reasons.append(f"{lines} líneas modificadas (umbral: {lines_threshold})")

        return {
            "should_run": len(reasons) > 0,
            "commits": commits,
            "lines_changed": lines,
            "reasons": reasons,
        }
