#!/usr/bin/env python3
"""Plugin Registry v2 — Auto-descubrimiento con prioridades, dependencias y versionado.

Contrato:
  PLUGIN = {
      "name": "...",
      "phase": "pre|refactor|post|maintenance",
      "priority": 100,         # menor = primero
      "timeout": 30,
      "blocking": True,        # si falla, aborta la fase
      "needs_file": False,
      "requires": [],          # nombres de plugins requeridos
      "incompatible": [],      # nombres de plugins incompatibles
      "min_engine_version": "1.0",
      "args": ["--json"],
  }
"""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
ENGINE_VERSION = "1.0"


def log(msg: str) -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _resolve_dependencies(plugins: dict[str, Any]) -> list[tuple[str, Any]]:
    """Ordena plugins por prioridad, verificando dependencias e incompatibilidades.

    R2: dependencias, prioridades, incompatibilidades, versión mínima.
    """
    ordered: list[tuple[str, Any]] = []
    resolved: set[str] = set()

    def _resolve(name: str) -> None:
        if name in resolved:
            return
        p = plugins.get(name)
        if not p:
            log(f"  ⚠️  Dependencia no encontrada: {name}")
            return
        for dep in p.get("requires", []):
            _resolve(dep)
        for inc in p.get("incompatible", []):
            if inc in resolved:
                log(f"  ⛔ Incompatible: {name} con {inc}")
                return
        ver = p.get("min_engine_version", "1.0")
        if tuple(map(int, ver.split("."))) > tuple(map(int, ENGINE_VERSION.split("."))):
            log(f"  ⛔ {name} requiere engine {ver}, actual {ENGINE_VERSION}")
            return
        resolved.add(name)
        ordered.append((name, p))

    sorted_plugins = sorted(plugins.items(), key=lambda x: x[1].get("priority", 500))
    for name, _ in sorted_plugins:
        _resolve(name)
    return ordered


def discover_all() -> dict[str, Any]:
    """Descubre todos los plugins en scripts/pro/ analizando PLUGIN = {...}."""
    plugins: dict[str, Any] = {}
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
                            plugin_dict.setdefault("priority", 500)
                            plugin_dict.setdefault("requires", [])
                            plugin_dict.setdefault("incompatible", [])
                            plugin_dict.setdefault("min_engine_version", "1.0")
                            plugin_dict.setdefault("capability", "infrastructure")
                            plugins[name] = plugin_dict
        except Exception:  # noqa: S110
            pass
    return plugins


def run_phase(
    phase: str,
    context: Any = None,
    file_path: str | None = None,
    capability: str | None = None,
) -> dict[str, Any]:
    """Ejecuta todos los plugins de una fase, ordenados por prioridad.

    Args:
        phase: "pre", "refactor", "post", "maintenance"
        capability: filtrar por capacidad ("infrastructure", "autonomy"). None = todos.
    """
    plugins = discover_all()
    phase_plugins = {
        name: p
        for name, p in plugins.items()
        if (p.get("phase") == phase or p.get("phase") == "always")
        and (capability is None or p.get("capability") == capability)
    }

    if not phase_plugins:
        log(f"Fase '{phase}': sin plugins")
        return {"status": "empty", "phase": phase, "results": {}}

    ordered = _resolve_dependencies(phase_plugins)
    if not ordered:
        log(f"Fase '{phase}': 0 plugins tras resolver dependencias")
        return {"status": "empty", "phase": phase, "results": {}}

    log("")
    log("=" * 50)
    log(f"  FASE: {phase.upper()} ({len(ordered)} plugins)")
    log("=" * 50)

    results: dict[str, Any] = {}
    for name, plugin in ordered:
        log(f"  ▶ {name} (timeout={plugin.get('timeout', 30)}s, pri={plugin.get('priority', 500)})")

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
    err = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") in ("error", "timeout"))
    log(f"\n  Fase '{phase}': {ok} OK, {err} errores")

    return {"status": "completed", "phase": phase, "results": results, "ok": ok, "errors": err}


def list_plugins() -> None:
    plugins = discover_all()
    ordered = sorted(plugins.items(), key=lambda x: (x[1].get("phase", "?"), x[1].get("priority", 500)))
    log("")
    log("=" * 55)
    log(f"  PLUGIN REGISTRY v2 — {len(plugins)} plugins")
    log("=" * 55)
    for name, p in ordered:
        icon = "⚡" if p.get("blocking") else "○"
        reqs = f" req:{p['requires']}" if p.get("requires") else ""
        pri = p.get("priority", 500)
        log(f"  {icon} {p.get('phase', '?'):10} pri={pri:>3} {name:30} (timeout={p.get('timeout', 30)}s){reqs}")
    log("")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_plugins()
    elif "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        phase = sys.argv[idx + 1]
        file_path = None
        if "--file" in sys.argv:
            fidx = sys.argv.index("--file")
            file_path = sys.argv[fidx + 1]
        run_phase(phase, file_path=file_path)
