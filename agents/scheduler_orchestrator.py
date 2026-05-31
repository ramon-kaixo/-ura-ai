#!/usr/bin/env python3
"""
scheduler_orchestrator.py — Orquestador proactivo de tareas programadas
======================================================================
Resuelve conflictos en crontab automáticamente: detecta tareas que se solapan
en menos de N minutos (N dinámico según recursos), reprograma respetando
ventanas de exclusión y prioridades, y documenta cada acción en logs y sugerencias.

Mejoras sobre v1:
  - Resolución con croniter real (sin aritmética artesanal de horas/días)
  - Prioridades explícitas en tareas.yaml (critica > alta > media > baja)
  - Resolución iterativa hasta convergencia total
  - Ventanas de exclusión que cruzan medianoche (23:00-01:00)
  - Modo --dry-run para depuración segura
  - Backups con timestamp (histórico no destructivo)
  - Conciencia de recursos en umbral de detección dinámico
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from croniter import croniter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
URA_BASE = Path("/opt/ura")
TASKS_CONFIG = URA_BASE / "config" / "tareas.yaml"
LOG_FILE = URA_BASE / "logs" / "scheduler.log"
SUGGESTIONS_FILE = URA_BASE / "data" / "sugerencias.json"
CRONTAB_BACKUP_DIR = URA_BASE / "backups"

MIN_GAP = timedelta(minutes=30)
MAX_ITERATIONS = 10
CRON_SEARCH_LIMIT = 168  # hours ahead (1 week)

RESOURCE_THRESHOLDS: dict[tuple[str, str], timedelta] = {
    ("cpu", "alta"): timedelta(minutes=60),
    ("cpu", "critica"): timedelta(minutes=90),
    ("disco", "alta"): timedelta(minutes=60),
    ("red", "alta"): timedelta(minutes=45),
}

PRIORITY_ORDER: dict[str, int] = {
    "critica": 0,
    "alta": 1,
    "media": 2,
    "baja": 3,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("SchedulerOrchestrator")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    for d in [URA_BASE, LOG_FILE.parent, SUGGESTIONS_FILE.parent, CRONTAB_BACKUP_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)


def load_tasks_config() -> dict[str, Any]:
    """Load tasks and global exclusion windows from YAML config."""
    with open(TASKS_CONFIG) as f:
        config = yaml.safe_load(f)
    return {
        "global_windows": config.get("ventanas_exclusion_globales", []),
        "tasks": config.get("tareas", []),
    }


def get_crontab_lines() -> list[str]:
    """Return current crontab lines."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    return result.stdout.splitlines()


def crontab_backup_path() -> Path:
    """Generate a timestamped backup path."""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return CRONTAB_BACKUP_DIR / f"crontab-{ts}.bak"


def save_crontab(lines: list[str], dry_run: bool = False) -> bool:
    """Save lines to crontab, with a timestamped backup before the change."""
    if dry_run:
        logger.info("[DRY-RUN] crontab se actualizaría con %d líneas", len(lines))
        return True
    current_lines = get_crontab_lines()
    backup_path = crontab_backup_path()
    with open(backup_path, "w") as f:
        f.write("\n".join(current_lines) + "\n")
    logger.info("Backup guardado en %s", backup_path)
    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(
        ["crontab", "-"], input=new_crontab, capture_output=True, text=True, timeout=10
    )
    if proc.returncode == 0:
        logger.info("Crontab actualizado correctamente")
        return True
    logger.error("Error al actualizar crontab: %s", proc.stderr)
    return False


def parse_next_execution(cron_expr: str, base: datetime | None = None) -> datetime | None:
    """Return the next execution datetime for a cron expression."""
    base = base or datetime.now()
    try:
        return croniter(cron_expr, base).get_next(datetime)
    except (ValueError, KeyError):
        return None


def time_in_exclusion_window(dt: datetime, windows: list[str]) -> bool:
    """Check if *dt* falls within any exclusion window (supports midnight-crossing)."""
    for window in windows:
        try:
            start_str, end_str = window.split("-", 1)
            start = datetime.strptime(start_str.strip(), "%H:%M").time()
            end = datetime.strptime(end_str.strip(), "%H:%M").time()
            t = dt.time()
            if start <= end:
                if start <= t <= end:
                    return True
            else:
                # Window crosses midnight (e.g. 23:00-01:00)
                if t >= start or t <= end:
                    return True
        except (ValueError, AttributeError):
            continue
    return False


