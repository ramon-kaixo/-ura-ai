"""PipelineRunner — orquesta fases del pipeline de validación."""
from __future__ import annotations

import ast
import compileall
import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts.pro import auditoria_continua as _auditoria_continua
from scripts.pro import change_log as _change_log
from scripts.pro import conciencia as _conciencia
from scripts.pro import plugin_registry as _plugin_registry
from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.memory.episodic import Episode, EpisodicMemory
from scripts.pro.tuneladora.memory.long_term import LongTermMemory, LTMEntry
from scripts.pro.tuneladora.memory.semantic import Concept, Relation, SemanticMemory
from scripts.pro.tuneladora.memory.short_term import ShortTermMemory
from scripts.pro.tuneladora.pipeline.llm_fallback import LLMFallback
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue
from scripts.pro.tuneladora.pipeline.snapshot_manager import SnapshotManager
from scripts.pro.tuneladora.pipeline.sofia import Sofia, SofiaReport
from scripts.pro.tuneladora.pipeline.tools.bandit_tool import BanditTool
from scripts.pro.tuneladora.pipeline.tools.base import Status, ToolBase
from scripts.pro.tuneladora.pipeline.tools.mypy_tool import MypyTool
from scripts.pro.tuneladora.pipeline.tools.pytest_tool import PytestTool
from scripts.pro.tuneladora.pipeline.tools.ruff_tool import RuffTool

log = logging.getLogger("tuneladora.runner")
LOCK_TIMEOUT = 1800


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


