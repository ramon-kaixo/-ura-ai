#!/usr/bin/env python3
"""Aprendizaje v4.0 — subsistema completo de aprendizaje avanzado.

Pipeline: Ledger → Pattern Analyzer → Knowledge Base → Recommendation Engine → Policy Engine → Trend Monitor
"""

from __future__ import annotations

import sys

from scripts.pro.tuneladora.engine import PipelineEngine


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="URA Aprendizaje v4.0")
    parser.add_argument(
        "--mode", choices=["observacion", "asistido", "autonomo"], default="observacion", help="Modo del Policy Engine"
    )
    parser.add_argument("--verify", action="store_true", help="Verificar políticas pendientes")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="aprendizaje")

    engine.log.info("=" * 55)
    engine.log.info("  APRENDIZAJE v4.0")
    engine.log.info("=" * 55)
    engine.log.info(f"  Modo: {args.mode}")

    # Cargar componentes
    from scripts.pro.autonomy.learning.knowledge_base import KnowledgeBase
    from scripts.pro.autonomy.learning.ledger_utils import LedgerValidator
    from scripts.pro.autonomy.learning.pattern_analyzer import PatternAnalyzer
    from scripts.pro.autonomy.learning.policy_engine import PolicyEngine
    from scripts.pro.autonomy.learning.recommendation_engine import RecommendationEngine
    from scripts.pro.autonomy.learning.trend_monitor import TrendMonitor

    analyzer = PatternAnalyzer(engine.config.nervioso)
    kb = KnowledgeBase(engine.config.nervioso)
    monitor = TrendMonitor(engine.config.nervioso)
    recommender = RecommendationEngine(analyzer, kb)
    policies = PolicyEngine(kb, monitor, mode=args.mode)

    # ── 0. Validación del Ledger ──
    engine.log.info("── 0. Validación del ExecutionLedger ──")
    validator = LedgerValidator(engine.config.nervioso)
    validator.load()
    engine.log.info(f"  {validator.summary.split(chr(10))[0]}")
    if validator.stats["invalidos"] > 0:
        engine.log.warning(f"  {validator.stats['invalidos']} registros inválidos:")
        for motivo, count in validator.stats["motivos"].items():
            engine.log.warning(f"    - {motivo}: {count}")
    else:
        engine.log.info("  Todos los registros válidos ✅")

    # ── 1. Pattern Analyzer ──
    engine.log.info("── 1. Pattern Analyzer: Detectando patrones ──")
    patterns = analyzer.analyze()
    if patterns:
        engine.log.info(f"  Patrones detectados: {len(patterns)}")
        for p in patterns:
            engine.log.info(f"    {p['pattern']}: {p['occurrences']} ocurrencias ({p['severity']})")
            engine.ledger.add_pattern(p)
            kb.from_pattern(p)
    else:
        engine.log.info("  Sin patrones (datos insuficientes)")

    # ── 2. Knowledge Base ──
    engine.log.info("── 2. Knowledge Base: Conocimiento persistente ──")
    knowledge = kb.search()
    engine.log.info(f"  Entradas de conocimiento: {len(knowledge)}")
    for k in knowledge[-3:]:
        engine.log.info(f"    [{k['category']}] {k['claim'][:60]}")
        engine.ledger.add_knowledge(k)

    # ── 3. Recommendation Engine ──
    engine.log.info("── 3. Recommendation Engine: Generando recomendaciones ──")
    recommendations = recommender.generate()
    if recommendations:
        engine.log.info(f"  Recomendaciones: {len(recommendations)}")
        for rec in recommendations:
            engine.log.info(f"    [{rec['impact']}] {rec['title']} (confianza: {rec['confidence']})")
            engine.ledger.add_recommendation(rec)
    else:
        engine.log.info("  Sin recomendaciones")

    # ── 4. Policy Engine ──
    engine.log.info(f"── 4. Policy Engine (modo: {args.mode}) ──")
    decisions = []
    for rec in recommendations:
        decision = policies.evaluate(rec)
        decisions.append(decision)
        if decision["applied"]:
            engine.log.info(f"  ✅ Aplicada: {decision.get('policy')} — {rec['title']}")
        else:
            engine.log.info(f"  ℹ️  {decision.get('action')}: {decision.get('reason', rec['title'])[:60]}")
        engine.ledger.add_policy(decision)

    if args.mode == "autonomo":
        engine.log.info(f"  Políticas aplicadas: {sum(1 for d in decisions if d.get('applied'))}")

    # ── 5. Verificación ──
    if args.verify:
        engine.log.info("── 5. Trend Monitor: Verificando políticas ──")
        verifications = policies.verify_policies()
        for v in verifications:
            action = "✅ Confirmada" if v["improved"] else "⏪ Rollback"
            engine.log.info(f"  {action}: {v['policy_id']} (before: {v['before']}s, after: {v['after']}s)")
            engine.ledger.add_verification(v)
            if v["improved"]:
                monitor.mark_verified(v["policy_id"], True)
    else:
        engine.log.info("── 5. Verificación: usar --verify en próxima ejecución ──")

    # ── Cierre ──
    engine.ledger.resource_sample()
    engine.ledger.set_git_commit()
    engine.ledger.set_result("completado")
    ledger_path = engine.ledger.save()

    engine.log.report(
        "APRENDIZAJE v4.0 FINALIZADO",
        [
            f"Modo: {args.mode}",
            f"Patrones detectados: {len(patterns)}",
            f"Conocimiento generado: {len(knowledge)}",
            f"Recomendaciones: {len(recommendations)}",
            f"Políticas aplicadas: {sum(1 for d in decisions if d.get('applied'))}",
            f"Ledger: {ledger_path}",
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
