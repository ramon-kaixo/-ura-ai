#!/usr/bin/env python3
"""orquestador_check.py — Chequeo read-only de pendientes para el rol Orquestador.

Lista: (1) planes en docs/udo/plans/ sin TASK asociada ni estado TERMINADA,
(2) lotes de docs/udo/review-pending.md con TASKs aún sin veredicto del revisor,
(3) hallazgos de docs/udo/hallazgos-fondo.md en estado "propuesto",
(4) TASKs UDO activas/atascadas (IN_PROGRESS antiguas).

Uso:
    python3 scripts/pro/orquestador_check.py            # lista pendientes
    python3 scripts/pro/orquestador_check.py --notify   # + aviso Telegram (notifier)

Exit code: 0 = sin pendientes · 1 = hay pendientes (para cron/gates).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "docs" / "udo" / "plans"
REVIEW = ROOT / "docs" / "udo" / "review-pending.md"
HALLAZGOS = ROOT / "docs" / "udo" / "hallazgos-fondo.md"
TASKS_DIR = ROOT / "docs" / "udo" / "tasks"


def find_plans_pendientes() -> list[str]:
    """Planes sin TASK asociada y sin estado TERMINADA."""
    pendientes: list[str] = []
    for f in sorted(PLANS.glob("PLAN-*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        has_task = re.search(r"TASK-\d{8}-\d{3}", text) is not None
        done = re.search(r"TERMINADA|REVISADA", text) is not None
        if not has_task or not done:
            pendientes.append(f"PLAN sin ejecutar/cerrar: {f.relative_to(ROOT)}")
    return pendientes


def find_review_pendientes() -> list[str]:
    """Filas de tabla del review-pending sin veredicto (sin 'REVISADA')."""
    if not REVIEW.exists():
        return []
    pendientes: list[str] = []
    revisado = re.compile(r"REVISADA|APROBADA|RECHAZADA")
    for line in REVIEW.read_text(encoding="utf-8", errors="replace").splitlines():
        if "TASK-" in line and "|" in line and not revisado.search(line):
            task_id = re.search(r"TASK-\d{8}-\d{3}", line)
            if task_id and "Estado revisión" not in line:
                pendientes.append(f"Revisión sin veredicto: {task_id.group(0)}")
    return pendientes


def find_hallazgos_propuestos() -> list[str]:
    """Hallazgos en estado 'propuesto' (con plan pero sin decidir)."""
    if not HALLAZGOS.exists():
        return []
    pendientes: list[str] = []
    for line in HALLAZGOS.read_text(encoding="utf-8", errors="replace").splitlines():
        if "propuesto" in line.lower() and "|" in line:
            m = re.search(r"\|([^|]+\.py:\d+)\|", line)
            if m:
                pendientes.append(f"Hallazgo propuesto: docs/udo/hallazgos-fondo.md ({m.group(1).strip()})")
    return pendientes


def find_tasks_atascadas(days: int = 3) -> list[str]:
    """TASKs cuyo estado ACTUAL es IN_PROGRESS/PLANNED con más de `days` días."""
    pendientes: list[str] = []
    for f in sorted(TASKS_DIR.glob("TASK-*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        m_estado = re.search(r"^estado:\s*(\S+)", text, re.MULTILINE)
        if not m_estado or m_estado.group(1) not in {"IN_PROGRESS", "PLANNED"}:
            continue
        m = re.search(r"TASK-(\d{8})-(\d{3})", f.name)
        if not m:
            continue
        created = datetime.strptime(m.group(1), "%Y%m%d")
        if (datetime.now() - created).days >= days:
            pendientes.append(
                f"TASK {m_estado.group(1)} atascada ({created.date()}): {f.stem}"
            )
    return pendientes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notify", action="store_true", help="enviar aviso Telegram si hay pendientes")
    parser.add_argument("--max-days", type=int, default=3, help="antigüedad TASK atascada (días)")
    args = parser.parse_args()

    pendientes = (
        find_plans_pendientes()
        + find_review_pendientes()
        + find_hallazgos_propuestos()
        + find_tasks_atascadas(args.max_days)
    )

    if not pendientes:
        print("OK: sin pendientes.")
        return 0

    print(f"{len(pendientes)} pendiente(s):")
    for item in pendientes:
        print(f"  - {item}")

    if args.notify:
        try:
            sys.path.insert(0, str(ROOT))
            from core.notifier import notify  # type: ignore[import-not-found]
            msg = "".join(f"\n- {p}" for p in pendientes)
            ok = notify(f"Orquestador: {len(pendientes)} pendiente(s):{msg}")
            print(f"Notificación enviada: {ok}")
        except Exception as exc:  # noqa: BLE001 — degradación controlada
            print(f"Aviso: notificación no disponible ({exc}); pendientes escritos arriba.")
    return 1


if __name__ == "__main__":
    sys.exit(main())