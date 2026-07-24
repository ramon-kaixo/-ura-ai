from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase, ToolResult


class MypyTool(ToolBase):
    name = "mypy"

    def __init__(self, ura_root: Path, timeout: int = 120) -> None:
        self._root = ura_root
        self._timeout = timeout

    def is_available(self) -> bool:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "mypy", "--version"],
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
        targets = files or ["."]
        try:
            r = subprocess.run(
                [sys.executable, "-m", "mypy", *targets],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                cwd=str(self._root),
            )
            elapsed = time.monotonic() - t0
            if r.returncode == 0:
                return ToolResult(name="mypy", status=Status.OK, seconds=elapsed, summary="No issues")
            err_lines = [l for l in r.stdout.split("\n") if l.strip() and " error" in l.lower()]
            return ToolResult(
                name="mypy",
                status=Status.WARN,
                seconds=elapsed,
                summary=f"{len(err_lines)} errors",
                detail=r.stdout[:2000],
            )
        except subprocess.TimeoutExpired:
            return ToolResult(name="mypy", status=Status.WARN, seconds=self._timeout, summary="Timeout")
        except Exception as e:
            return ToolResult(name="mypy", status=Status.WARN, summary=str(e))

    def run_fix(self, files: list[str] | None = None) -> ToolResult:
        return self.run_check(files)

    def severity(self) -> str:
        return "optional"
