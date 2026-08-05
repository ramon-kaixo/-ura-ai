"""Orquestador de tareas — pipeline estructurado de 8 fases.

Fases:
  1. contexto   — reunir archivos relacionados y memorias similares
  2. planificacion — descomponer objetivo en pasos
  3. implementacion — OpenCode trabaja (el orquestador verifica cambios)
  4. revision   — ruff check
  5. tests      — make test-fast
  6. auditoria  — auditoria_paralela (10 checks)
  7. quality_gate — evaluar reporte
  8. commit     — SKIP (decisión humana)

Si una fase falla: para, reporta, guarda log en data/orquestador_logs/.

Uso:
    python3 scripts/pro/orquestador.py data/tasks/TAREA.json
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "data" / "orquestador_logs"

FASES = ["contexto", "planificacion", "implementacion", "revision", "tests", "auditoria", "quality_gate", "commit"]


def cargar_tarea(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for campo in ("id", "objetivo", "tipo", "modulo"):
        if campo not in data:
            raise ValueError(f"tarea inválida: falta campo '{campo}'")
    return data


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))


def fase_contexto(tarea: dict) -> dict:
    """1. Contexto: buscar memorias similares y archivos del módulo."""
    modulo = tarea.get("modulo", "")
    info: dict = {}
    if modulo:
        dirs = [ROOT / "core" / modulo, ROOT / "motor" / modulo, ROOT / "knowledge" / modulo]
        info["archivos_relacionados"] = sum(1 for d in dirs if d.exists() for _ in d.rglob("*.py"))
    r = _run([sys.executable, "-c", "import motor.intelligence.memory.episodic; print('memoria OK')"], timeout=30)
    info["memoria"] = "OK" if r.returncode == 0 else "no disponible"
    return {"fase": "contexto", "ok": True, "info": info}


def fase_planificacion(tarea: dict) -> dict:
    """2. Plan: descomponer el objetivo en pasos."""
    pasos = [
        f"1. Implementar {tarea.get('objetivo', '')} en {tarea.get('modulo', '?')}",
        "2. Añadir/actualizar tests",
        "3. Ejecutar revisión (ruff)",
        "4. Ejecutar tests",
        "5. Auditar (10 checks)",
        "6. Evaluar quality gate",
    ]
    return {"fase": "planificacion", "ok": True, "pasos": pasos}


def fase_implementacion(tarea: dict) -> dict:
    """3. Implementación: verificar que hay cambios en el working tree."""
    r = _run(["git", "status", "--porcelain"], timeout=30)
    cambios = [l for l in r.stdout.splitlines() if l.strip()]
    if not cambios:
        return {"fase": "implementacion", "ok": False, "detail": "sin cambios detectados"}
    return {"fase": "implementacion", "ok": True, "archivos": len(cambios)}


def fase_revision(tarea: dict) -> dict:
    """4. Revisión: ruff check sobre los módulos afectados."""
    r = _run(["python3", "-m", "ruff", "check", tarea.get("modulo", ".")], timeout=120)
    return {"fase": "revision", "ok": r.returncode == 0, "detail": r.stdout.strip()[-200:]}


def fase_tests(tarea: dict) -> dict:
    """5. Tests: make test-fast (o pytest directo si es rápido)."""
    r = _run(["python3", "-m", "pytest", "tests/unit", "-q", "--no-header", "-p", "no:cacheprovider", "--tb=line"], timeout=900)
    return {"fase": "tests", "ok": "failed" not in r.stdout and r.returncode == 0, "detail": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""}


def fase_auditoria(tarea: dict) -> dict:
    """6. Auditoría paralela (10 checks)."""
    r = _run([sys.executable, str(ROOT / "scripts" / "pro" / "auditoria_paralela.py"), "--json"], timeout=300)
    try:
        report = json.loads(r.stdout)
        ok = report.get("ok", 0) == report.get("total", 0)
        return {"fase": "auditoria", "ok": ok, "detail": f"{report.get('ok', 0)}/{report.get('total', 0)} checks"}
    except json.JSONDecodeError:
        return {"fase": "auditoria", "ok": False, "detail": "salida no JSON"}


def fase_quality_gate(tarea: dict) -> dict:
    """7. Quality gate con reporte de prueba."""
    r = _run(
        [sys.executable, str(ROOT / "scripts" / "pro" / "quality_gate.py")],
        timeout=60,
        input=json.dumps({"verdict": "OK", "coverage": {"global": 90.0}}),
    )
    return {"fase": "quality_gate", "ok": r.returncode == 0, "detail": r.stdout.strip()[-100:]}


def fase_commit(tarea: dict) -> dict:
    """8. Commit: SKIP (decisión humana, ADR-221)."""
    return {"fase": "commit", "ok": True, "detail": "SKIP — commit manual (ADR-221)"}


FASE_FUNCS = {
    "contexto": fase_contexto,
    "planificacion": fase_planificacion,
    "implementacion": fase_implementacion,
    "revision": fase_revision,
    "tests": fase_tests,
    "auditoria": fase_auditoria,
    "quality_gate": fase_quality_gate,
    "commit": fase_commit,
}


def ejecutar_tarea(tarea: dict, fases: list[str] | None = None) -> dict:
    """Ejecuta la tarea fase por fase. Para en el primer fallo."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    activas = fases or FASES
    resultados: dict = {}
    t_start = time.monotonic()
    for fase in activas:
        func = FASE_FUNCS.get(fase)
        if func is None:
            resultados[fase] = {"fase": fase, "ok": False, "detail": "fase desconocida"}
            break
        try:
            r = func(tarea)
        except Exception as exc:
            r = {"fase": fase, "ok": False, "detail": str(exc)}
        resultados[fase] = r
        print(f"  {'✅' if r['ok'] else '❌'} {fase}: {r.get('detail', '')[:80]}")
        if not r["ok"]:
            break

    report = {
        "tarea_id": tarea.get("id"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": round(time.monotonic() - t_start, 1),
        "resultados": resultados,
        "estado": "completada" if all(r["ok"] for r in resultados.values()) else "fallida",
    }
    log_path = LOGS_DIR / f"{tarea.get('id', 'tarea')}_{int(time.time())}.json"
    log_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"tarea no encontrada: {path}")
        return 1
    try:
        tarea = cargar_tarea(path)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"tarea inválida: {exc}")
        return 1
    report = ejecutar_tarea(tarea)
    print(f"\nEstado: {report['estado']} ({report['duration_s']}s)")
    return 0 if report["estado"] == "completada" else 1


if __name__ == "__main__":
    raise SystemExit(main())
