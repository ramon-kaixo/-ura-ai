#!/usr/bin/env python3
"""mutmut_daily — Barrido diario progresivo de mutation testing (PLAN v5).

Ejecutado por systemd timer a las 06:00. Selecciona el lote del día por
rotación semanal, ejecuta mutmut sobre ese lote con HYPOTHESIS_PROFILE=ci,
genera un reporte markdown en docs/udo/mutation-reports/ y crea una TASK
UDO para que OpenCode Terminal la revise.

Sin fricción: no toca hooks de git, no muta en el working tree (mutmut usa
una copia de trabajo propia en .mutmut-cache/). El fallo del lote se
registra (exit code) y la TASK queda BLOCKED.

Uso: scripts/pro/mutmut_daily.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from datetime import UTC
from pathlib import Path

REPO = Path("/home/ramon/URA/ura_ia_1972")
VENV_BIN = REPO / ".venv" / "bin"
MUTMUT = VENV_BIN / "mutmut"
REPORT_DIR = REPO / "docs" / "udo" / "mutation-reports"

# Lotes equilibrados por tamaño de código (motor/core: 105, motor/intelligence: 36,
# core: 125, knowledge: 88 — en realidad motor/core tiene ~105 y core ~125, se reparte
# para que cada día dure < 1-2h con mutmut).
BATCHES: list[list[str]] = [
    ["motor/core/"],
    ["core/"],
    ["knowledge/", "motor/intelligence/"],
    ["motor/assistant/", "motor/observability/", "motor/scanner/"],
    ["motor/agents/", "motor/brain/", "motor/memory/", "motor/events/", "motor/cli/"],
]


def _lote_del_dia() -> tuple[int, list[str]]:
    """Índice por día de la semana (0=lunes..6=domingo) → lote rotativo."""
    idx = datetime.datetime.now(UTC).date().weekday() % len(BATCHES)
    return idx, BATCHES[idx]


def _ejecutar_mutmut(lote: list[str], dry: bool) -> int:
    cmd = [str(MUTMUT), "run", *lote]
    if dry:
        print("[dry-run] mutmut:", " ".join(cmd))
        return 0
    env = dict(os.environ)
    env["HYPOTHESIS_PROFILE"] = "ci"
    print("Ejecutando:", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(REPO), env=env, check=False).returncode


def _reporte_mutmut() -> str:
    res = subprocess.run(
        [str(MUTMUT), "results"], capture_output=True, text=True, cwd=str(REPO), check=False
    )
    return res.stdout if res.returncode == 0 else f"(mutmut results falló: {res.stderr})"


def _crear_task_udo(reporte_path: Path, lote: list[str], exit_code: int, dry: bool) -> str:
    """Crea una TASK UDO con el resumen del lote para que TERM la revise."""
    estado = "BLOCKED" if exit_code != 0 else "PLANNED"
    desc = f"Revisar reporte mutmut {lote[0] if len(lote) == 1 else 'lote combinado'} ({reporte_path.name})"
    if dry:
        print(f"[dry-run] ura-udo create: {desc} | estado={estado}")
        return "TASK-dry-run"
    cmd = [str(REPO / "scripts" / "pro" / "ura-udo"), "create", desc]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), check=False).stdout
    task_id = next(
        (tok for tok in out.split() if tok.startswith("TASK-")), "TASK-?"
    )
    # Registra el estado inicial (BLOCKED si el lote falló) con nota del reporte
    subprocess.run(
        [
            str(REPO / "scripts" / "pro" / "ura-udo"),
            "update", task_id,
            "--estado", estado,
            "--nota", f"Reporte mutmut: {reporte_path.name} (exit={exit_code})",
        ],
        capture_output=True, text=True, cwd=str(REPO), check=False,
    )
    return task_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    idx, lote = _lote_del_dia()
    date_str = datetime.datetime.now(UTC).date().isoformat()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lote_name = "+".join(p.rstrip("/").replace("/", "_") for p in lote)
    reporte_path = REPORT_DIR / f"{date_str}_{lote_name}.md"

    # Lote ya cubierto hoy (idempotente): no re-ejecutar
    if reporte_path.exists() and not args.dry_run:
        print(f"Lote ya ejecutado hoy: {reporte_path.name}")
        return 0

    print(f"== Barrido mutmut {date_str} — lote {idx}: {', '.join(lote)}")
    exit_code = _ejecutar_mutmut(lote, args.dry_run)

    reporte = _reporte_mutmut() if not args.dry_run else "(reporte en dry-run)"
    reporte_path.write_text(
        f"# Reporte mutmut {date_str} — {lote_name}\n\n"
        f"**Lote**: {', '.join(lote)} · **Exit code**: {exit_code}\n\n"
        f"```\n{reporte}\n```\n"
    )
    print(f"Reporte: {reporte_path}")

    task = _crear_task_udo(reporte_path, lote, exit_code, args.dry_run)
    print(f"TASK UDO: {task}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
