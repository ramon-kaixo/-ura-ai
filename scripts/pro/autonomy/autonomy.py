#!/usr/bin/env python3
"""Autonomía v3.1 — orquestador multi-objetivo con cola priorizada.

Goal Manager → Planner → Executor → Evaluator → Learning
Gestiona múltiples objetivos con prioridades y dependencias.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.autonomy.goal_manager import GoalManager
from scripts.pro.autonomy.planner import Planner
from scripts.pro.autonomy.evaluator import Evaluator
from scripts.pro.autonomy.learning import LearningPlugin
from scripts.pro.tuneladora.engine import PipelineEngine


def _run_goal(engine, gm, planner, goal) -> dict:
    """Ejecuta un objetivo completo: planificar → ejecutar → evaluar."""
    engine.log.info(f"  ▶ Ejecutando objetivo: {goal['title']}")
    gm.set_status(goal["goal_id"], "in_progress")

    plan = planner.create_plan(goal)
    engine.log.info(f"    Plan: {plan['phases']}")

    results = planner.execute_plan(plan)

    ruff = engine.run_ruff(["check", "--select", "F821", ".", "--output-format", "concise"])
    results["ruff"] = {"ok": ruff.returncode, "errors": ruff.stdout.count("F821")}

    diff = engine.run_git(["diff", "--stat"])
    files_changed = len([l for l in diff.stdout.split("\n") if l.strip()]) if diff.stdout else 0
    engine.ledger.set_changes(files_changed, diff.stdout.count("+") + diff.stdout.count("-"))

    evaluator = Evaluator(engine)
    evaluation = evaluator.evaluate(goal, results)
    engine.log.info(f"    Decisión: {evaluation['action']} (score: {evaluation['score']})")

    status = "completed" if evaluation["action"] == "finalizar" else "failed"
    gm.set_status(goal["goal_id"], status, evaluation["action"])
    return evaluation


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="URA Autonomía v3.1 — Multi-objetivo")
    parser.add_argument("goals", nargs="*", default=[],
                        help="Objetivos a ejecutar (si no se especifican, usa la cola)")
    parser.add_argument("--priority", default="medium")
    parser.add_argument("--list", action="store_true", help="Listar cola de objetivos")
    parser.add_argument("--show", type=str, default=None, help="Mostrar detalle de un objetivo")
    parser.add_argument("--suspend", type=str, default=None, metavar="GOAL_ID")
    parser.add_argument("--resume", type=str, default=None, metavar="GOAL_ID")
    parser.add_argument("--cancel", type=str, default=None, metavar="GOAL_ID")
    parser.add_argument("--reprioritize", type=str, default=None, nargs=2,
                        metavar=("GOAL_ID", "PRIORITY"))
    parser.add_argument("--budget-time", type=int, default=3600)
    parser.add_argument("--budget-changes", type=int, default=50)
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="autonomy")
    gm = GoalManager(engine)

    # ── Comandos de gestión ──
    if args.list:
        for g in gm.queue():
            deps = f" (dep: {g['dependencies']})" if g.get("dependencies") else ""
            print(f"  [{g['status']:12}] {g['priority']:8} {g['title']}{deps}")
        print(f"\n  Total: {gm.summary()['total']} | "
              f"Pendientes: {gm.summary()['pending']} | "
              f"Completados: {gm.summary()['completed']}")
        return 0

    if args.show:
        g = gm.get(args.show)
        if g:
            for k, v in g.items():
                print(f"  {k}: {v}")
        else:
            print(f"  Objetivo no encontrado: {args.show}")
        return 0

    if args.suspend:
        gm.suspend(args.suspend)
        engine.log.info(f"Objetivo suspendido: {args.suspend}")
        return 0

    if args.resume:
        gm.resume(args.resume)
        engine.log.info(f"Objetivo reanudado: {args.resume}")
        return 0

    if args.cancel:
        gm.cancel(args.cancel)
        engine.log.info(f"Objetivo cancelado: {args.cancel}")
        return 0

    if args.reprioritize:
        gm.reprioritize(args.reprioritize[0], args.reprioritize[1])
        engine.log.info(f"Objetivo {args.reprioritize[0]} → prioridad {args.reprioritize[1]}")
        return 0

    # ── Crear objetivos ──
    engine.log.info("=" * 55)
    engine.log.info("  AUTONOMÍA v3.1 — Multi-objetivo")
    engine.log.info("=" * 55)

    created = []
    for title in args.goals:
        goal = gm.create(
            title=title,
            priority=args.priority,
            budget={"time_max_s": args.budget_time, "changes_max": args.budget_changes},
        )
        created.append(goal)
        engine.log.info(f"  Objetivo creado: {goal['goal_id']} — {title}")

    if not created:
        engine.log.info("  Sin objetivos nuevos — usando cola existente")
        created = gm.list_by_status("pending")

    # ── Ejecutar cola priorizada ──
    planner = Planner(engine)
    ordered = planner.plan_dependency_order(created, gm)

    engine.log.info(f"  Cola de ejecución: {len(ordered)} objetivos")
    for g in ordered:
        engine.log.info(f"    [{g['priority']}] {g['title']} (dep: {g.get('dependencies', [])})")

    t0 = time.time()
    results_summary = []
    for goal in ordered:
        engine.log.info(f"── Objetivo: {goal['title']} ──")
        evaluation = _run_goal(engine, gm, planner, goal)
        results_summary.append({
            "goal_id": goal["goal_id"],
            "title": goal["title"],
            "action": evaluation["action"],
        })

    # ── Learning ──
    engine.log.info("── Learning: Analizar historial ──")
    learning = LearningPlugin(engine)
    metrics = learning.analyze()
    engine.log.info(f"  Ejecuciones históricas: {metrics.get('total_ejecuciones', 0)}")

    # ── Cierre ──
    engine.ledger.resource_sample()
    engine.ledger.set_git_commit()
    ledger_path = engine.ledger.save()

    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report("AUTONOMÍA v3.1 FINALIZADA", [
        f"Objetivos ejecutados: {len(ordered)}",
        f"Duración: {H}h {M}m {S}s",
        f"Resultados: {[r['action'] for r in results_summary]}",
        f"Ledger: {ledger_path}",
    ])
    return 0 if all(r["action"] == "finalizar" for r in results_summary) else 1


if __name__ == "__main__":
    sys.exit(main())
