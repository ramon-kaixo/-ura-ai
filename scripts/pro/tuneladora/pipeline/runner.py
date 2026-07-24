"""PipelineRunner — orquesta fases del pipeline de validación."""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.llm_fallback import LLMFallback
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue
from scripts.pro.tuneladora.pipeline.snapshot_manager import SnapshotManager
from scripts.pro.tuneladora.pipeline.tools.bandit_tool import BanditTool
from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase
from scripts.pro.tuneladora.pipeline.tools.mypy_tool import MypyTool
from scripts.pro.tuneladora.pipeline.tools.pytest_tool import PytestTool
from scripts.pro.tuneladora.pipeline.tools.ruff_tool import RuffTool

log = logging.getLogger("tuneladora.runner")


def _free_disk_gb(path: Path) -> float | None:
    for fn in (lambda p: os.statvfs(p), lambda p: shutil.disk_usage(p)):
        try:
            st = fn(str(path))
            if hasattr(st, "f_frsize"):
                return st.f_frsize * st.f_bavail / (1024**3)
            return st.free / (1024**3)
        except (OSError, AttributeError):
            continue
    return None


class PhaseResult:
    def __init__(self, name: str, status: Status, results: list[Any] | None = None) -> None:
        self.name = name
        self.status = status
        self.results = results or []


def _discover_focused_tests(changed_files: list[str]) -> list[str]:
    focused: list[str] = []
    for f in changed_files:
        if not f.endswith(".py"):
            continue
        stem = Path(f).stem
        test_file = f"tests/test_{stem}.py"
        if Path(test_file).exists():
            focused.append(test_file)
    return focused


