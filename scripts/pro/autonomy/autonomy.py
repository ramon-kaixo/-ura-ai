#!/usr/bin/env python3
"""Autonomía v3.0 — Orquestador del vertical slice completo.

Recibe un objetivo, lo planifica, ejecuta, evalúa y aprende.
Todo registrado en el ExecutionLedger.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.autonomy.goal_manager import GoalManager
from scripts.pro.autonomy.planner import Planner
from scripts.pro.autonomy.evaluator import Evaluator
from scripts.pro.autonomy.learning import LearningPlugin
from scripts.pro.tuneladora.engine import PipelineEngine


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="URA Autonomía v3.0")
    parser.add_argument("title", nargs="*", default=["Auditar el repositorio URA"],
                        help="Objetivo de alto nivel")
    parser.add_argument("--priority", default="medium")
    parser.add_argument("--budget-time", type=int, default=3600)
    parser.add_argument("--budget-changes", type=int, default=50)
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="autonomy")
    title = " ".join(args.title)

    engine.log.info("=" * 55)
    engine.log.info("  AUTONOMÍA v3.0 — Vertical Slice")
    engine.log.info("=" * 55)

    t0 = time.time()

    # ── 1. Goal Manager ──
    engine.log.info("── 1. Goal Manager: Crear objetivo ──")
    gm = GoalManager(engine)
    goal = gm.create(
        title=title,
        priority=args.priority,
        budget={"time_max_s": args.budget_time, "changes_max": args.budget_changes},
    )
    engine.log.info(f"  Objetivo creado: {goal['goal_id']} — {title}")
    gm.set_status(goal["goal_id"], "in_progress")

    # ── 2. Planner ──
    engine.log.info("── 2. Planner: Generar plan ──")
    planner = Planner(engine)
    plan = planner.create_plan(goal)
    engine.log.info(f"  Plan: {len(plan['phases'])} fases — {plan['phases']}")

    # ── 3. Executor ──
    engine.log.info("── 3. Executor: Ejecutar plan ──")
    results = planner.execute_plan(plan)

    # Ruff check como tarea específica
    ruff = engine.run_ruff(["check", "--select", "F821", ".", "--output-format", "concise"])
    results["ruff"] = {"ok": ruff.returncode, "errors": ruff.stdout.count("F821")}

    # Git diff para presupuesto
    diff = engine.run_git(["diff", "--stat"])
    files_changed = len([l for l in diff.stdout.split("\n") if l.strip()]) if diff.stdout else 0
    engine.ledger.set_changes(files_changed, diff.stdout.count("+") + diff.stdout.count("-"))

    # ── 4. Evaluator ──
    engine.log.info("── 4. Evaluator: Evaluar resultado ──")
    evaluator = Evaluator(engine)
    evaluation = evaluator.evaluate(goal, results)
    engine.log.info(f"  Decisión: {evaluation['action']} (score: {evaluation['score']})")
    gm.set_status(goal["goal_id"], "completed" if evaluation["action"] == "finalizar" else "failed")

    # ── 5. Learning ──
    engine.log.info("── 5. Learning: Analizar historial ──")
    learning = LearningPlugin(engine)
    metrics = learning.analyze()
    engine.log.info(f"  Ejecuciones históricas: {metrics.get('total_ejecuciones', 0)}")
    if metrics.get("duracion_media_s"):
        engine.log.info(f"  Duración media: {metrics['duracion_media_s']}s")

    # ── Cierre ──
    engine.ledger.set_result(evaluation["action"])
    engine.ledger.resource_sample()
    engine.ledger.set_git_commit()
    ledger_path = engine.ledger.save()

    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report("AUTONOMÍA v3.0 FINALIZADA", [
        f"Objetivo: {title}",
        f"Duración: {H}h {M}m {S}s",
        f"Fases ejecutadas: {plan['phases']}",
        f"Decisión: {evaluation['action']}",
        f"Ejecuciones históricas: {metrics.get('total_ejecuciones', 0)}",
        f"Ledger: {ledger_path}",
    ])
    return 0 if evaluation["action"] == "finalizar" else 1


if __name__ == "__main__":
    sys.exit(main())
