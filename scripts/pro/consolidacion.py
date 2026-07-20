#!/usr/bin/env python3
"""Consolidación Automática — ciclo completo de calidad.

Ejecuta: Gates → Mantenimiento → Mejora → Refactor → Reuse → Auditoría
Disparadores: cada N commits, cada N líneas, antes de tag, antes de merge
"""

from __future__ import annotations

import sys
import time

from scripts.pro.tuneladora.engine import PipelineEngine


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Consolidación Automática")
    parser.add_argument("--check", action="store_true", help="Solo verificar si debe ejecutarse")
    parser.add_argument("--commit-threshold", type=int, default=10)
    parser.add_argument("--lines-threshold", type=int, default=2000)
    parser.add_argument("--force", action="store_true", help="Forzar ciclo aunque no sea necesario")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="consolidacion")

    # ── 0. Quality Gates ──
    from scripts.pro.reuse.quality_gates import QualityGates

    gates = QualityGates(engine.config.ura_root)
    result = gates.should_run_maintenance(
        commit_threshold=args.commit_threshold,
        lines_threshold=args.lines_threshold,
    )

    engine.log.info(f"Commits desde último tag: {result['commits']}")
    engine.log.info(f"Líneas modificadas: {result['lines_changed']}")

    if not args.force and not result["should_run"]:
        engine.log.info("Sin actividad suficiente. Omitiendo ciclo.")
        return 0

    if args.check:
        for r in result["reasons"]:
            engine.log.info(f"  Motivo: {r}")
        return 0

    t0 = time.time()

    # ── 1. Tuneladora de Mantenimiento ──
    engine.log.info("── 1. Mantenimiento ──")
    import subprocess
    subprocess.run(
        [engine.config.venv_python, "scripts/pro/tuneladora_mantenimiento.py", "--nivel", "profundo"],
        timeout=3600, check=False, cwd=str(engine.config.ura_root),
    )

    # ── 2. Tuneladora de Mejora ──
    engine.log.info("── 2. Mejora Continua ──")
    subprocess.run(
        [engine.config.venv_python, "scripts/pro/tuneladora_mejora.py"],
        timeout=3600, check=False, cwd=str(engine.config.ura_root),
    )

    # ── 3. Pipeline de Refactorización ──
    engine.log.info("── 3. Refactorización ──")
    subprocess.run(
        [engine.config.venv_python, "scripts/pro/pipeline_refactor.py", "--workers", "2"],
        timeout=3600, check=False, cwd=str(engine.config.ura_root),
    )

    # ── 4. Reuse Detector ──
    engine.log.info("── 4. Reuse Detector ──")
    from scripts.pro.reuse.reuse_detector import ReuseDetector
    detector = ReuseDetector(engine.config.ura_root)
    indexed = detector.build_index()
    engine.log.info(f"  Indexadas {indexed} funciones")
    for pyfile in engine.config.ura_root.rglob("*.py"):
        if ".venv" in str(pyfile) or ".sandbox" in str(pyfile):
            continue
        code = pyfile.read_text(encoding="utf-8", errors="ignore")
        if "class " not in code and "def " not in code:
            continue
        duplicates = detector.analyze_new_code(code, min_score=0.75)
        if duplicates:
            for d in duplicates[:2]:
                engine.log.warn(f"  Posible duplicación: {d.get('new_name')} ≈ {d.get('existing_name')} ({d.get('score', 0):.0%})")

    # ── 5. Conocimiento: olvido ──
    engine.log.info("── 5. Política de olvido ──")
    from scripts.pro.autonomy.learning.knowledge_base import KnowledgeBase
    kb = KnowledgeBase(engine.config.nervioso)
    archived = kb.forget(max_age_days=90, min_confidence=0.3)
    engine.log.info(f"  Conocimiento archivado: {len(archived)} entradas")
    stats = kb.stats()
    engine.log.info(f"  Activo: {stats['active']}, Archivado: {stats['archived']}, Deprecado: {stats['deprecated']}")

    # ── 6. Learning: analizar ──
    engine.log.info("── 6. Aprendizaje ──")
    from scripts.pro.autonomy.learning import LearningPlugin
    learning = LearningPlugin(engine)
    metrics = learning.analyze()
    engine.log.info(f"  Ejecuciones históricas: {metrics.get('total_ejecuciones', 0)}")

    # ── Reporte ──
    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report("CONSOLIDACIÓN FINALIZADA", [
        f"Motivo: {', '.join(result['reasons']) if result['reasons'] else 'manual'}",
        f"Duración: {H}h {M}m {S}s",
        f"Mantenimiento + Mejora + Refactor: ejecutados",
        f"Reuse: {indexed} funciones indexadas",
        f"Olvido: {len(archived)} entradas archivadas",
        f"Aprendizaje: {metrics.get('total_ejecuciones', 0)} ejecuciones analizadas",
    ])
    return 0


if __name__ == "__main__":
    sys.exit(main())
