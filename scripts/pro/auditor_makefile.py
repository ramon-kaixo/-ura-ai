"""auditor_makefile.py — Auditoría de targets del Makefile (Fase 1 adaptada).

Ejecuta cada target con timeout 30s y registra OK / FAIL / TIMEOUT / SKIP.
Los targets destructivos o muy lentos se marcan MANUAL (no se ejecutan).

Salida: docs/auditoria_makefile.md
Uso: python3 scripts/pro/auditor_makefile.py
"""
from __future__ import annotations

import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
OUT = REPO_ROOT / "docs" / "auditoria_makefile.md"

# Targets que NO se ejecutan automáticamente (destructivos, lentos o con efectos colaterales)
MANUAL_TARGETS = {
    "backup", "cleanup", "clean", "server-stop", "server-start", "reindex",
    "router-audit", "chaos", "hardening", "validate-full", "test-slow",
    "test-full", "fix", "dashboard", "audit-docs",
}


def _targets() -> list[str]:
    text = MAKEFILE.read_text()
    return [
        m for m in re.findall(r"^([a-zA-Z][a-zA-Z0-9-]*):", text, re.M)
        if not m.startswith((".", "/"))
    ]


def _run(target: str) -> tuple[str, str]:
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            ["make", target],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        elapsed = time.monotonic() - t0
        if r.returncode == 0:
            return "OK", f"{elapsed:.0f}s"
        detalle = (r.stdout + r.stderr).strip().splitlines()[-3:]
        return "FAIL", f"{elapsed:.0f}s | " + " | ".join(detalle)[:200]
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ">30s"


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    for target in _targets():
        if target in MANUAL_TARGETS:
            rows.append((target, "MANUAL", "no ejecutado (destructivo/lento)"))
            continue
        estado, detalle = _run(target)
        rows.append((target, estado, detalle))
        print(f"  {target}: {estado}", flush=True)

    md = [f"# Auditoría Makefile — {datetime.now(UTC).isoformat()}", ""]
    md.append("| Target | Estado | Detalle |")
    md.append("|---|---|---|")
    for target, estado, detalle in rows:
        md.append(f"| {target} | {estado} | {detalle} |")
    OUT.write_text("\n".join(md) + "\n")
    print(f"Output: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
