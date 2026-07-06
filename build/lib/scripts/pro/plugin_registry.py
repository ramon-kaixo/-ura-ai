#!/usr/bin/env python3
"""Plugin Registry — Auto-descubrimiento de scripts."""

import ast
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def log(msg) -> None:
    datetime.now(UTC).strftime("%H:%M:%S")


def discover_all():
    plugins = {}
    for py_file in sorted(SCRIPT_DIR.glob("*.py")):
        if py_file.name in ("plugin_registry.py", "PLUGIN_TEMPLATE.py"):
            continue
        try:
            content = py_file.read_text()
            tree = ast.parse(content)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "PLUGIN":
                            plugin_dict = ast.literal_eval(node.value)
                            plugin_dict["script"] = str(py_file)
                            name = plugin_dict.get("name", py_file.stem)
                            plugins[name] = plugin_dict
        except Exception:
            pass
    return plugins


def run_phase(phase, context=None, file_path=None):
    plugins = discover_all()
    phase_plugins = {name: p for name, p in plugins.items() if p.get("phase") == phase or p.get("phase") == "always"}

    if not phase_plugins:
        log(f"Fase '{phase}': sin plugins")
        return {"status": "empty", "phase": phase}

    log("")
    log("=" * 50)
    log(f"  FASE: {phase.upper()} ({len(phase_plugins)} plugins)")
    log("=" * 50)

    results = {}
    for name, plugin in phase_plugins.items():
        log(f"  ▶ {name} (timeout={plugin.get('timeout', 30)}s)")

        cmd = [sys.executable, plugin["script"]]
        cmd.extend(plugin.get("args", []))

        if file_path and plugin.get("needs_file"):
            cmd.append(file_path)
        elif not file_path and "--scan" not in str(cmd):
            cmd.append("--scan")

        t0 = time.time()
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=plugin.get("timeout", 30),
                cwd=str(SCRIPT_DIR.parent.parent),
                check=False,
            )
            elapsed = round(time.time() - t0, 2)

            if r.returncode == 0:
                log(f"    ✅ {name} ({elapsed}s)")
                results[name] = {"status": "ok", "exit_code": 0, "elapsed": elapsed}
            else:
                log(f"    ❌ {name} falló (exit {r.returncode})")
                if r.stderr:
                    for line in r.stderr.strip().split("\n")[:3]:
                        log(f"       {line}")
                results[name] = {
                    "status": "error",
                    "exit_code": r.returncode,
                    "stderr": r.stderr[:500],
                }

                if plugin.get("blocking"):
                    log(f"  ⛔ Fase '{phase}' abortada por {name}")
                    results["_aborted_by"] = name
                    return {"status": "aborted", "phase": phase, "results": results}

        except subprocess.TimeoutExpired:
            log(f"    ⏰ {name} timeout ({plugin.get('timeout', 30)}s)")
            results[name] = {"status": "timeout"}
            if plugin.get("blocking"):
                results["_aborted_by"] = name
                return {"status": "aborted", "phase": phase, "results": results}

    ok = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "ok")
    log(f"\n  Fase '{phase}': {ok} OK, {len(results) - ok - (1 if '_aborted_by' in results else 0)} errores")

    return {"status": "completed", "phase": phase, "results": results}


def list_plugins() -> None:
    plugins = discover_all()
    log("")
    log("=" * 55)
    log(f"  PLUGIN REGISTRY — {len(plugins)} plugins descubiertos")
    log("=" * 55)
    for name, p in plugins.items():
        icon = "⚡" if p.get("blocking") else "○"
        log(f"  {icon} {p.get('phase', '?'):10} {name:30} (timeout={p.get('timeout', 30)}s)")
    log("")


if __name__ == "__main__":
    if "--list" in sys.argv:
        discover_all()
        list_plugins()
    elif "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        phase = sys.argv[idx + 1]
        file_path = None
        if "--file" in sys.argv:
            fidx = sys.argv.index("--file")
            file_path = sys.argv[fidx + 1]
        run_phase(phase, file_path=file_path)
    else:
        pass
