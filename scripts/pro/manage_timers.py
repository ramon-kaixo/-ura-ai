#!/usr/bin/env python3
"""manage_timers.py — gestiona los timers systemd de URA.

Los timers automatizan los scripts manuales del Makefile (Módulo 7).
Requiere sudo para instalar en /etc/systemd/system (rootfs RO en GX10 —
ejecutar con permisos elevados o desplegar las unidades manualmente).

Uso:
    python3 scripts/pro/manage_timers.py status   # estado de cada timer
    python3 scripts/pro/manage_timers.py install  # instala unidades (sudo)
    python3 scripts/pro/manage_timers.py start    # enable --now todos
    python3 scripts/pro/manage_timers.py stop     # stop todos
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
UNITS_DIR = ROOT / "deploy" / "timers"

# nombre -> (script, frecuencia, descripción)
TIMERS: dict[str, tuple[str, str, str]] = {
    "ura-fix": ("scripts/pro/sanear_codigo.py", "daily", "make fix — auto-fix de ruff"),
    "ura-backup": ("scripts/pro/backup_assistant.py", "daily", "backup del repo"),
    "ura-reindex": ("scripts/pro/reindex_vectors.py", "weekly", "reindexado vectorial"),
    "ura-audit-extra": ("scripts/pro/auditoria_paralela.py", "weekly", "auditoría paralela"),
    "ura-harden": ("scripts/pro/hardening_audit.py", "weekly", "auditoría de hardening"),
    "ura-consolidate": ("scripts/pro/consolidacion.py", "weekly", "consolidación de código"),
    "ura-cleanup-auto": ("scripts/pro/cleanup_assistant.py", "6h", "limpieza asistente"),
    "ura-chaos": ("scripts/pro/chaos_test.py", "monthly", "chaos engineering"),
    "ura-dashboard": ("scripts/pro/dashboard.py", "permanent", "dashboard web"),
}


def _unit_paths(name: str) -> tuple[Path, Path]:
    return UNITS_DIR / f"{name}.timer", UNITS_DIR / f"{name}.service"


def _frecuencia_on_calendar(frecuencia: str) -> str:
    return {
        "daily": "*-*-* 04:00:00",
        "weekly": "*-*-* 05:00:00",
        "6h": "*:0/6",
        "monthly": "*-*-01 06:00:00",
    }.get(frecuencia, "*-*-* 04:00:00")


def generar_unidades(verbose: bool = True) -> list[Path]:
    """Genera los archivos .timer/.service en deploy/timers/."""
    UNITS_DIR.mkdir(parents=True, exist_ok=True)
    generados: list[Path] = []
    for name, (script, frecuencia, desc) in TIMERS.items():
        if frecuencia == "permanent":
            continue
        timer = UNITS_DIR / f"{name}.timer"
        timer.write_text(
            f"[Unit]\nDescription={desc}\n\n"
            f"[Timer]\nOnCalendar={_frecuencia_on_calendar(frecuencia)}\n"
            f"Persistent=true\n\n[Install]\nWantedBy=timers.target\n",
        )
        service = UNITS_DIR / f"{name}.service"
        service.write_text(
            f"[Unit]\nDescription={desc}\n\n"
            f"[Service]\nType=oneshot\nUser=ramon\n"
            f"ExecStart=/home/ramon/URA/ura_ia_1972/.venv/bin/python3 "
            f"/home/ramon/URA/ura_ia_1972/{script}\n"
            f"Nice=10\n",
        )
        generados.extend([timer, service])
        if verbose:
            print(f"  generado: {timer.name} ({frecuencia})")
    return generados


def _run(cmd: list[str]) -> int:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # noqa: PLW1510 — legacy/estable, sin cambio de comportamiento
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0 and r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)
        return r.returncode
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def status() -> int:
    print("Estado de timers URA:")
    for name in TIMERS:
        if TIMERS[name][1] == "permanent":
            continue
        r = subprocess.run(  # noqa: PLW1510 — legacy/estable, sin cambio de comportamiento
            ["systemctl", "is-active", f"{name}.timer"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        estado = r.stdout.strip() or "inactive"
        print(f"  {name}.timer: {estado}")
    return 0


def install() -> int:
    """Instala las unidades en /etc/systemd/system (requiere sudo)."""
    generados = generar_unidades(verbose=True)
    if _run(["sudo", "-n", "true"]) != 0:
        print("Se requiere sudo (password) — las unidades quedan en deploy/timers/")
        print("Instalación manual:")
        print(f"  sudo cp {UNITS_DIR}/*.timer {UNITS_DIR}/*.service /etc/systemd/system/")
        print("  sudo systemctl daemon-reload")
        return 1
    for unit in generados:
        _run(["sudo", "cp", str(unit), "/etc/systemd/system/"])
    _run(["sudo", "systemctl", "daemon-reload"])
    return 0


def start() -> int:
    rc = 0
    for name in TIMERS:
        if TIMERS[name][1] == "permanent":
            continue
        if _run(["sudo", "-n", "systemctl", "enable", "--now", f"{name}.timer"]) != 0:
            rc = 1
    return rc


def stop() -> int:
    rc = 0
    for name in TIMERS:
        if TIMERS[name][1] == "permanent":
            continue
        if _run(["sudo", "-n", "systemctl", "stop", f"{name}.timer"]) != 0:
            rc = 1
    return rc


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "install", "start", "stop", "generate"):
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "generate":
        generar_unidades()
        return 0
    return {"status": status, "install": install, "start": start, "stop": stop}[cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
