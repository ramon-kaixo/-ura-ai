#!/usr/bin/env python3
"""Health check para motor/brain/ — verifica imports, instancias, hooks.

Uso:
    python3 scripts/health_check_brain.py           # stdout
    python3 scripts/health_check_brain.py --json     # JSON output
    python3 scripts/health_check_brain.py --ci       # exit code 1 on failure
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Asegurar que el repo root esta en sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

BRAIN_MODULES = [
    "motor.brain.analyzer",
    "motor.brain.advisor",
    "motor.brain.alerts",
    "motor.brain.observer",
    "motor.brain.auto_maintain",
    "motor.brain.executor",
    "motor.brain.web_adapter",
]

BRAIN_CLASSES: dict[str, str] = {
    "motor.brain.analyzer": "CodeAnalyzer",
    "motor.brain.advisor": "ArchitectureAdvisor",
    "motor.brain.alerts": "AlertEngine",
    "motor.brain.observer": "BrainObserver",
    "motor.brain.auto_maintain": "AutoMaintainer",
    "motor.brain.executor": "ProposalExecutor",
    "motor.brain.web_adapter": "WebLearningAdapter",
}


def check_imports() -> dict[str, str]:
    """Verifica que todos los modulos importan correctamente."""
    results: dict[str, str] = {}
    for mod_name in BRAIN_MODULES:
        try:
            importlib.import_module(mod_name)
            results[mod_name] = "ok"
        except ImportError as e:
            results[mod_name] = f"fail: {e}"
    return results


def check_classes(imports: dict[str, str]) -> dict[str, str]:
    """Verifica que las clases principales existen."""
    results: dict[str, str] = {}
    for mod_name, class_name in BRAIN_CLASSES.items():
        if imports.get(mod_name) != "ok":
            results[f"{mod_name}.{class_name}"] = "skip (import failed)"
            continue
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, class_name, None)
            if cls is None:
                results[f"{mod_name}.{class_name}"] = "fail: class not found"
            else:
                results[f"{mod_name}.{class_name}"] = "ok"
        except Exception as e:
            results[f"{mod_name}.{class_name}"] = f"fail: {e}"
    return results


def check_instantiation() -> dict[str, str]:
    """Verifica que AutoMaintainer se instancia con mocks."""
    results: dict[str, str] = {}
    try:
        from unittest import mock

        from motor.brain.auto_maintain import AutoMaintainer
        from motor.brain.executor import ProposalExecutor
        from motor.brain.observer import BrainObserver

        observer = mock.Mock(spec=BrainObserver)
        executor = mock.Mock(spec=ProposalExecutor)
        maintainer = AutoMaintainer(observer, executor)

        if hasattr(maintainer, "scan") and hasattr(maintainer, "approve_and_execute"):
            results["AutoMaintainer()"] = "ok"
        else:
            results["AutoMaintainer()"] = "fail: missing methods"
    except Exception as e:
        results["AutoMaintainer()"] = f"fail: {e}"

    try:
        from motor.brain.observer import BrainObserver
        from motor.brain.alerts import AlertEngine

        engine = AlertEngine(mock.Mock(spec=BrainObserver))
        if hasattr(engine, "evaluate"):
            results["AlertEngine()"] = "ok"
        else:
            results["AlertEngine()"] = "fail: missing evaluate"
    except Exception as e:
        results["AlertEngine()"] = f"fail: {e}"

    try:
        from motor.brain.executor import ProposalExecutor

        ex = ProposalExecutor()
        if hasattr(ex, "execute") and hasattr(ex, "_get_engine"):
            results["ProposalExecutor()"] = "ok"
        else:
            results["ProposalExecutor()"] = "fail: missing methods"
    except Exception as e:
        results["ProposalExecutor()"] = f"fail: {e}"

    return results


def check_hooks() -> dict[str, str]:
    """Ejecuta pre-commit hooks en motor/brain/ y reporta resultados."""
    results: dict[str, str] = {}
    hooks = ["ruff", "ruff-format", "mypy", "bandit"]

    for hook in hooks:
        try:
            import os as _os

            env = dict((k, v) for k, v in [("TMPDIR", "/tmp"), ("PRE_COMMIT_HOME", "/tmp/pre-commit-home"), ("PATH", f"{_REPO_ROOT}/.venv/bin:{_os.environ.get('PATH', '')}")])
            proc = subprocess.run(
                [sys.executable, "-m", "pre_commit", "run", hook, "--files", "motor/brain/"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(_REPO_ROOT),
                env=env,
            )
            combined = proc.stdout + proc.stderr
            if "Passed" in combined or "Skipped" in combined:
                results[hook] = "ok"
            elif "Failed" in combined:
                results[hook] = "fail"
            else:
                results[hook] = f"unknown: {combined.strip()[:100]}"
        except subprocess.TimeoutExpired:
            results[hook] = "timeout"
        except Exception as e:
            results[hook] = f"error: {e}"

    return results


def compute_overall(
    imports: dict[str, str],
    classes: dict[str, str],
    instances: dict[str, str],
    hooks: dict[str, str],
) -> str:
    """Calcula estado general."""
    all_ok = True
    for cat in (imports, classes, instances, hooks):
        for v in cat.values():
            if v != "ok" and not v.startswith("skip"):
                all_ok = False
                break
        if not all_ok:
            break
    return "ok" if all_ok else "fail"


def collect_failures(
    imports: dict[str, str],
    classes: dict[str, str],
    instances: dict[str, str],
    hooks: dict[str, str],
) -> list[str]:
    """Recopila todos los fallos para reporte."""
    failures: list[str] = []
    for name, status in imports.items():
        if status != "ok":
            failures.append(f"[import] {name}: {status}")
    for name, status in classes.items():
        if status != "ok":
            failures.append(f"[class] {name}: {status}")
    for name, status in instances.items():
        if status != "ok":
            failures.append(f"[instance] {name}: {status}")
    for name, status in hooks.items():
        if status != "ok":
            failures.append(f"[hook] {name}: {status}")
    return failures


def main() -> int:
    args = set(sys.argv[1:])
    as_json = "--json" in args or "-j" in args
    ci_mode = "--ci" in args or "-c" in args

    imports = check_imports()
    classes = check_classes(imports)
    instances = check_instantiation()
    hooks = check_hooks()
    overall = compute_overall(imports, classes, instances, hooks)
    failures = collect_failures(imports, classes, instances, hooks)

    report: dict[str, Any] = {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "modules": imports,
        "classes": classes,
        "instantiation": instances,
        "hooks": hooks,
    }

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Brain Health Check — {datetime.now(UTC).isoformat()}")
        print(f"Status: {overall.upper()}")
        print()
        print("Modules:")
        for name, status in sorted(imports.items()):
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {name}: {status}")
        print()
        print("Classes:")
        for name, status in sorted(classes.items()):
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {name}: {status}")
        print()
        print("Instantiation:")
        for name, status in sorted(instances.items()):
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {name}: {status}")
        print()
        print("Hooks:")
        for name, status in sorted(hooks.items()):
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {name}: {status}")
        print()
        if failures:
            print(f"FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  • {f}")
        else:
            print("No failures.")

    if ci_mode and failures:
        return 1
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
