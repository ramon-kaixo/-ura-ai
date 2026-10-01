#!/usr/bin/env python3
"""capturar_evidencias.py — registra evidencias objetivas del proyecto.

Guarda en data/evidencias/<timestamp>.json:
  - tests: totales, errores de collection
  - complejidad: promedio radon, violaciones xenon
  - git: commit actual, rama
  - auditoria_paralela: resultado de los 10 checks

Uso: python3 scripts/pro/capturar_evidencias.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EVIDENCIAS_DIR = ROOT / "data" / "evidencias"


def _run(cmd: list[str], timeout: int = 300) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))  # noqa: PLW1510 — legacy/estable, sin cambio de comportamiento
        return r.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"error: {exc}"


def recoger_evidencias() -> dict:
    evidencias: dict = {}

    # Tests: colección
    out = _run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"]
    )
    import re

    m = re.search(r"(\d+) tests collected", out)
    evidencias["tests_totales"] = int(m.group(1)) if m else -1
    evidencias["tests_errores_collection"] = len([l for l in out.splitlines() if l.startswith("ERROR")])

    # Complejidad
    radon = _run([sys.executable, "-m", "radon", "cc", "core/", "motor/", "knowledge/"])
    rank_counts: dict[str, int] = {}
    for line in radon.splitlines():
        parts = line.split()
        if parts and parts[-1] in ("A", "B", "C", "D", "E", "F"):
            rank_counts[parts[-1]] = rank_counts.get(parts[-1], 0) + 1
    evidencias["complejidad"] = rank_counts
    avg_line = [l for l in radon.splitlines() if "Average complexity" in l]
    evidencias["complejidad_promedio"] = avg_line[-1] if avg_line else "?"

    # Git
    evidencias["git_commit"] = _run(["git", "rev-parse", "--short", "HEAD"], timeout=10).strip()
    evidencias["git_rama"] = _run(["git", "branch", "--show-current"], timeout=10).strip()
    dirty = _run(["git", "status", "--porcelain"], timeout=10)
    evidencias["git_sin_commit"] = len([l for l in dirty.splitlines() if l.strip()])

    # Auditoría paralela
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "pro"))
        from auditoria_paralela import run_all as audit_run

        audit = audit_run()
        evidencias["auditoria_paralela"] = {"ok": audit["ok"], "total": audit["total"]}
    except Exception as exc:
        evidencias["auditoria_paralela"] = {"error": str(exc)}

    evidencias["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return evidencias


def main() -> int:
    EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    data = recoger_evidencias()
    path = EVIDENCIAS_DIR / f"evidencia_{int(time.time())}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Evidencias guardadas en {path}")
    print(json.dumps({k: v for k, v in data.items() if k != "timestamp"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
