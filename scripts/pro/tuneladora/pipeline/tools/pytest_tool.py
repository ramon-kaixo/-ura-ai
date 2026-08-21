from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.pipeline.sandbox import preexec_fn
from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase, ToolResult


class PytestTool(ToolBase):
    name = "pytest"

    def __init__(
        self,
        ura_root: Path,
        timeout: int = 300,
        use_sandbox: bool = False,
        disable_socket: bool = False,
        test_target: str = "tests/",
    ) -> None:
        self._root = ura_root
        self._timeout = timeout
        self._use_sandbox = use_sandbox
        self._disable_socket = disable_socket
        self._test_target = test_target

    def is_available(self) -> bool:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=str(self._root),
            )
            return r.returncode == 0
        except Exception:
            return False

    def _run_pytest(self, target: str, extra_args: list[str] | None = None) -> ToolResult:
        t0 = time.monotonic()
        args = [sys.executable, "-m", "pytest", target, "--no-cov", "--tb=no"]
        if extra_args:
            args.extend(extra_args)
        if self._disable_socket:
            args.append("--disable-socket")
        kwargs: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "timeout": self._timeout,
            "cwd": str(self._root),
        }
        if self._use_sandbox:
            kwargs["preexec_fn"] = preexec_fn
        try:
            r = subprocess.run(args, check=False, **kwargs)
            elapsed = time.monotonic() - t0
            stdout = r.stdout
            passed = self._parse_count(stdout, "passed")
            failed = self._parse_count(stdout, "failed")
            errors = self._parse_count(stdout, "error")
            if r.returncode == 0:
                return ToolResult(name="pytest", status=Status.OK, seconds=elapsed, summary=f"{passed} passed")
            return ToolResult(
                name="pytest",
                status=Status.FAIL,
                seconds=elapsed,
                summary=f"{failed} failed, {errors} errors",
                detail=stdout[:2000],
            )
        except subprocess.TimeoutExpired:
            return ToolResult(name="pytest", status=Status.FAIL, seconds=self._timeout, summary="Timeout")
        except Exception as e:
            return ToolResult(name="pytest", status=Status.FAIL, summary=str(e))

    def _parse_count(self, text: str, keyword: str) -> int:
        import re

        match = re.search(rf"(\d+)\s+{keyword}s?(?:\s|$|,)", text)
        return int(match.group(1)) if match else 0

    def run_check(self, files: list[str] | None = None) -> ToolResult:
        target = self._test_target if not files else " ".join(files)
        return self._run_pytest(target)

    def run_fix(self, files: list[str] | None = None) -> ToolResult:
        return self.run_check(files)

    def severity(self) -> str:
        return "required"
