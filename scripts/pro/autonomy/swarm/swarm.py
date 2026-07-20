#!/usr/bin/env python3
"""Swarm URA — sistema multiagente coordinado.

Coordinator asigna objetivos a agentes especializados según el dominio.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.autonomy.goal_manager import GoalManager


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="URA Swarm Multiagente")
    parser.add_argument("goals", nargs="*", default=["Auditar el repositorio URA"],
                        help="Objetivos para los agentes")
    parser.add_argument("--list-domains", action="store_true", help="Listar dominios disponibles")
    parser.add_argument("--sync", action="store_true", help="Sincronizar memoria semántica primero")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="swarm")

    if args.list_domains:
        from scripts.pro.autonomy.swarm import DOMAIN_MAP
        engine.log.info("Dominios disponibles:")
        for keyword, domain in sorted(DOMAIN_MAP.items()):
            engine.log.info(f"  {keyword:20} → {domain}")
        return 0

    # Sincronizar memoria si se pide
    if args.sync:
        db_path = engine.config.nervioso / "memory" / "semantic.db"
        from scripts.pro.autonomy.memory import SemanticMemory
        mem = SemanticMemory(db_path, engine.config.nervioso)
        engine.log.info("Sincronizando memoria semántica...")
        stats = mem.sync()
        engine.log.info(f"  {stats.get('procesados', 0)} ejecuciones nuevas")
        mem.close()

    # Crear agentes
    from scripts.pro.autonomy.swarm import (
        Coordinator,
        ArchitectureAgent, SecurityAgent, PerformanceAgent,
        DocumentationAgent, ResearchAgent, TestingAgent,
    )

    agents = [
        ArchitectureAgent(engine),
        SecurityAgent(engine),
        PerformanceAgent(engine),
        DocumentationAgent(engine),
        ResearchAgent(engine),
        TestingAgent(engine),
    ]
    coordinator = Coordinator(engine, agents)
    gm = GoalManager(engine)

    engine.log.info("=" * 55)
    engine.log.info("  SWARM URA — Multiagente")
    engine.log.info(f"  Agentes: {len(agents)} ({', '.join(a.name for a in agents)})")
    engine.log.info("=" * 55)

    # Crear objetivos y asignar
    t0 = time.time()
    for title in args.goals:
        goal = gm.create(title=title)
        engine.log.info(f"  Objetivo: {goal['goal_id'][:8]} — {title}")
        domain = coordinator.resolve_agent(goal)
        if domain:
            result = coordinator.assign(goal)
            gm.set_status(goal["goal_id"], result.get("result", "unknown"))
        else:
            engine.log.warn(f"  Sin agente para: {title}")

    # Reporte final
    assignments = coordinator.summary()
    engine.log.report("SWARM FINALIZADO", [
        f"Objetivos: {len(args.goals)}",
        f"Asignaciones: {len(assignments)}",
        f"Duración: {round(time.time() - t0, 1)}s",
    ])
    for a in assignments:
        engine.log.info(f"  [{a.get('result', '?')}] {a.get('agent', '?')} → {a.get('title', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
