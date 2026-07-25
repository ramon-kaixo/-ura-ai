"""Layer 3: Shadow Execution — run new code vs HEAD, compare output."""
from __future__ import annotations

import ast
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("shadow.layer3")


@dataclass
class ShadowResult:
    file: str
    status: str  # OK / WARN / FAIL
    detail: str = ""
    duration_ms: float = 0.0


def _git_show(path: str, ura_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "show", f"HEAD:{path}"], capture_output=True, text=True,
            timeout=10, check=False, cwd=str(ura_root),
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception as exc:
        log.debug("git show HEAD:%s failed: %s", path, exc)
        return ""


def _extract_callables(source: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    funcs: list[dict[str, Any]] = []
    method_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{node.name}.{child.name}"
                    method_ids.add(id(child))
                    funcs.append({
                        "name": qualname,
                        "lineno": child.lineno,
                        "args": [a.arg for a in child.args.args],
                    })
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in method_ids:
                funcs.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [a.arg for a in node.args.args],
                })
    return funcs


def run(files: list[str], ura_root: Path) -> list[ShadowResult]:
    results: list[ShadowResult] = []
    for f in files:
        t0 = time.monotonic()
        if not f.endswith(".py"):
            results.append(ShadowResult(f, "SKIP", "Not a Python file"))
            continue

        new_path = Path(f)
        if not new_path.exists():
            new_path = ura_root / f
        if not new_path.exists():
            results.append(ShadowResult(f, "SKIP", "File not found"))
            continue

        old_content = _git_show(f, ura_root)
        if not old_content:
            results.append(ShadowResult(f, "OK", "New file, no previous version to compare"))
            results[-1].duration_ms = (time.monotonic() - t0) * 1000
            continue

        new_content = new_path.read_text(encoding="utf-8", errors="replace")
        if new_content == old_content:
            results.append(ShadowResult(f, "OK", "No changes"))
            results[-1].duration_ms = (time.monotonic() - t0) * 1000
            continue

        old_funcs = _extract_callables(old_content)
        new_funcs = _extract_callables(new_content)

        old_names = {f["name"] for f in old_funcs}
        new_names = {f["name"] for f in new_funcs}
        removed = old_names - new_names
        added = new_names - old_names
        common = old_names & new_names

        changes: list[str] = []
        for name in sorted(removed):
            changes.append(f"  - {name} (removed)")
        for name in sorted(added):
            changes.append(f"  + {name} (added)")
        for name in sorted(common):
            old_f = next(f for f in old_funcs if f["name"] == name)
            new_f = next(f for f in new_funcs if f["name"] == name)
            if old_f["args"] != new_f["args"]:
                changes.append(f"  ~ {name}: args {old_f['args']} -> {new_f['args']}")

        args_changed = any("~" in ch for ch in changes)
        if removed or args_changed:
            n_msg = len(removed) + (1 if args_changed else 0)
            results.append(ShadowResult(f, "WARN", f"API surface changed ({n_msg}): removed={len(removed)}, args_changed={args_changed}"))
        else:
            results.append(ShadowResult(f, "OK", f"{len(added)} new functions"))

        results[-1].duration_ms = (time.monotonic() - t0) * 1000

    return results
