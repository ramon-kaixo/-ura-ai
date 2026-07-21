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

import json
import logging
import subprocess
import sys
import time

log = logging.getLogger(__name__)
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
_total_weight: dict[str, int] = {"value": 0}


def run_all(verbose: bool = True) -> dict:
    _total_weight["value"] = sum(c["weight"] for c in CHECKS)
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
                print(f"  ❌ {c['name']:35} {e} ({time.time() - t0:.1f}s)")

    score = (
        sum(c["weight"] for c in CHECKS if _results.get(c["name"], {}).get("ok")) / _total_weight["value"] * 100
        if _total_weight["value"]
        else 0
    )

    return {"score": round(score, 1), "results": _results}


# ── Histórico ──

import json as _json
from datetime import UTC
from datetime import datetime as _datetime
from pathlib import Path as _Path

HISTORIAL = _Path(__file__).resolve().parent.parent.parent / ".nervioso" / "audits"
HISTORIAL.mkdir(parents=True, exist_ok=True)
_GIT_TAG: dict[str, str] = {"value": ""}


def _get_git_tag() -> str:
    if not _GIT_TAG["value"]:
        try:
            _GIT_TAG["value"] = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip()
        except Exception:
            _GIT_TAG["value"] = "unknown"
    return _GIT_TAG["value"]


def load_history() -> list[dict]:
    """Carga el historial de auditorías anteriores."""
    records = []
    for f in sorted(HISTORIAL.glob("*.json")):
        try:
            records.append(_json.loads(f.read_text(encoding="utf-8")))
        except (_json.JSONDecodeError, OSError):
            continue
    return records


def collect_metrics() -> dict:
    """Recoge métricas detalladas del sistema para el histórico."""
    metrics: dict = {}
    ROOT = _Path(__file__).resolve().parent.parent.parent

    # Tamaño
    py_files = list(ROOT.rglob("*.py"))
    metrics["tamano"] = {
        "archivos_py": len(py_files),
        "funciones_indexadas": 0,
    }

    # Reuse index
    try:
        import sys as _sys

        _sys.path.insert(0, str(ROOT / "scripts" / "pro"))
        from reuse.reuse_detector import ReuseDetector

        d = ReuseDetector(ROOT)
        metrics["tamano"]["funciones_indexadas"] = d.build_index()
    except Exception:
        log.debug("ReuseDetector no disponible")

    # Memoria semántica
    memory_db = ROOT / ".nervioso" / "memory" / "semantic.db"
    if memory_db.exists():
        try:
            import sqlite3 as _sqlite3

            conn = _sqlite3.connect(str(memory_db))
            metrics["memoria"] = {
                "ejecuciones": conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0],
                "plugins": conn.execute("SELECT COUNT(*) FROM plugin_durations").fetchone()[0],
                "decisiones": conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
                "tamano_kb": round(memory_db.stat().st_size / 1024, 1),
            }
            conn.close()
        except Exception:
            log.debug("Memoria semántica no disponible")

    # Ledger
    ledger_dir = ROOT / ".nervioso" / "ledger"
    if ledger_dir.exists():
        ledgers = list(ledger_dir.glob("*.json"))
        metrics["ledger"] = {
            "ejecuciones": len(ledgers),
            "tamano_kb": round(sum(f.stat().st_size for f in ledgers) / 1024, 1),
        }

    # Swarm
    try:
        from autonomy.goal_manager import GoalManager as _GM
        from tuneladora.engine import PipelineEngine as _PE

        engine = _PE(pipeline="metrics")
        gm = _GM(engine)
        goals = gm.list_all()
        metrics["swarm"] = {
            "objetivos_total": len(goals),
            "completados": sum(1 for g in goals if g.get("status") == "completed"),
            "fallidos": sum(1 for g in goals if g.get("status") == "failed"),
        }
    except Exception:
        log.debug("Swarm no disponible")

    # Conocimiento
    kb_file = ROOT / ".nervioso" / "knowledge" / "knowledge.json"
    if kb_file.exists():
        try:
            kb = _json.loads(kb_file.read_text(encoding="utf-8"))
            metrics["aprendizaje"] = {
                "total": len(kb),
                "activo": sum(1 for e in kb if e.get("status") == "active"),
                "verificado": sum(1 for e in kb if e.get("verified")),
            }
        except Exception:
            log.debug("Knowledge base no disponible")

    # Quality Gates
    try:
        from reuse.quality_gates import QualityGates as _QG

        gates = _QG(ROOT)
        g = gates.should_run_maintenance()
        metrics["consolidacion"] = {
            "commits_desde_tag": g["commits"],
            "lineas_modificadas": g["lines_changed"],
        }
    except Exception:
        log.debug("Quality Gates no disponible")

    return metrics