def effective_min_gap(task: dict[str, Any]) -> timedelta:
    """Return dynamic minimum gap based on a single task's resource requirements."""
    gap = MIN_GAP
    recursos = task.get("recursos", {})
    for (res_type, level), threshold in RESOURCE_THRESHOLDS.items():
        if recursos.get(res_type) == level and threshold > gap:
            gap = threshold
    return gap


def combined_min_gap(task1: dict[str, Any], task2: dict[str, Any]) -> timedelta:
    """Return a minimum gap that considers the combined resource load of both tasks.

    When two resource-hungry tasks overlap, the gap grows beyond the
    individual maximum to account for cumulative system pressure.
    """
    gap = max(effective_min_gap(task1), effective_min_gap(task2))

    r1 = task1.get("recursos", {})
    r2 = task2.get("recursos", {})

    # Numeric CPU sum: if both tasks consume > 0.7 → widen the gap
    cpu_sum = float(r1.get("cpu", 0)) + float(r2.get("cpu", 0))
    if cpu_sum > 1.2:
        gap += timedelta(minutes=60)
    elif cpu_sum > 0.8:
        gap += timedelta(minutes=30)

    # Disk: if both demand high disk I/O → add extra buffer
    if r1.get("disco") == "alta" and r2.get("disco") == "alta":
        gap += timedelta(minutes=30)

    # Network: if both need high bandwidth → add moderate buffer
    if r1.get("red") == "alta" and r2.get("red") == "alta":
        gap += timedelta(minutes=15)

    return gap


def task_priority(task: dict[str, Any]) -> int:
    """Return numeric priority (0 highest, 99 unknown)."""
    return PRIORITY_ORDER.get(task.get("prioridad", ""), 99)


# ---------------------------------------------------------------------------
# Conflict detection & resolution
# ---------------------------------------------------------------------------
def detect_conflicts(tasks: list[dict[str, Any]]) -> list[tuple[dict, dict]]:
    """Return list of (loser, winner) pairs that conflict, respecting priorities.

    The task with lower priority (higher number) is returned second,
    meaning it is the one that should be moved.
    """
    now = datetime.now()
    enriched: list[dict] = []
    for t in tasks:
        nt = parse_next_execution(t["cron"], now)
        if nt:
            enriched.append({**t, "next_time": nt})
    enriched.sort(key=lambda x: x["next_time"])

    conflicts: list[tuple[dict, dict]] = []
    for i in range(len(enriched) - 1):
        t1, t2 = enriched[i], enriched[i + 1]
        threshold = combined_min_gap(t1, t2)
        diff = t2["next_time"] - t1["next_time"]
        if diff < threshold:
            p1, p2 = task_priority(t1), task_priority(t2)
            if p2 < p1:  # t2 has higher priority → move t1 (it runs first but is less important)
                conflicts.append((t2, t1))
            else:
                conflicts.append((t1, t2))
    return conflicts


def _shift_hour(
    dt: datetime,
    parts: list[str],
    exclusion_windows: list[str],
) -> tuple[str, datetime] | None:
    """Produce a new cron expression shifted 1-23 hours forward from *dt*."""
    for hours in range(1, 24):
        shifted = dt + timedelta(hours=hours)
        if time_in_exclusion_window(shifted, exclusion_windows):
            continue
        new_parts = [str(shifted.minute), str(shifted.hour), parts[2], parts[3], parts[4]]
        return (" ".join(new_parts), shifted)
    return None


def resolve_conflict(
    fixed_task: dict[str, Any],
    movable_task: dict[str, Any],
    exclusion_windows: list[str],
    other_tasks: list[dict[str, Any]],
) -> tuple[str, datetime] | None:
    """Find the next valid cron expression for *movable_task* that:
    - Is at least ``combined_min_gap`` after *fixed_task*
    - Does not fall in any exclusion window
    - Does not conflict with *other_tasks*

    When the next cron occurrence falls on the same hour as the original
    (e.g. same time next day), the hour is explicitly shifted so the
    resulting expression differs from the original, avoiding infinite loops.
    """
    original_cron = movable_task["cron"]
    parts = original_cron.split()
    if len(parts) != 5:
        return None

    base = fixed_task["next_time"] + combined_min_gap(fixed_task, movable_task)
    try:
        cron = croniter(original_cron, base)
    except (ValueError, KeyError):
        return None

    for _ in range(CRON_SEARCH_LIMIT):
        candidate = cron.get_next(datetime)
        if time_in_exclusion_window(candidate, exclusion_windows):
            continue
        conflict = False
        for other in other_tasks:
            if "fixed_time" in other:
                gap = combined_min_gap(other, movable_task).total_seconds()
                if abs((candidate - other["fixed_time"]).total_seconds()) < gap:
                    conflict = True
                    break
        if conflict:
            continue

        orig_hour, orig_min = int(parts[1]), int(parts[0])
        is_same_time = candidate.hour == orig_hour and candidate.minute == orig_min
        if is_same_time:
            # Same hour/minute on a different day → shift hour to avoid infinite loop
            result = _shift_hour(candidate, parts, exclusion_windows)
            if result:
                return result
            continue  # fallback: keep looking

        new_parts = [str(candidate.minute), str(candidate.hour), parts[2], parts[3], parts[4]]
        return (" ".join(new_parts), candidate)
    return None


