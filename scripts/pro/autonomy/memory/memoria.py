#!/usr/bin/env python3
"""Memoria Semántica — capa de conocimiento sobre el ExecutionLedger.

Sincroniza el ledger en SQLite con índices para consultas eficientes.
"""

from __future__ import annotations

import sys

from scripts.pro.tuneladora.engine import PipelineEngine


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="URA Memoria Semántica")
    parser.add_argument("--sync", action="store_true", help="Sincronizar ledger → SQLite")
    parser.add_argument("--rebuild", action="store_true", help="Reconstruir desde cero")
    parser.add_argument("--summary", action="store_true", help="Resumen de la base")
    parser.add_argument("--goals", type=str, default=None, help="Objetivos por estado (pending/completed)")
    parser.add_argument("--slow-plugins", action="store_true", help="Plugins más lentos")
    parser.add_argument("--executions", type=str, default=None, help="Ejecuciones por pipeline")
    parser.add_argument("--recent", type=int, default=0, help="Ejecuciones de los últimos N días")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="memoria")
    db_path = engine.config.nervioso / "memory" / "semantic.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    from scripts.pro.autonomy.memory import SemanticMemory  # noqa: PLC0415

    mem = SemanticMemory(db_path, engine.config.nervioso)

    if args.sync:
        engine.log.info("Sincronizando ledger → SQLite...")
        stats = mem.sync()
        engine.log.info(f"  Procesados: {stats.get('procesados', 0)}")
        engine.log.info(f"  Omitidos (ya existentes): {stats.get('omitidos', 0)}")
        engine.log.info(f"  Errores: {stats.get('errores', 0)}")

    if args.rebuild:
        engine.log.info("Reconstruyendo base desde cero...")
        stats = mem.rebuild()
        engine.log.info(f"  Procesados: {stats.get('procesados', 0)}")

    if args.summary:
        s = mem.summary()
        engine.log.info(f"Base de datos: {s.get('basedatos', '')}")
        engine.log.info(f"Ejecuciones: {s.get('execuciones', 0)}")
        engine.log.info(f"Plugins registrados: {s.get('plugins', 0)}")
        engine.log.info(f"Decisiones: {s.get('decisiones', 0)}")
        engine.log.info(f"Objetivos: {s.get('objetivos', 0)}")
        engine.log.info(f"Tasa de promoción: {s.get('tasa_promocion', 0)}%")

    if args.goals:
        for g in mem.queries.goals_by_status(args.goals):
            engine.log.info(f"  [{g['status']}] {g['title']} ({g['goal_id']})")

    if args.slow_plugins:
        for p in mem.queries.slowest_plugins(limit=10):
            engine.log.info(f"  {p['plugin_name']:30} media={p['avg_dur']:>6.1f}s  fallos={p['errors']}")

    if args.executions:
        for e in mem.queries.executions_by_pipeline(args.executions, limit=10):
            engine.log.info(f"  {e['execution_id'][:12]} {e['result']:12} {e.get('duration_ms', 0)}ms")

    if args.recent:
        for e in mem.queries.executions_by_date(days=args.recent):
            engine.log.info(f"  {e['execution_id'][:12]} {e['pipeline']:12} {e['result']:12} {e.get('duration_ms', 0)}ms")

    mem.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