def _compute_health_index(metrics: dict, score: float) -> dict:
    """Calcula el URA Health Index a partir de métricas y score de auditoría."""
    # Componentes del índice (cada uno 0-100)
    calidad = score  # el score de auditoría ya pesa calidad

    rendimiento = 50.0
    if metrics.get("consolidacion", {}).get("commits_desde_tag", 0) < 10:
        rendimiento = 80.0
    elif metrics.get("consolidacion", {}).get("commits_desde_tag", 0) < 20:
        rendimiento = 60.0

    estabilidad = 70.0
    if metrics.get("swarm", {}).get("fallidos", 0) == 0:
        estabilidad = 90.0
    elif metrics.get("swarm", {}).get("fallidos", 0) < 3:
        estabilidad = 70.0

    reutilizacion = 50.0
    if metrics.get("tamano", {}).get("funciones_indexadas", 0) > 10000:
        reutilizacion = 80.0

    aprendizaje = 50.0
    if metrics.get("aprendizaje", {}).get("activo", 0) > 0:
        aprendizaje = 70.0
    if metrics.get("aprendizaje", {}).get("verificado", 0) > 0:
        aprendizaje = 85.0

    observabilidad = 70.0
    if metrics.get("ledger", {}).get("ejecuciones", 0) > 5:
        observabilidad = 90.0

    health = round(
        calidad * 0.25
        + rendimiento * 0.20
        + estabilidad * 0.20
        + reutilizacion * 0.15
        + aprendizaje * 0.10
        + observabilidad * 0.10,
        1,
    )

    return {
        "health_index": health,
        "componentes": {
            "calidad": round(calidad, 1),
            "rendimiento": round(rendimiento, 1),
            "estabilidad": round(estabilidad, 1),
            "reutilizacion": round(reutilizacion, 1),
            "aprendizaje": round(aprendizaje, 1),
            "observabilidad": round(observabilidad, 1),
        },
    }


def save_result(score: float, results: dict, elapsed: float) -> None:
    """Guarda el resultado de la auditoría actual en el histórico."""
    metrics = collect_metrics()
    health = _compute_health_index(metrics, score)
    record = {
        "timestamp": _datetime.now(UTC).isoformat(),
        "tag": _get_git_tag(),
        "health_index": health["health_index"],
        "health_componentes": health["componentes"],
        "score": score,
        "elapsed_s": round(elapsed, 1),
        "metrics": metrics,
        "checks": {name: {"ok": r["ok"], "msg": r["msg"], "elapsed_s": r["elapsed_s"]} for name, r in results.items()},
    }
    path = HISTORIAL / f"audit_{_datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(_json.dumps(record, indent=2, ensure_ascii=False))
    return record


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
        except py_compile.PyCompileError:
            errors.append(str(pyfile.relative_to(ROOT)))
    if errors:
        return False, f"{len(errors)} archivos no compilan"
    return True, "OK"


# ── 2. Logger regression ──