class PipelineRunner:
    def __init__(self, cfg: Configuration, mode: str = "check", files: list[str] | None = None) -> None:
        self.cfg = cfg
        self.mode = mode
        self.files = files or []
        self.pending_queue = PendingQueue(cfg.knowledge_db)
        self.snapshot_manager = SnapshotManager(cfg.tuneladora_dir, log.info)
        self.llm_fallback = LLMFallback(cfg, self.pending_queue)
        self._last_snapshot: Path | None = None
        self._build_tools()

    def _build_tools(self) -> None:
        self.tools: dict[str, ToolBase] = {
            "ruff": RuffTool(self.cfg.ruff, self.cfg.ura_root, self.cfg.timeout_ruff),
            "pytest": PytestTool(
                self.cfg.ura_root, timeout=self.cfg.timeout_worker, use_sandbox=self.mode == "gate",
                disable_socket=self.mode == "gate", test_target=self.cfg.test_target,
            ),
            "bandit": BanditTool(self.cfg.ura_root),
            "mypy": MypyTool(self.cfg.ura_root),
        }

    # ── Pre-flight ───────────────────────────────────────────

    def preflight(self) -> list[PhaseResult]:
        rules = {
            "ruff": {"check": "FAIL", "fix": "FAIL", "gate": "FAIL"},
            "pytest": {"check": "WARN", "fix": "WARN", "gate": "FAIL"},
            "bandit": {"check": "SKIP", "fix": "SKIP", "gate": "FAIL"},
            "mypy": {"check": "SKIP", "fix": "SKIP", "gate": "WARN"},
        }
        results: list[PhaseResult] = []
        all_ok = True
        for name, tool in self.tools.items():
            available = tool.is_available()
            expected = rules.get(name, {}).get(self.mode, "WARN")
            if not available and expected == "FAIL":
                log.error("[PRE-FLIGHT] %s FAIL — no disponible (requerido en modo %s)", name, self.mode)
                all_ok = False
            elif not available and expected == "WARN":
                log.warning("[PRE-FLIGHT] %s no disponible (opcional en modo %s)", name, self.mode)
            elif available:
                log.info("[PRE-FLIGHT] %s ✓", name)
        if not all_ok:
            results.append(PhaseResult("preflight", Status.FAIL))
        else:
            results.append(PhaseResult("preflight", Status.OK))
        return results

    # ── Fase 0: Snapshot ─────────────────────────────────────

    def phase_snapshot(self) -> list[PhaseResult]:
        label = f"ciclo_{self.mode}"
        files_to_snapshot = [Path(f) for f in self.files] if self.files else []
        if not files_to_snapshot:
            try:
                r = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True, text=True, timeout=10, check=False, cwd=str(self.cfg.ura_root),
                )
                if r.returncode == 0 and r.stdout:
                    files_to_snapshot = [Path(f.strip()) for f in r.stdout.split("\n") if f.strip().endswith(".py")]
            except Exception:
                log.warning("Could not determine changed files for snapshot")
        if not files_to_snapshot:
            log.warning("No files to snapshot")
            return [PhaseResult("snapshot", Status.SKIP)]
        snap = self.snapshot_manager.take(label, files_to_snapshot, model=self.cfg.llm_fallback_model)
        if snap:
            self._last_snapshot = snap
            return [PhaseResult("snapshot", Status.OK)]
        return [PhaseResult("snapshot", Status.WARN)]

    # ── Fase 1: Estática (py_compile + tools) ────────────────

    def phase_static(self) -> list[PhaseResult]:
        results: list[PhaseResult] = []

        # py_compile
        pr = self._run_py_compile()
        results.append(PhaseResult("py_compile", pr.status, [pr]))
        if pr.status == Status.FAIL:
            return results

        for name in ("ruff", "bandit", "mypy"):
            tool = self.tools[name]
            if not tool.is_available():
                results.append(PhaseResult(name, Status.SKIP))
                continue
            result = self._run_tool_with_retry(tool, self.files)
            results.append(PhaseResult(name, result.status, [result]))
            if result.status == Status.FAIL and tool.severity() == "required" and self.mode in ("fix", "gate"):
                archivo_ref = ", ".join(self.files) if self.files else "."
                sugerencia = self.llm_fallback.analyze(result.detail, archivo_ref, name)
                self.pending_queue.add(
                    archivo=archivo_ref,
                    herramienta=name,
                    severidad="high" if result.status == Status.FAIL else "medium",
                    error_raw=result.detail,
                    bloque="static",
                    sugerencia_llm=sugerencia or "",
                    modelo_generador=self.cfg.llm_fallback_model,
                )

        return results

    def _run_py_compile(self) -> Any:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        t0 = time.monotonic()
        try:
            targets = self.files or ["scripts/pro/tuneladora/"]
            for t in targets:
                r = subprocess.run(
                    [sys.executable, "-m", "py_compile", t], capture_output=True, text=True, timeout=self.cfg.timeout_script, check=False
                )
                if r.returncode != 0:
                    return ToolResult(
                        name="py_compile",
                        status=Status.FAIL,
                        seconds=time.monotonic() - t0,
                        summary=f"Syntax error in {t}",
                        detail=r.stderr[:1000],
                    )
            return ToolResult(
                name="py_compile", status=Status.OK, seconds=time.monotonic() - t0, summary="All syntax OK"
            )
        except Exception as e:
            return ToolResult(name="py_compile", status=Status.FAIL, summary=str(e))

    # ── Fase 2: Dinámica (pytest) ────────────────────────────

    def phase_dynamic(self) -> list[PhaseResult]:
        results: list[PhaseResult] = []
        tool = self.tools["pytest"]
        if not tool.is_available():
            return [PhaseResult("pytest", Status.SKIP)]

        # focused tests
        focused = _discover_focused_tests(self.files)
        if focused:
            log.info("Focused tests: %s", focused)
            r = tool.run_check(focused)
            results.append(PhaseResult("pytest_focused", r.status, [r]))
            if r.status == Status.FAIL:
                archivo_ref = ", ".join(focused)
                sugerencia = self.llm_fallback.analyze(r.detail, archivo_ref, "pytest")
                self.pending_queue.add(
                    archivo=archivo_ref,
                    herramienta="pytest",
                    severidad="high",
                    error_raw=r.detail,
                    bloque="dynamic_focused",
                    sugerencia_llm=sugerencia or "",
                    modelo_generador=self.cfg.llm_fallback_model,
                )
                return results
            log.info("Focused tests passed — skipping full suite")
            return results

        # full suite
        r = tool.run_check()
        results.append(PhaseResult("pytest_full", r.status, [r]))
        if r.status == Status.FAIL:
            sugerencia = self.llm_fallback.analyze(r.detail, ".", "pytest")
            self.pending_queue.add(
                archivo=".", herramienta="pytest", severidad="high", error_raw=r.detail, bloque="dynamic_full",
                sugerencia_llm=sugerencia or "",
                modelo_generador=self.cfg.llm_fallback_model,
            )
        return results

    # ── Fase 3: Integridad ───────────────────────────────────

    def phase_integrity(self) -> list[PhaseResult]:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        results: list[PhaseResult] = []
        changed_files: list[str] = []
        changed_lines = 0

        # blast radius via git diff --name-only
        try:
            r = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_script,
                check=False,
                cwd=str(self.cfg.ura_root),
            )
            if r.returncode == 0 and r.stdout:
                changed_files = [f for f in r.stdout.strip().split("\n") if f]
        except Exception:
            log.warning("Failed to get git diff stats")

        # line count via git diff --numstat
        try:
            r = subprocess.run(
                ["git", "diff", "--numstat"],
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_script,
                check=False,
                cwd=str(self.cfg.ura_root),
            )
            if r.returncode == 0 and r.stdout:
                for line in r.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        with contextlib.suppress(ValueError):
                            changed_lines += int(parts[0]) + int(parts[1])
        except Exception:
            log.warning("Failed to get git diff numstat")

        max_files = 50
        max_lines = 5000
        if len(changed_files) > max_files:
            results.append(
                PhaseResult(
                    "blast_radius",
                    Status.FAIL,
                    [
                        ToolResult(
                            name="blast_radius",
                            status=Status.FAIL,
                            summary=f"{len(changed_files)} files exceeds {max_files}",
                        )
                    ],
                )
            )
        elif changed_lines > max_lines:
            results.append(
                PhaseResult(
                    "blast_radius",
                    Status.FAIL,
                    [
                        ToolResult(
                            name="blast_radius",
                            status=Status.FAIL,
                            summary=f"{changed_lines} lines exceeds {max_lines}",
                        )
                    ],
                )
            )
        else:
            results.append(PhaseResult("blast_radius", Status.OK))

        # disk
        try:
            free_gb = _free_disk_gb(self.cfg.ura_root)
            if free_gb is None:
                results.append(PhaseResult("disk", Status.WARN))
            elif free_gb < 1:
                results.append(
                    PhaseResult(
                        "disk",
                        Status.FAIL,
                        [ToolResult(name="disk", status=Status.FAIL, summary=f"Only {free_gb:.1f} GB free")],
                    )
                )
            else:
                results.append(
                    PhaseResult(
                        "disk", Status.OK, [ToolResult(name="disk", status=Status.OK, summary=f"{free_gb:.1f} GB free")]
                    )
                )
        except Exception:
            results.append(PhaseResult("disk", Status.WARN))

        return results

    # ── Fase 4: Veredicto ────────────────────────────────────

    def phase_verdict(self, phase_results: list[list[PhaseResult]]) -> tuple[Status, str]:
        any_fail = False
        n_warn = 0
        for phase in phase_results:
            for pr in phase:
                if pr.status == Status.FAIL:
                    any_fail = True
                elif pr.status == Status.WARN:
                    n_warn += 1
        if any_fail:
            return Status.FAIL, "Pipeline FAILED — rollback recommended"
        if n_warn > 0:
            return Status.WARN, f"Pipeline passed with {n_warn} warnings"
        return Status.OK, "Pipeline passed all checks"

    # ── Retry helper ─────────────────────────────────────────

    def _run_tool_with_retry(self, tool: ToolBase, files: list[str] | None) -> Any:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        if self.mode in ("fix", "gate") and tool.name != "mypy":
            result = tool.run_fix(files)
            if result.status == Status.FAIL:
                result = tool.run_check(files)
                if (
                    result.status == Status.FAIL
                    and self.cfg.unsafe_fixes
                    and tool.name == "ruff"
                    and hasattr(tool, "_ruff")
                ):
                    t0 = time.monotonic()
                    args = [tool._ruff, "check", "--fix", "--unsafe-fixes"]
                    if files:
                        args.extend(files)
                    r = subprocess.run(
                        args, capture_output=True, text=True, timeout=tool._timeout, check=False, cwd=str(tool._root)
                    )
                    result = ToolResult(
                        name=tool.name,
                        status=Status.OK if r.returncode == 0 else Status.FAIL,
                        seconds=time.monotonic() - t0,
                        detail=r.stdout[:2000],
                    )
            if result.status == Status.FAIL:
                archivo_ref = ", ".join(files) if files else "."
                self.llm_fallback.analyze(error_raw=result.detail, archivo=archivo_ref, tool_name=tool.name)
            return result
        result = tool.run_check(files)
        if result.status == Status.FAIL:
            archivo_ref = ", ".join(files) if files else "."
            self.llm_fallback.analyze(error_raw=result.detail, archivo=archivo_ref, tool_name=tool.name)
        return result

    # ── Run all ──────────────────────────────────────────────

    def run(self) -> Status:
        t_start = time.monotonic()
        all_phase_results: list[list[PhaseResult]] = []

        # Pre-flight
        pre = self.preflight()
        all_phase_results.append(pre)
        if any(pr.status == Status.FAIL for pr in pre):
            log.error("Pre-flight failed — aborting")
            return Status.FAIL

        # Phase 0: Snapshot
        p0 = self.phase_snapshot()
        all_phase_results.append(p0)

        # Phase 1: Static
        p1 = self.phase_static()
        all_phase_results.append(p1)

        # Phase 2: Dynamic
        p2 = self.phase_dynamic()
        all_phase_results.append(p2)

        # Phase 3: Integrity
        p3 = self.phase_integrity()
        all_phase_results.append(p3)

        # Phase 4: Verdict
        verdict, msg = self.phase_verdict(all_phase_results)
        elapsed = time.monotonic() - t_start

        if verdict == Status.FAIL and self._last_snapshot is not None:
            log.warning("Pipeline FAILED — restoring snapshot %s", self._last_snapshot.name)
            self.snapshot_manager.restore(self._last_snapshot)
            msg = "Pipeline FAILED — rollback executed"

        head = ""
        with contextlib.suppress(Exception):
            head = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                cwd=str(self.cfg.ura_root),
            ).stdout.strip()

        self.pending_queue.record_run(
            mode=self.mode,
            verdict=verdict.value,
            seconds=elapsed,
            n_files=len(self.files),
            head=head,
            failures=msg if verdict != Status.OK else "",
        )

        log.info("Pipeline %s: %s (%.1fs)", self.mode, msg, elapsed)
        return verdict
