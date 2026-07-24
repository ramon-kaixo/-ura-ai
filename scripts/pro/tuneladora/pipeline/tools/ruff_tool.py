from __future__ import annotations

import subprocess
import time
from pathlib import Path

from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase, ToolResult


class RuffTool(ToolBase):
    name = "ruff"

    def __init__(self, ruff_path: str, ura_root: Path, timeout: int = 300) -> None:
        self._ruff = ruff_path
        self._root = ura_root
        self._timeout = timeout

    def is_available(self) -> bool:
        return Path(self._ruff).exists()

    def run_check(self, files: list[str] | None = None) -> ToolResult:
        t0 = time.monotonic()
        args = [self._ruff, "check"]
        if files:
            args.extend(files)
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=self._timeout, check=False, cwd=str(self._root)
            )
            elapsed = time.monotonic() - t0
            if r.returncode == 0:
                return ToolResult(name="ruff", status=Status.OK, seconds=elapsed, summary="ruff check passed")
            errors = [
                l
                for l in r.stdout.split("\n")
                if l.strip() and not l.startswith("All checks") and not l.startswith("Found")
            ]
            return ToolResult(
                name="ruff",
                status=Status.FAIL,
                seconds=elapsed,
                summary=f"{len(errors)} errors",
                detail=r.stdout[:2000],
                fixable=True,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(name="ruff", status=Status.FAIL, seconds=self._timeout, summary="Timeout")
        except Exception as e:
            return ToolResult(name="ruff", status=Status.FAIL, summary=str(e))

    def run_fix(self, files: list[str] | None = None) -> ToolResult:
        t0 = time.monotonic()
        args = [self._ruff, "check", "--fix"]
        if files:
            args.extend(files)
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=self._timeout, check=False, cwd=str(self._root)
            )
            elapsed = time.monotonic() - t0
            ok = r.returncode == 0
            return ToolResult(
                name="ruff",
                status=Status.OK if ok else Status.FAIL,
                seconds=elapsed,
                summary="ruff fix applied" if ok else "ruff fix incomplete",
                fixable=True,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(name="ruff", status=Status.FAIL, seconds=self._timeout, summary="Timeout")
        except Exception as e:
            return ToolResult(name="ruff", status=Status.FAIL, summary=str(e))

    def severity(self) -> str:
        return "required"