# ---------------------------------------------------------------------------
# Crontab manipulation
# ---------------------------------------------------------------------------
def build_crontab_map(crontab_lines: list[str]) -> dict[str, dict[str, str]]:
    """Build ``{command: {cron, original_line}}`` from crontab lines."""
    current: dict[str, dict[str, str]] = {}
    for line in crontab_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(maxsplit=5)
        if len(parts) >= 6:
            cron = " ".join(parts[:5])
            command = parts[5]
            current[command] = {"cron": cron, "original_line": stripped}
    return current


def build_task_list(
    config_tasks: list[dict[str, Any]],
    crontab_map: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Merge YAML config tasks with actual crontab data.

    Uses substring matching so ``comando: /opt/ura/scripts/backup_ura.sh``
    matches crontab lines like ``bash /opt/ura/scripts/backup_ura.sh >> /var/log/...``.
    """
    tasks: list[dict[str, Any]] = []
    for t in config_tasks:
        cmd = t["comando"]
        matched_key: str | None = None
        for key in crontab_map:
            if cmd in key:
                matched_key = key
                break
        entry = crontab_map.get(matched_key) if matched_key else None  # type: ignore[arg-type]
        if entry:
            tasks.append(
                {
                    "nombre": t["nombre"],
                    "comando": cmd,
                    "cron": entry["cron"],
                    "recursos": t.get("recursos", {}),
                    "prioridad": t.get("prioridad", "media"),
                    "ventanas_exclusion": t.get("ventanas_exclusion", []),
                }
            )
        else:
            logger.warning("Tarea '%s' (%s) no encontrada en crontab", t["nombre"], cmd)
    return tasks


def merge_tasks_into_crontab_lines(
    lines: list[str],
    task_updates: dict[str, str],
) -> list[str]:
    """Apply ``{command: new_cron}`` changes to crontab lines.

    Uses substring matching to find the line to update, so a config key like
    ``docs_index.py`` matches ``/opt/homebrew/bin/python3 /opt/ura/scripts/docs_index.py >> ...``.
    """
    keys: list[str] = sorted(task_updates, key=len, reverse=True)  # longest match first
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        parts = stripped.split(maxsplit=5)
        if len(parts) >= 6:
            full_command = parts[5]
            matched_key: str | None = None
            for key in keys:
                if key in full_command:
                    matched_key = key
                    break
            if matched_key:
                new_line = f"{task_updates[matched_key]} " + " ".join(parts[5:])
                new_lines.append(new_line)
                logger.info("Reemplazando: %s -> %s", stripped, new_line)
                continue
        new_lines.append(line)
    return new_lines


# ---------------------------------------------------------------------------
# Suggestions persistence
# ---------------------------------------------------------------------------
def add_suggestion(problem: str, solution: str) -> None:
    """Append a suggestion entry to the suggestions JSON file."""
    sugs: list[dict] = []
    if SUGGESTIONS_FILE.exists():
        with open(SUGGESTIONS_FILE) as f:
            try:
                sugs = json.load(f)
            except json.JSONDecodeError:
                sugs = []
    sugs.append(
        {
            "timestamp": time.time(),
            "dominio": "scheduler",
            "problema": problem,
            "solucion": solution,
            "gravedad": "info",
        }
    )
    if len(sugs) > 200:
        sugs = sugs[-200:]
    with open(SUGGESTIONS_FILE, "w") as f:
        json.dump(sugs, f, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquestador proactivo de tareas programadas (crontab)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula los cambios sin modificar el crontab",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Nivel de logging (default: INFO)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.setLevel(getattr(logging, args.log_level.upper()))
    ensure_dirs()

    config = load_tasks_config()
    global_windows: list[str] = config["global_windows"]
    config_tasks: list[dict] = config["tasks"]

    if not config_tasks:
        logger.warning("No hay tareas configuradas en tareas.yaml")
        return 0

    crontab_lines = get_crontab_lines()
    crontab_map = build_crontab_map(crontab_lines)
    tasks = build_task_list(config_tasks, crontab_map)

    if not tasks:
        logger.warning("Ninguna tarea configurada coincide con el crontab actual")
        return 0

    task_updates, resolved_log = resolve_conflicts(
        tasks, crontab_map, global_windows, MAX_ITERATIONS
    )
    if not task_updates:
        logger.info("No hay cambios que aplicar")
        return 0

    new_lines = merge_tasks_into_crontab_lines(crontab_lines, task_updates)

    if args.dry_run:
        logger.info("[DRY-RUN] Cambios simulados (%d tarea(s))", len(task_updates))
        for cmd, nc in task_updates.items():
            logger.info("[DRY-RUN]   %s -> %s", cmd, nc)
        return 0

    if not save_crontab(new_lines):
        return 1

    logger.info("Crontab actualizado con %d cambio(s)", len(task_updates))
    for t1, t2, nc in resolved_log:
        add_suggestion(
            f"Conflicto: {t1['nombre']} y {t2['nombre']} muy cercanas",
            f"Se reprogramó {t2['nombre']} de {t2['cron']} a {nc}",
        )
    return 0


def resolve_conflicts(
    tasks: list[dict], crontab_map: dict, global_windows: list[str], max_iterations: int
) -> tuple[dict[str, str], list[tuple[dict, dict, str]]]:
    task_updates: dict[str, str] = {}
    resolved_log: list[tuple[dict, dict, str]] = []

    for iteration in range(1, max_iterations + 1):
        current_tasks = update_task_cron(tasks, task_updates)
        conflicts = detect_conflicts(current_tasks)

        if not conflicts:
            logger.info("Iteración %d: sin conflictos — convergencia alcanzada", iteration)
            break

        logger.info("Iteración %d: %d conflicto(s) detectado(s)", iteration, len(conflicts))
        for t1, t2 in conflicts:
            logger.info(
                "Conflicto: %s (%s) vs %s (%s)", t1["nombre"], t1["cron"], t2["nombre"], t2["cron"]
            )

            base = datetime.now()
            t1_next = parse_next_execution(t1["cron"], base)
            t2_next = parse_next_execution(t2["cron"], base)

            if t1_next is None or t2_next is None:
                logger.warning("No se pudo calcular ejecución para tareas en conflicto")
                continue

            t1_fixed = {**t1, "next_time": t1_next, "fixed_time": t1_next}
            t2_movable = {**t2, "next_time": t2_next}
            windows = global_windows + t2.get("ventanas_exclusion", [])

            other_fixed: list[dict] = []
            for t in current_tasks:
                if t["comando"] not in (t1["comando"], t2["comando"]):
                    nt = parse_next_execution(t["cron"], base)
                    if nt:
                        other_fixed.append({**t, "next_time": nt, "fixed_time": nt})

            result = resolve_conflict(t1_fixed, t2_movable, windows, [t1_fixed] + other_fixed)
            if result:
                new_cron, candidate_time = result
                task_updates[t2["comando"]] = new_cron
                resolved_log.append((t1, t2, new_cron))
                logger.info(
                    "Resuelto: %s -> %s (ejecutará ~%s)",
                    t2["nombre"],
                    new_cron,
                    candidate_time.strftime("%H:%M %Y-%m-%d"),
                )
            else:
                logger.warning("No se encontró horario válido para %s", t2["nombre"])

    if iteration == max_iterations:
        logger.warning(
            "Se alcanzó el máximo de %d iteraciones sin resolver todos los conflictos",
            max_iterations,
        )

    return task_updates, resolved_log


def update_task_cron(tasks: list[dict], task_updates: dict[str, str]) -> list[dict]:
    current_tasks = []
    for t in tasks:
        tc = dict(t)
        if t["comando"] in task_updates:
            tc["cron"] = task_updates[t["comando"]]
        current_tasks.append(tc)
    return current_tasks


def parse_next_execution(cron: str, base: datetime) -> Optional[datetime]:
    # Placeholder for actual implementation
    pass


def resolve_conflict(
    t1_fixed: dict, t2_movable: dict, windows: list[str], other_fixed: list[dict]
) -> Optional[tuple[str, datetime]]:
    # Placeholder for actual implementation
    pass


def merge_tasks_into_crontab_lines(
    crontab_lines: list[str], task_updates: dict[str, str]
) -> list[str]:
    # Placeholder for actual implementation
    pass


def save_crontab(new_lines: list[str]) -> bool:
    # Placeholder for actual implementation
    return True


def add_suggestion(title: str, message: str) -> None:
    # Placeholder for actual implementation
    pass


if __name__ == "__main__":
    sys.exit(main())
