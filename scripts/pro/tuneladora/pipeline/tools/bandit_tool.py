from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase, ToolResult


class BanditTool(ToolBase):
    name = "bandit"

    def __init__(self, ura_root: Path, timeout: int = 120) -> None:
        self._root = ura_root
        self._timeout = timeout

    def is_available(self) -> bool:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "bandit", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=str(self._root),
            )
            return r.returncode == 0
        except Exception:
            return False

    def run_check(self, files: list[str] | None = None) -> ToolResult:
        t0 = time.monotonic()
        targets = files or ["-r", "."]
        try:
            r = subprocess.run(
                [sys.executable, "-m", "bandit", *targets],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                cwd=str(self._root),
            )
            elapsed = time.monotonic() - t0
            stdout = r.stdout
            high = stdout.count("Severity: High")
            medium = stdout.count("Severity: Medium")
            if high > 0 or medium > 0:
                return ToolResult(
                    name="bandit",
                    status=Status.FAIL,
                    seconds=elapsed,
                    summary=f"{high} high, {medium} medium",
                    detail=stdout[:2000],
                )
            return ToolResult(name="bandit", status=Status.OK, seconds=elapsed, summary="No issues")
        except subprocess.TimeoutExpired:
            return ToolResult(name="bandit", status=Status.FAIL, seconds=self._timeout, summary="Timeout")
        except Exception as e:
            return ToolResult(name="bandit", status=Status.FAIL, summary=str(e))

    def run_fix(self, files: list[str] | None = None) -> ToolResult:
        return self.run_check(files)

    def severity(self) -> str:
        return "required"