def _build_json_report(
    episode_id: str,
    verdict: Status,
    msg: str,
    duration_ms: float,
    mode: str,
    files: list[str],
    telemetry: dict,
    sofia_n_criticos: int,
    sofia_n_advertencias: int,
) -> dict:
    """Reporte estructurado del pipeline (JSON serializable)."""
    coverage = {
        "global": telemetry.get("coverage_global", 0),
        "modulo": telemetry.get("coverage_modulo", {}),
        "tests_total": telemetry.get("tests_total", 0),
        "tests_passed": telemetry.get("tests_passed", 0),
        "tests_failed": telemetry.get("tests_failed", 0),
        "tests_skipped": telemetry.get("tests_skipped", 0),
    }
    return {
        "episode_id": episode_id,
        "pipeline": "tuneladora",
        "mode": mode,
        "verdict": verdict.name,
        "summary": msg,
        "files": files,
        "duration_ms": round(duration_ms, 1),
        "telemetry": telemetry,
        "coverage": coverage,
        "sofia": {
            "criticos": sofia_n_criticos,
            "advertencias": sofia_n_advertencias,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _pid_alive(pid: int) -> bool:
    """True si el proceso con el PID dado sigue vivo (portable)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe pero sin permisos para señalarlo
    except OSError:
        return False


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
        for pattern in (f"tests/test_{stem}.py", f"tests/test_{stem}_*.py"):
            matches = sorted(Path().glob(pattern))
            for m in matches:
                if str(m) not in focused:
                    focused.append(str(m))
    return focused


def _extract_api(tree: ast.AST) -> dict[str, dict[str, str]]:
    api: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            returns = ast.unparse(node.returns) if node.returns else "None"
            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            api[f"{prefix}{node.name}"] = {"args": ", ".join(args), "returns": returns}
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            api[f"class {node.name}"] = {"bases": ", ".join(bases)}
    return api


def _api_diff(old_api: dict, new_api: dict) -> list[str]:
    changes: list[str] = []
    removed = set(old_api) - set(new_api)
    added = set(new_api) - set(old_api)
    common = set(old_api) & set(new_api)
    for k in removed:
        changes.append(f"  - {k} (ELIMINADO)")
    for k in added:
        changes.append(f"  + {k} (NUEVO)")
    for k in common:
        if old_api[k] != new_api[k]:
            changes.append(f"  ~ {k}: {old_api[k]} → {new_api[k]}")
    return changes


class PipelineRunner:
    def __init__(self, cfg: Configuration, mode: str = "check", files: list[str] | None = None) -> None:
        self.cfg = cfg
        self.mode = mode
        self.files = files or []
        self.pending_queue = PendingQueue(cfg.knowledge_db)
        self.snapshot_manager = SnapshotManager(cfg.tuneladora_dir, log.info)
        self.llm_fallback = LLMFallback(cfg, self.pending_queue)
        self.episodic = EpisodicMemory(cfg.episodic_db)
        self.ltm = LongTermMemory(cfg.ltm_db)
        self.semantic = SemanticMemory(cfg.knowledge_db)
        self.cache = ShortTermMemory(max_size=500, default_ttl=60.0)
        self.sofia = Sofia(cfg)
        self._last_snapshot: Path | None = None
        self._sofia_report: SofiaReport = SofiaReport()
        self._telemetry: dict[str, Any] = {"model": cfg.llm_fallback_model}
        self._lock_acquired = False
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

    # ── Lock management ──────────────────────────────────────

    def _acquire_lock(self) -> bool:
        self._lock_acquired = False
        lock_path = self.cfg.tuneladora_dir / "pipeline.lock"
        try:
            self.cfg.tuneladora_dir.mkdir(parents=True, exist_ok=True)
            if lock_path.exists():
                age = time.time() - lock_path.stat().st_mtime
                if age < LOCK_TIMEOUT:
                    # Verificar si el proceso que creó el lock sigue vivo:
                    # un proceso muerto no debe bloquear el pipeline.
                    try:
                        lock_data = json.loads(lock_path.read_text())
                        lock_pid = int(lock_data.get("pid", -1))
                    except (json.JSONDecodeError, OSError, ValueError, TypeError):
                        lock_pid = -1
                    if lock_pid > 0 and not _pid_alive(lock_pid):
                        log.warning("Lock de proceso muerto (pid=%d) — sobrescribiendo", lock_pid)
                        lock_path.unlink(missing_ok=True)
                    else:
                        log.warning("Pipeline lock activo (%ds restantes) — abortando", int(LOCK_TIMEOUT - age))
                        return False
                else:
                    log.warning("Lock stale (%ds) — sobrescribiendo", int(age))
                    lock_path.unlink(missing_ok=True)
            lock_path.write_text(json.dumps({"pid": os.getpid(), "start": time.time(), "mode": self.mode}))
            self._lock_acquired = True
            return True
        except OSError as exc:
            log.warning("Cannot create lock: %s", exc)
            return True  # degrade: proceed without lock

    def _release_lock(self) -> None:
        if not self._lock_acquired:
            return
        lock_path = self.cfg.tuneladora_dir / "pipeline.lock"
        with contextlib.suppress(OSError):
            lock_path.unlink(missing_ok=True)

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
            results.append(PhaseResult("preflight_tools", Status.FAIL))
        else:
            results.append(PhaseResult("preflight_tools", Status.OK))

        # System manifest audit
        preflight_script = self.cfg.ura_root / "scripts/pro/tuneladora/preflight_system.py"
        if preflight_script.exists():
            try:
                r = subprocess.run(
                    [sys.executable, str(preflight_script), "audit"],
                    capture_output=True, text=True, timeout=15,
                    check=False, cwd=str(self.cfg.ura_root),
                )
                if r.returncode == 0:
                    log.info("[PRE-FLIGHT] system manifest ✓")
                    results.append(PhaseResult("preflight_manifest", Status.OK))
                elif self.mode == "gate":
                    log.error("[PRE-FLIGHT] system manifest FAIL — discrepancias detectadas")
                    log.error(r.stdout)
                    results.append(PhaseResult("preflight_manifest", Status.FAIL))
                    all_ok = False
                else:
                    log.warning("[PRE-FLIGHT] system manifest WARN — discrepancias (modo %s)", self.mode)
                    for line in r.stdout.splitlines():
                        log.warning("  %s", line)
                    results.append(PhaseResult("preflight_manifest", Status.WARN))
            except Exception as exc:
                log.warning("[PRE-FLIGHT] system manifest error: %s", exc)
                results.append(PhaseResult("preflight_manifest", Status.WARN))
        else:
            log.warning("[PRE-FLIGHT] preflight_system.py no encontrado")
            results.append(PhaseResult("preflight_manifest", Status.SKIP))
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
            targets = self.files or []
            if not targets:
                ok = compileall.compile_dir(
                    str(self.cfg.ura_root / "scripts" / "pro" / "tuneladora"),
                    force=False, quiet=1, rx=Path("__pycache__"),
                )
                if not ok:
                    return ToolResult(name="py_compile", status=Status.FAIL, summary="compileall errors")
                return ToolResult(name="py_compile", status=Status.OK, seconds=time.monotonic() - t0, summary="All syntax OK")
            for t in targets:
                r = subprocess.run(
                    [sys.executable, "-m", "py_compile", t], capture_output=True, text=True,
                    timeout=self.cfg.timeout_script, check=False,
                )
                if r.returncode != 0:
                    return ToolResult(
                        name="py_compile", status=Status.FAIL, seconds=time.monotonic() - t0,
                        summary=f"Syntax error in {t}", detail=r.stderr[:1000],
                    )
            return ToolResult(name="py_compile", status=Status.OK, seconds=time.monotonic() - t0, summary="All syntax OK")
        except Exception as e:
            return ToolResult(name="py_compile", status=Status.FAIL, summary=str(e))

    # ── Fase 2: Dinámica (pytest) ────────────────────────────

    def phase_dynamic(self) -> list[PhaseResult]:
        results: list[PhaseResult] = []
        tool = self.tools["pytest"]
        if not tool.is_available():
            return [PhaseResult("pytest", Status.SKIP)]

        focused = _discover_focused_tests(self.files)
        if focused:
            log.info("Focused tests: %s", focused)
            cache_key = f"pytest:{':'.join(focused)}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [PhaseResult("pytest_focused", Status.OK, [cached])]
            r = tool.run_check(focused)
            if r.status == Status.OK:
                self.cache.set(cache_key, r, ttl=120.0)
            results.append(PhaseResult("pytest_focused", r.status, [r]))
            if r.status == Status.FAIL:
                archivo_ref = ", ".join(focused)
                sugerencia = self.llm_fallback.analyze(r.detail, archivo_ref, "pytest")
                self.pending_queue.add(
                    archivo=archivo_ref, herramienta="pytest", severidad="high",
                    error_raw=r.detail, bloque="dynamic_focused",
                    sugerencia_llm=sugerencia or "", modelo_generador=self.cfg.llm_fallback_model,
                )
                return results
            log.info("Focused tests passed — skipping full suite")
            return results

        r = tool.run_check()
        results.append(PhaseResult("pytest_full", r.status, [r]))
        if r.status == Status.FAIL:
            sugerencia = self.llm_fallback.analyze(r.detail, ".", "pytest")
            self.pending_queue.add(
                archivo=".", herramienta="pytest", severidad="high", error_raw=r.detail,
                bloque="dynamic_full", sugerencia_llm=sugerencia or "",
                modelo_generador=self.cfg.llm_fallback_model,
            )
        return results

    # ── Fase 3: Indexación semántica ─────────────────────────

    def phase_index(self) -> list[PhaseResult]:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        changed_files = self.files
        if not changed_files:
            try:
                r = subprocess.run(
                    ["git", "diff", "--name-only"], capture_output=True, text=True,
                    timeout=10, check=False, cwd=str(self.cfg.ura_root),
                )
                if r.returncode == 0 and r.stdout:
                    changed_files = [f.strip() for f in r.stdout.split("\n") if f.strip().endswith(".py")]
            except Exception as exc:
                log.debug("git diff in phase_index failed: %s", exc)

        n_concepts = 0
        n_relations = 0
        for f in changed_files:
            fp = Path(f)
            if not fp.exists():
                fp = self.cfg.ura_root / f
            if not fp.exists() or not f.endswith(".py"):
                continue
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.semantic.learn_concept(Concept(
                        name=node.name, context=str(f), weight=1.0, tags=("function",),
                    ))
                    n_concepts += 1
                elif isinstance(node, ast.ClassDef):
                    self.semantic.learn_concept(Concept(
                        name=node.name, context=str(f), weight=1.0, tags=("class",),
                    ))
                    n_concepts += 1
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    self.semantic.learn_relation(Relation(
                        source=node.func.value.id, target=node.func.attr, relation_type="calls",
                    ))
                    n_relations += 1

        log.info("Index: %d conceptos, %d relaciones en %d archivos", n_concepts, n_relations, len(changed_files))
        return [PhaseResult("index", Status.OK, [
            ToolResult(name="index", status=Status.OK, summary=f"{n_concepts} concepts, {n_relations} relations"),
        ])]

    # ── Fase 4: API diff ──────────────────────────────────────

    def phase_api_diff(self) -> list[PhaseResult]:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        changes: list[str] = []
        for f in self.files:
            fp = Path(f)
            if not fp.exists():
                fp = self.cfg.ura_root / f
            if not fp.exists() or not f.endswith(".py"):
                continue
            try:
                new_tree = ast.parse(fp.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            new_api = _extract_api(new_tree)

            old_content = ""
            try:
                r = subprocess.run(
                    ["git", "show", f"HEAD:{f}"], capture_output=True, text=True,
                    timeout=10, check=False, cwd=str(self.cfg.ura_root),
                )
                if r.returncode == 0:
                    old_content = r.stdout
            except Exception as exc:
                log.debug("git show HEAD:%s failed: %s", f, exc)

            if old_content:
                try:
                    old_tree = ast.parse(old_content)
                    old_api = _extract_api(old_tree)
                    diffs = _api_diff(old_api, new_api)
                    changes.extend(diffs)
                except SyntaxError:
                    pass

        if changes:
            log.info("API changes:\n%s", "\n".join(changes))
            return [PhaseResult("api_diff", Status.WARN, [
                ToolResult(name="api_diff", status=Status.WARN, summary=f"{len(changes)} API changes"),
            ])]
        return [PhaseResult("api_diff", Status.OK, [
            ToolResult(name="api_diff", status=Status.OK, summary="No API changes"),
        ])]

    # ── Fase 5: Integridad ───────────────────────────────────

    def phase_integrity(self) -> list[PhaseResult]:
        from scripts.pro.tuneladora.pipeline.tools.base import ToolResult

        results: list[PhaseResult] = []
        changed_files: list[str] = []
        changed_lines = 0

        try:
            r = subprocess.run(
                ["git", "diff", "--name-only"], capture_output=True, text=True,
                timeout=self.cfg.timeout_script, check=False, cwd=str(self.cfg.ura_root),
            )
            if r.returncode == 0 and r.stdout:
                changed_files = [f for f in r.stdout.strip().split("\n") if f]
        except Exception:
            log.warning("Failed to get git diff stats")

        try:
            r = subprocess.run(
                ["git", "diff", "--numstat"], capture_output=True, text=True,
                timeout=self.cfg.timeout_script, check=False, cwd=str(self.cfg.ura_root),
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
            results.append(PhaseResult("blast_radius", Status.FAIL, [
                ToolResult(name="blast_radius", status=Status.FAIL, summary=f"{len(changed_files)} files exceeds {max_files}"),
            ]))
        elif changed_lines > max_lines:
            results.append(PhaseResult("blast_radius", Status.FAIL, [
                ToolResult(name="blast_radius", status=Status.FAIL, summary=f"{changed_lines} lines exceeds {max_lines}"),
            ]))
        else:
            results.append(PhaseResult("blast_radius", Status.OK))

        # Test manipulation detection
        test_files = [f for f in changed_files if Path(f).name.startswith("test_")]
        src_files = [f for f in changed_files if not Path(f).name.startswith("test_") and f.endswith(".py")]
        if test_files and src_files:
            msg = f"Tests modificados junto al código: {len(test_files)} tests, {len(src_files)} fuentes"
            log.warning("INTEGRITY: %s", msg)
            results.append(PhaseResult("test_manipulation", Status.WARN, [
                ToolResult(name="test_manipulation", status=Status.WARN, summary=msg),
            ]))

        free_gb: float | None = None
        try:
            free_gb = _free_disk_gb(self.cfg.ura_root)
            if free_gb is None:
                results.append(PhaseResult("disk", Status.WARN))
            elif free_gb < 1:
                results.append(PhaseResult("disk", Status.FAIL, [
                    ToolResult(name="disk", status=Status.FAIL, summary=f"Only {free_gb:.1f} GB free"),
                ]))
            else:
                results.append(PhaseResult("disk", Status.OK, [
                    ToolResult(name="disk", status=Status.OK, summary=f"{free_gb:.1f} GB free"),
                ]))
        except Exception:
            results.append(PhaseResult("disk", Status.WARN))

        self.ltm.store(LTMEntry(
            key=f"integrity_{self.mode}_{int(time.time())}",
            value={"files": len(changed_files), "lines": changed_lines, "disk_gb": free_gb or 0,
                   "test_files": len(test_files), "src_files": len(src_files)},
            source="runner.phase_integrity", tags=("integrity", "blast"),
        ))
        return results

    # ── Fase 6: Veredicto ────────────────────────────────────

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

    # ── Fase 7: Commit (solo gate) ───────────────────────────

    def phase_commit(self) -> list[PhaseResult]:
        # DESACTIVADO: auto-commit viola regla de aprobación humana.
        # Ver ADR pendiente: tuneladora no commiteará sin diff revisado.
        return [PhaseResult("commit", Status.SKIP)]
        if self.mode != "gate":
            return [PhaseResult("commit", Status.SKIP)]
        if not self.cfg.auto_commit:
            return [PhaseResult("commit", Status.SKIP)]
        try:
            msg = f"tuneladora: auto-fix {self.mode} - {len(self.files)} file(s)"
            r = subprocess.run(
                ["git", "add", "-u"], capture_output=True, text=True, timeout=30,
                check=False, cwd=str(self.cfg.ura_root),
            )
            if r.returncode != 0:
                return [PhaseResult("commit", Status.FAIL, [
                    type("ToolResult", (), {"name": "commit", "status": Status.FAIL, "summary": f"git add failed: {r.stderr[:500]}"})(),
                ])]
            r = subprocess.run(
                ["git", "commit", "-m", msg, "--no-verify"], capture_output=True, text=True, timeout=30,
                check=False, cwd=str(self.cfg.ura_root),
            )
            if r.returncode == 0:
                log.info("Committed: %s", r.stdout.strip()[:100])
                return [PhaseResult("commit", Status.OK)]
            if "nothing to commit" in r.stdout:
                return [PhaseResult("commit", Status.OK)]
            return [PhaseResult("commit", Status.WARN)]
        except Exception as e:
            return [PhaseResult("commit", Status.WARN, [
                type("ToolResult", (), {"name": "commit", "status": Status.WARN, "summary": str(e)})(),
            ])]

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
                        name=tool.name, status=Status.OK if r.returncode == 0 else Status.FAIL,
                        seconds=time.monotonic() - t0, detail=r.stdout[:2000],
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
        episode_id = f"tuneladora_{int(t_start)}_{self.mode}"
        all_phase_results: list[list[PhaseResult]] = []

        if not self._acquire_lock():
            log.error("Pipeline bloqueado por otro proceso")
            return self._finish(episode_id, Status.FAIL, "Lock activo", t_start)

        try:
            self._telemetry["start"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _conciencia.escribir_proceso("tuneladora", "iniciado", {"mode": self.mode, "n_files": len(self.files)})

            pre = self.preflight()
            all_phase_results.append(pre)
            if any(pr.status == Status.FAIL for pr in pre):
                return self._finish(episode_id, Status.FAIL, "Pre-flight failed", t_start)

            # Plugin registry: fase "pre" (solo gate/fix)
            if self.mode in ("gate", "fix"):
                try:
                    pre_result = _plugin_registry.run_phase("pre", {"mode": self.mode, "files": self.files})
                    log.info("[PLUGIN] pre: %s", pre_result.get("status"))
                except Exception as e:
                    log.warning("[PLUGIN] pre falló: %s", e)

            p0 = self.phase_snapshot()
            all_phase_results.append(p0)

            p1 = self.phase_static()
            all_phase_results.append(p1)

            # Plugin registry: fase "refactor" (solo gate/fix)
            if self.mode in ("gate", "fix"):
                try:
                    ref_result = _plugin_registry.run_phase("refactor", {"mode": self.mode, "files": self.files})
                    log.info("[PLUGIN] refactor: %s", ref_result.get("status"))
                except Exception as e:
                    log.warning("[PLUGIN] refactor falló: %s", e)

            # Sofía review (between static and dynamic)
            if self.mode in ("gate", "fix"):
                diff = subprocess.run(
                    ["git", "diff"], capture_output=True, text=True, timeout=10,
                    check=False, cwd=str(self.cfg.ura_root),
                ).stdout[:8000]
                self._sofia_report = self.sofia.review(
                    diff=diff, n_files=len(self.files),
                    tests_modified="", api_diff="",
                )
                self._telemetry["sofia_criticos"] = self._sofia_report.n_criticos
                self._telemetry["sofia_advertencias"] = self._sofia_report.n_advertencias
                if self._sofia_report.hallazgos:
                    all_phase_results.append([PhaseResult("sofia", Status.WARN)])

            p2 = self.phase_dynamic()
            all_phase_results.append(p2)

            p_api = self.phase_api_diff()
            all_phase_results.append(p_api)

            p_index = self.phase_index()
            all_phase_results.append(p_index)

            p3 = self.phase_integrity()
            all_phase_results.append(p3)

            p_commit = self.phase_commit()
            all_phase_results.append(p_commit)

            # Plugin registry: fase "post" (solo gate/fix)
            if self.mode in ("gate", "fix"):
                try:
                    post_result = _plugin_registry.run_phase("post", {"mode": self.mode, "files": self.files, "verdict": verdict.name if 'verdict' in dir() else "unknown"})
                    log.info("[PLUGIN] post: %s", post_result.get("status"))
                except Exception as e:
                    log.warning("[PLUGIN] post falló: %s", e)

            verdict, msg = self.phase_verdict(all_phase_results)

            if verdict == Status.FAIL and self._last_snapshot is not None:
                log.warning("Pipeline FAILED — restoring snapshot %s", self._last_snapshot.name)
                self.snapshot_manager.restore(self._last_snapshot)
                msg = "Pipeline FAILED — rollback executed"

            # ADR auto-generation DESACTIVADO — ver ADR-223 (loop infinito)
            # if self.mode == "gate" and verdict == Status.OK:
            #     try:
            #         r = subprocess.run(
            #             [sys.executable, str(self.cfg.ura_root / "scripts/pro/adr_generator.py")],
            #             capture_output=True, text=True, timeout=15,
            #             check=False, cwd=str(self.cfg.ura_root),
            #         )
            #         if r.returncode == 0 and r.stdout.strip():
            #             log.info("ADR: %s", r.stdout.strip()[:100])
            #     except Exception:
            #         pass

            head = ""
            with contextlib.suppress(Exception):
                head = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                    timeout=5, check=False, cwd=str(self.cfg.ura_root),
                ).stdout.strip()

            self._telemetry["duration_s"] = time.monotonic() - t_start
            self._telemetry["verdict"] = verdict.name
            _conciencia.escribir_proceso("tuneladora", verdict.name, {"duration_s": self._telemetry["duration_s"], "msg": msg})
            self._telemetry["n_files"] = len(self.files)
            self._telemetry["head"] = head

            self.pending_queue.record_run(
                mode=self.mode, verdict=verdict.value, seconds=time.monotonic() - t_start,
                n_files=len(self.files), head=head, failures=msg if verdict != Status.OK else "",
            )

            log.info("Pipeline %s: %s (%.1fs) [sofia: %d/%d]",
                     self.mode, msg, time.monotonic() - t_start,
                     self._sofia_report.n_criticos, self._sofia_report.n_advertencias)
            return self._finish(episode_id, verdict, msg, t_start)
        finally:
            self._release_lock()

    def _recolectar_coverage(self) -> None:
        """Recolecta cobertura desde coverage.xml si existe (pytest con --cov).

        Si el pipeline no ejecutó pytest con --cov, coverage_global queda 0
        y el reporte lo documenta (Gap #5 del Plan Maestro).
        """
        try:
            cov_xml = self.cfg.ura_root / "coverage.xml"
            if not cov_xml.exists():
                return
            import xml.etree.ElementTree as ET

            tree = ET.parse(str(cov_xml))
            root = tree.getroot()
            rate = float(root.attrib.get("line-rate", 0))
            self._telemetry["coverage_global"] = round(rate * 100, 1)
        except (OSError, ValueError, TypeError, ET.ParseError):
            self._telemetry["coverage_global"] = 0

    def _finish(self, episode_id: str, verdict: Status, msg: str, t_start: float) -> Status:
        duration_ms = (time.monotonic() - t_start) * 1000
        details = {
            "mode": self.mode,
            "n_files": len(self.files),
            "sofia_criticos": self._sofia_report.n_criticos,
            "sofia_advertencias": self._sofia_report.n_advertencias,
            "telemetry": self._telemetry,
        }
        self.episodic.record(Episode(
            episode_id=episode_id, pipeline="tuneladora", status=verdict.name,
            started=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t_start)),
            finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
            summary=msg, details=details,
            duration_ms=duration_ms, error=msg if verdict == Status.FAIL else None,
        ))
        self._recolectar_coverage()
        report = self._write_json_report(episode_id, verdict, msg, duration_ms)
        if verdict == Status.FAIL:
            try:
                from scripts.pro.tuneladora.notifier import notificar_fallo

                notificar_fallo(report)
            except Exception as e:
                log.warning("notificar_fallo falló: %s", e)
        if verdict == Status.OK:
            self.ltm.store(LTMEntry(
                key=f"ok_{episode_id}",
                value={"mode": self.mode, "files": self.files, "duration_ms": duration_ms, "msg": msg},
                source="runner.run", tags=("pipeline", "ok"),
            ))

        # Registrar en change_log (unified change log)
        try:
            head = self._telemetry.get("head", "")
            if head:
                _change_log.record(head, actor="ia")
        except Exception as e:
            log.warning("change_log falló: %s", e)

        # Auditoría continua
        try:
            audit = _auditoria_continua.run_all(verbose=False)
            log.info("[AUDIT] Score: %.1f%%", audit["score"])
        except Exception as e:
            log.warning("[AUDIT] falló: %s", e)

        return verdict

    def _write_json_report(self, episode_id: str, verdict: Status, msg: str, duration_ms: float) -> dict:
        """Persiste el reporte estructurado del pipeline en data/tuneladora_reports/.

        Retorna el reporte (dict) para que el llamador pueda notificar.
        """
        report = _build_json_report(
            episode_id=episode_id,
            verdict=verdict,
            msg=msg,
            duration_ms=duration_ms,
            mode=self.mode,
            files=self.files,
            telemetry=self._telemetry,
            sofia_n_criticos=self._sofia_report.n_criticos,
            sofia_n_advertencias=self._sofia_report.n_advertencias,
        )
        try:
            out_dir = self.cfg.ura_root / "data" / "tuneladora_reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{episode_id}.json").write_text(json.dumps(report, indent=2))
        except OSError as e:
            log.warning("no se pudo escribir reporte JSON: %s", e)
        return report