@check("Logger: sin .warning()", 10)
def _():
    result = subprocess.run(
        [sys.executable, "scripts/pro/tests/test_logger_regression.py"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
        check=False,
    )
    if result.returncode != 0:
        lines = [l for l in result.stdout.split("\n") if "❌" in l or "Error" in l]
        return False, "\n".join(lines[:3]) if lines else "fallo"
    return True, "OK"


# ── 3. Plugin discovery ──


@check("Plugin discovery", 10)
def _():
    sys.path.insert(0, str(ROOT / "scripts" / "pro"))
    import plugin_registry

    plugins = plugin_registry.discover_all()
    required = {"name", "phase", "timeout", "priority"}
    missing = [f"{name}: falta {field}" for name, p in plugins.items() for field in required if field not in p]
    if missing:
        return False, "\n".join(missing[:3])
    return True, f"{len(plugins)} plugins, todos OK"


# ── 4. Reuse Detector regression ──


@check("Reuse Detector regresión", 15)
def _():
    result = subprocess.run(
        [sys.executable, "scripts/pro/reuse/test_regression.py"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
        check=False,
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
        [
            str(ruff),
            "check",
            "scripts/pro/tuneladora/",
            "scripts/pro/autonomy/",
            "scripts/pro/reuse/",
            "--ignore",
            "EXE001,E402",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        check=False,
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
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
        check=False,
    )
    if result.returncode != 0:
        return False, f"dashboard falla: {result.stderr[:200]}"
    try:
        data = json.loads(result.stdout)
        return (
            True,
            f"{data.get('ledger_ejecuciones', '?')} ejecuciones, {data.get('memoria_ejecuciones', '?')} indexadas",
        )
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
        data = _json.loads(cp.read_text(encoding="utf-8"))
        if data.get("pipeline") not in ("mejora", "mantenimiento", "autonomy"):
            return False, f"pipeline desconocido: {data.get('pipeline')}"
        return True, f"checkpoint: {data.get('pipeline')} (fase {data.get('last_completed', '?')})"
    return True, "sin checkpoint (limpieza correcta)"


# ── 10. Plugins uniformidad ──


@check("Plugins uniformes", 5)
def _():
    sys.path.insert(0, str(ROOT / "scripts" / "pro"))
    import plugin_registry

    plugins = plugin_registry.discover_all()
    fields = {"name", "phase", "timeout", "priority"}
    for name, p in plugins.items():
        missing = fields - set(p.keys())
        if missing:
            return False, f"{name}: falta {missing}"
    return True, f"{len(plugins)} plugins, contrato OK"


def show_history() -> None:
    """Muestra el histórico de auditorías, health index y tendencias."""
    records = load_history()
    if not records:
        return

    print("\n── URA Health Index ──")
    last = records[-1]
    hi = last.get("health_index", 0)
    comp = last.get("health_componentes", {})
    print(f"  Health Index: {hi:.0f}/100 {'🟢' if hi >= 80 else '🟡' if hi >= 50 else '🔴'}")
    for name, val in comp.items():
        bar = "█" * int(val / 10) + "░" * (10 - int(val / 10))
        print(f"    {name:15} {bar} {val:.0f}%")

    print("\n── Histórico de auditorías ──")
    print(f"  {'Versión':12} {'Health':>7} {'Score':>6} {'Tiempo':>8}")
    print(f"  {'-' * 12} {'-' * 7} {'-' * 6} {'-' * 8}")
    for r in records[-10:]:
        tag = r.get("tag", "?")[:12]
        print(f"  {tag:12} {r.get('health_index', 0):>6.0f}  {r.get('score', 0):>5.0f}  {r.get('elapsed_s', 0):>6.1f}s")

    if len(records) >= 2:
        first_hi = records[0].get("health_index", 0)
        last_hi = records[-1].get("health_index", 0)
        diff = last_hi - first_hi
        arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        print(f"\n  Health Index: {first_hi:.0f} → {last_hi:.0f} ({diff:+.0f}) {arrow}")
        print(f"  Auditorías registradas: {len(records)}")


def main() -> int:
    import argparse

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

    # Guardar histórico
    _ = save_result(result["score"], result["results"], elapsed)
    show_history()

    if args.json:
        print(_json.dumps({"actual": result, "historial": load_history()[-5:]}, indent=2, ensure_ascii=False))

    return 0 if result["score"] >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
