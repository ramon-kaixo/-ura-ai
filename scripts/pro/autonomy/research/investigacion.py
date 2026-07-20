#!/usr/bin/env python3
"""Investigación Autónoma — genera hipótesis, busca evidencias, sintetiza conclusiones.

Usa la memoria semántica como fuente de datos.
"""

from __future__ import annotations

import sys

from scripts.pro.tuneladora.engine import PipelineEngine


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="URA Investigación Autónoma")
    parser.add_argument("--research", action="store_true", help="Ejecutar ciclo completo")
    parser.add_argument("--sync", action="store_true", help="Sincronizar memoria primero")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="investigacion")
    db_path = engine.config.nervioso / "memory" / "semantic.db"

    if args.sync:
        from scripts.pro.autonomy.memory import SemanticMemory
        mem = SemanticMemory(db_path, engine.config.nervioso)
        engine.log.info("Sincronizando memoria semántica...")
        stats = mem.sync()
        engine.log.info(f"  {stats.get('procesados', 0)} ejecuciones nuevas")
        mem.close()

    if args.research:
        engine.log.info("=" * 55)
        engine.log.info("  INVESTIGACIÓN AUTÓNOMA")
        engine.log.info("=" * 55)

        from scripts.pro.autonomy.research import Researcher
        researcher = Researcher(db_path)
        result = researcher.research()
        researcher.close()

        engine.log.info(f"Hipótesis generadas: {result['total_hipotesis']}")
        for c in result.get("conclusiones", []):
            icon = {"confirmada": "✅", "no_concluyente": "❓", "refutada": "❌", "sin_datos": "⚠️"}
            engine.log.info(f"  {icon.get(c.get('veredicto', ''), '?')} [{c.get('veredicto', '')}] {c.get('title', '')}")
            engine.log.info(f"    Confianza: {c.get('confianza', 0)} | Evidencias: {c.get('total_evidencias', 0)}")
            engine.log.info(f"    {c.get('conclusion', '')[:120]}")

        engine.log.report("INVESTIGACIÓN FINALIZADA", [
            f"Hipótesis: {result['total_hipotesis']}",
            f"Confirmadas: {result['resumen']['confirmadas']}",
            f"No concluyentes: {result['resumen']['no_concluyentes']}",
            f"Refutadas: {result['resumen']['refutadas']}",
        ])

    return 0


if __name__ == "__main__":
    sys.exit(main())
