#!/usr/bin/env python3
"""Rodillo 8 — Certificador URA. Emite Sello de Calidad."""

import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, UTC

REPO = Path(os.environ.get("REPO_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
SEAL_DIR = REPO / "docs" / "sellos"
SEAL_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def check(name, fn):
    ok, out = fn()
    return name, {"ok": ok, "detalle": out[:200]}


checks = [
    check(
        "ruff (estilo)",
        lambda: (
            r := run(["ruff", "check", ".", "--statistics"]),
            r.returncode == 0,
            r.stdout.strip(),
        )[1:],
    ),
    check(
        "pytest (tests)",
        lambda: (
            r := run(["pytest", "--quiet", "--ignore=scripts/GX10", "--ignore=quarantine"]),
            r.returncode == 0,
            r.stdout.strip(),
        )[1:],
    ),
    check(
        "bandit (seguridad)",
        lambda: (
            r := run(["bandit", "-r", ".", "-f", "txt", "-ll"]),
            r.returncode == 0,
            r.stdout.strip(),
        )[1:],
    ),
]

resultados = dict(checks)
aprobado = all(v["ok"] for v in resultados.values())
sello = {
    "proyecto": "URA",
    "fecha": datetime.now(UTC).isoformat(),
    "aprobado": aprobado,
    "resultados": resultados,
    "version": "1.0",
}
f = SEAL_DIR / f"sello_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
f.write_text(json.dumps(sello, indent=2))
print(f"{'✅ CERTIFICADO' if aprobado else '🔴 NO CERTIFICADO'} — {f}")
sys.exit(0 if aprobado else 1)
