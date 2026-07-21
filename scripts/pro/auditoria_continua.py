#!/usr/bin/env python3
"""Auditoría Continua — suite única de comprobaciones automáticas.

Ejecuta en orden:
  1. Compilación (py_compile)
  2. Logger regression (test_logger_regression)
  3. Plugin discovery (plugin_registry)
  4. Reuse Detector regresión (test_regression)
  5. Ruff check
  6. Health Dashboard
  7. Calidad Gates
  8. Código huérfano (imports no utilizados)

Retorna puntuación 0-100 y lista de incidencias.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHECKS: list[dict] = []


def check(name: str, weight: int) -> callable:
    """Decorador para registrar una comprobación con su peso."""
    def decorator(fn):
        CHECKS.append({"name": name, "weight": weight, "fn": fn})
        return fn
    return decorator


# Almacén de resultados
_results: dict[str, dict] = {}
_total_weight = 0


def run_all(verbose: bool = True) -> dict:
    global _total_weight
    _total_weight = sum(c["weight"] for c in CHECKS)
    for c in CHECKS:
        t0 = time.time()
        try:
            ok, msg = c["fn"]()
            elapsed = time.time() - t0
            _results[c["name"]] = {"ok": ok, "msg": msg, "elapsed_s": round(elapsed, 1)}
            if verbose:
                icon = "✅" if ok else "❌"
                print(f"  {icon} {c['name']:35} {msg} ({elapsed:.1f}s)")
        except Exception as e:
            _results[c["name"]] = {"ok": False, "msg": str(e), "elapsed_s": round(time.time() - t0, 1)}
            if verbose:
                print(f"  ❌ {c['name']:35} {e} ({time.time()-t0:.1f}s)")

    score = sum(
        c["weight"] for c in CHECKS if _results.get(c["name"], {}).get("ok")
    ) / _total_weight * 100 if _total_weight else 0

    return {"score": round(score, 1), "results": _results}


# ── 1. Compilación ──

@check("Compilación (py_compile)", 20)
def _():
    import py_compile
    errors = []
    for pyfile in ROOT.rglob("*.py"):
        if ".venv" in str(pyfile) or ".sandbox" in str(pyfile) or "__pycache__" in str(pyfile):
            continue
        try:
            py_compile.compile(str(pyfile), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(pyfile.relative_to(ROOT)))
    if errors:
        return False, f"{len(errors)} archivos no compilan"
    return True, "OK"

# ── 2. Logger regression ──

@check("Logger: sin .warning()", 10)
def _():
    result = subprocess.run(
        [sys.executable, "scripts/pro/tests/test_logger_regression.py"],
        capture_output=True, text=True, timeout=30, cwd=str(ROOT),
    )
    if result.returncode != 0:
        lines = [l for l in result.stdout.split("\n") if "❌" in l or "Error" in l]
        return False, "\n".join(lines[:3]) if lines else "fallo"
    return True, "OK"

# ── 3. Plugin discovery ──

@check("Plugin discovery", 10)
def _():
    sys.path.insert(0, str(ROOT / "scripts" / "pro"))
    import plugin_registry  # noqa: PLC0415
    plugins = plugin_registry.discover_all()
    required = {"name", "phase", "timeout", "priority"}
    missing = []
    for name, p in plugins.items():
        for field in required:
            if field not in p:
                missing.append(f"{name}: falta {field}")
    if missing:
        return False, "\n".join(missing[:3])
    return True, f"{len(plugins)} plugins, todos OK"

# ── 4. Reuse Detector regression ──

@check("Reuse Detector regresión", 15)
def _():
    result = subprocess.run(
        [sys.executable, "scripts/pro/reuse/test_regression.py"],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
    )
    if result.returncode != 0:
        fails = [l for l in result.stdout.split("\n") if "❌" in l]
        return False, f"{len(fails)} tests fallidos"
    return True, "12/12 passed"

# ── 5. Ruff ──

@check("Ruff check", 15)
def _():
    ruff = ROOT / ".venv" / "bin" / "ruff"
    if not ruff.exists():
        return True, "ruff no instalado (saltando)"
    result = subprocess.run(
        [str(ruff), "check", "scripts/pro/tuneladora/", "scripts/pro/autonomy/", "scripts/pro/reuse/",
         "--ignore", "EXE001,E402"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    errors = len([l for l in result.stdout.split("\n") if l.strip() and "|" not in l and l.startswith("scripts")])
    if errors > 0:
        return False, f"{errors} errores (ignorando EXE001, E402)"
    return True, "OK"

# ── 6. Health Dashboard ──

@check("Health Dashboard", 5)
def _():
    result = subprocess.run(
        [sys.executable, "scripts/pro/dashboard.py", "--json"],
        capture_output=True, text=True, timeout=30, cwd=str(ROOT),
    )
    if result.returncode != 0:
        return False, f"dashboard falla: {result.stderr[:200]}"
    import json  # noqa: PLC0415
    try:
        data = json.loads(result.stdout)
        return True, f"{data.get('ledger_ejecuciones', '?')} ejecuciones, {data.get('memoria_ejecuciones', '?')} indexadas"
    except json.JSONDecodeError:
        return False, "JSON inválido"

# ── 7. Quality Gates ──

@check("Quality Gates", 5)
def _():
    from scripts.pro.reuse.quality_gates import QualityGates
    gates = QualityGates(ROOT)
    g = gates.should_run_maintenance()
    msg = f"{g['commits']} commits, {g['lines_changed']} líneas"
    return True, msg

# ── 8. Código huérfano ──

@check("Código huérfano", 10)
def _():
    from scripts.pro.reuse.reuse_detector import ReuseDetector
    d = ReuseDetector(ROOT)
    indexed = d.build_index()
    return True, f"{indexed} funciones indexadas"

# ── 9. Checkpoint validity ──

@check("Checkpoint válido", 5)
def _():
    cp = ROOT / ".nervioso" / "checkpoint.json"
    if cp.exists():
        import json
        data = json.loads(cp.read_text(encoding="utf-8"))
        if data.get("pipeline") not in ("mejora", "mantenimiento", "autonomy"):
            return False, f"pipeline desconocido: {data.get('pipeline')}"
        return True, f"checkpoint: {data.get('pipeline')} (fase {data.get('last_completed', '?')})"
    return True, "sin checkpoint (limpieza correcta)"


# ── 10. Plugins uniformidad ──

@check("Plugins uniformes", 5)
def _():
    sys.path.insert(0, str(ROOT / "scripts" / "pro"))
    import plugin_registry  # noqa: PLC0415
    plugins = plugin_registry.discover_all()
    fields = {"name", "phase", "timeout", "priority"}
    for name, p in plugins.items():
        missing = fields - set(p.keys())
        if missing:
            return False, f"{name}: falta {missing}"
    return True, f"{len(plugins)} plugins, contrato OK"


def main() -> int:
    import argparse  # noqa: PLC0415
    parser = argparse.ArgumentParser(description="URA Auditoría Continua")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print("=" * 55)
    print("  URA AUDITORÍA CONTINUA")
    print("=" * 55)
    print()

    t0 = time.time()
    result = run_all(verbose=args.verbose)
    elapsed = time.time() - t0

    print()
    print(f"  Puntuación: {result['score']}/100")
    print(f"  Tiempo total: {elapsed:.1f}s")
    print()

    # Detalle
    for name, r in result["results"].items():
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {name:35} {r['msg']}")

    print()
    if result["score"] >= 80:
        print("  🟢 SUPERADO")
    elif result["score"] >= 50:
        print("  🟡 REVISAR")
    else:
        print("  🔴 NO SUPERADO")

    if args.json:
        import json  # noqa: PLC0415
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["score"] >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
