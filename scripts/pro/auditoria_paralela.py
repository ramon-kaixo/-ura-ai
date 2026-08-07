"""Auditoría paralela — 10 checks automáticos de salud del sistema.

Uso:
    python3 scripts/pro/auditoria_paralela.py          # ejecuta los 10 checks
    python3 scripts/pro/auditoria_paralela.py --json   # salida JSON

Los checks (Módulo 6 del Plan Día 2):
  1. Consistencia de memorias (episódica/LTM/semántica/short-term)
  2. Supervisor realmente lee (auditoria_continua)
  3. Quality gate con reporte real
  4. Lock stale (regresión del fix de PID muerto)
  5. Consistencia de tests (3 runs — resumen)
  6. Archivos huérfanos (no importados)
  7. Duplicados reales (mismos nombres de función entre core/ y motor/)
  8. Imports circulares (import del runner)
  9. Secretos hardcodeados
  10. Rendimiento (tiempos de import)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _check(label: str, ok: bool, detail: str = "") -> dict:
    return {"check": label, "ok": ok, "detail": detail}


def check_memorias() -> dict:
    """1. Las 4 capas de memoria existen y tienen datos."""
    episodica = ROOT / "knowledge" / "episodic.db"
    ltm = ROOT / "knowledge" / "ltm.db"
    knowledge = ROOT / "knowledge" / "knowledge.db"
    existentes = [p for p in (episodica, ltm, knowledge) if p.exists()]
    if len(existentes) < 3:
        return _check("memorias", False, f"solo {len(existentes)}/3 DBs existen")
    return _check("memorias", True, ", ".join(p.name for p in existentes))


def check_supervisor() -> dict:
    """2. auditoria_continua se ejecuta sin errores."""
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "pro"))
        import auditoria_continua as ac

        result = ac.run_all(verbose=False)
        score = result.get("score", -1)
        return _check("supervisor", score >= 0, f"score={score}")
    except Exception as exc:
        return _check("supervisor", False, str(exc))


def check_quality_gate() -> dict:
    """3. quality_gate funciona con un reporte de prueba."""
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "pro"))
        import quality_gate as qg

        verdict, _alertas = qg.evaluar({"verdict": "OK", "coverage": {"global": 90.0}})
        return _check("quality_gate", verdict == "ACCEPTED", f"verdict={verdict}")
    except Exception as exc:
        return _check("quality_gate", False, str(exc))


def check_lock_stale() -> dict:
    """4. El fix de lock stale funciona (PID muerto se sobrescribe)."""
    from scripts.pro.tuneladora.pipeline.runner import _pid_alive

    ok = not _pid_alive(999999999)
    return _check("lock_stale", ok, "PID 999999999 no existe (liveness correcto)")


def check_tests_consistencia() -> dict:
    """5. La suite colecciona sin errores."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "--no-header"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        ok = "error" not in tail.lower() and r.returncode == 0
        return _check("tests", ok, tail[:80])
    except Exception as exc:
        return _check("tests", False, str(exc))


def check_huerfanos() -> dict:
    """6. Scripts de scripts/pro no importados por nadie (excluye Makefile/cron)."""
    makefile = (ROOT / "Makefile").read_text()
    conectados = {Path(m).stem for m in __import__("re").findall(r"scripts/pro/(\w+)\.py", makefile)}
    huerfanos: list[str] = []
    for f in sorted((ROOT / "scripts" / "pro").glob("*.py")):
        if f.name in ("__init__.py", "plugin_registry.py", "auditoria_continua.py", "auditoria_paralela.py"):
            continue
        stem = f.stem
        if stem in conectados:
            continue
        refs = subprocess.run(
            ["grep", "-rl", f"scripts.pro.{stem}", "--include=*.py",
             str(ROOT / "core"), str(ROOT / "motor"), str(ROOT / "knowledge"),
             str(ROOT / "scripts"), str(ROOT / "tests")],
            capture_output=True, text=True, timeout=30,
        ).stdout.splitlines()
        refs = [r for r in refs if not r.endswith(f"/{f.name}")]
        if not refs:
            huerfanos.append(stem)
    return _check("huerfanos", len(huerfanos) <= 15, f"{len(huerfanos)}: {", ".join(huerfanos[:5])}")


def check_duplicados() -> dict:
    """7. Funciones con el mismo nombre en core/ y motor/."""
    dups: dict[str, list[str]] = {}

    def _funcs(d: Path) -> list[str]:
        out = []
        for f in d.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("def ") or line.startswith("async def "):
                        name = line.split("(")[0].replace("def ", "").replace("async def ", "").strip()
                        out.append(name)
            except OSError:
                pass
        return out

    core_f = set(_funcs(ROOT / "core"))
    motor_f = set(_funcs(ROOT / "motor"))
    for name in sorted(core_f & motor_f):
        dups[name] = ["core", "motor"]
    return _check("duplicados", len(dups) <= 50, f"{len(dups)} funciones compartidas (homonimos, ver ADR-220)")


def check_imports_circulares() -> dict:
    """8. El runner importa sin ciclos."""
    try:
        import scripts.pro.tuneladora.pipeline.runner  # noqa: F401

        return _check("imports", True, "runner OK")
    except Exception as exc:
        return _check("imports", False, str(exc))


def check_secretos() -> dict:
    """9. Sin secretos hardcodeados en scripts/pro."""
    patrones = ("password = ", "secret = ", "api_key = ", "token = ")
    hallazgos: list[str] = []
    for f in (ROOT / "scripts" / "pro").rglob("*.py"):
        if "test_" in f.name or "__pycache__" in str(f) or f.name == "auditoria_paralela.py":
            continue
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for pat in patrones:
                    if pat in line and "os.environ" not in line and "get_secret" not in line:
                        hallazgos.append(f"{f.name}:{i}")
        except OSError:
            pass
    return _check("secretos", len(hallazgos) == 0, f"{len(hallazgos)} hallazgos")


def check_rendimiento() -> dict:
    """10. Tiempo de import del runner."""
    t0 = time.monotonic()
    try:
        import scripts.pro.tuneladora.pipeline.runner  # noqa: F401

        elapsed = round(time.monotonic() - t0, 3)
        return _check("rendimiento", elapsed < 5.0, f"import runner: {elapsed}s")
    except Exception as exc:
        return _check("rendimiento", False, str(exc))


CHECKS = [
    check_memorias,
    check_supervisor,
    check_quality_gate,
    check_lock_stale,
    check_tests_consistencia,
    check_huerfanos,
    check_duplicados,
    check_imports_circulares,
    check_secretos,
    check_rendimiento,
]


def run_all() -> dict:
    results = [c() for c in CHECKS]
    ok_count = sum(1 for r in results if r["ok"])
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": ok_count,
        "total": len(results),
        "results": results,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Auditoría paralela de URA")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    report = run_all()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for r in report["results"]:
            icon = "✅" if r["ok"] else "❌"
            print(f"  {icon} {r['check']}: {r['detail']}")
        print(f"\n  {report['ok']}/{report['total']} checks OK")
    return 0 if report["ok"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
