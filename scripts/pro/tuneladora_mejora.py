#!/usr/bin/env python3
"""Tuneladora de Mejora Continua — plugins, optimización, refactorización.

Solo se puede invocar después de mantenimiento.
Pipeline Refactor solo se inicia desde aquí (R6: no recursivo).
Decisión: ¿hay trabajo? → refactor / informe y fin.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.plugin_registry import discover_all, run_phase
from scripts.pro.tuneladora.engine import PipelineEngine


def _hay_trabajo_refactor(result_refactor: dict) -> bool:
    """Determina si hay trabajo de refactorización pendiente."""
    plugins = result_refactor.get("results", {})
    for name, r in plugins.items():
        if isinstance(r, dict) and r.get("status") == "ok":
            return True
    return False


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Tuneladora de Mejora Continua")
    parser.add_argument("--file", type=str, default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--force-refactor", action="store_true")
    args = parser.parse_args()

    engine = PipelineEngine()

    # R6: protección contra refactorización recursiva
    if engine._refactor_ejecutado:
        engine.log.warn("Refactor ya ejecutado en este ciclo — omitiendo")
        return 0

    engine.log.info("=" * 55)
    engine.log.info("  MEJORA CONTINUA")
    engine.log.info("=" * 55)

    plugins = discover_all()
    engine.log.info(f"Plugins descubiertos: {len(plugins)}")
    if args.list:
        return 0

    t0 = time.time()
    refactor_ejecutado = False

    # ── Fase pre ──
    engine.log.info("── Fase pre: Validación ──")
    t_pre = time.time()
    result_pre = run_phase("pre", file_path=args.file)
    engine.metrics.plugin_done("pre", round(time.time() - t_pre, 1))
    if result_pre.get("_aborted_by"):
        engine.log.warn(f"Abortado en pre ({result_pre['_aborted_by']})")
        engine.metrics.set_result("aborted_pre")
        engine.metrics.save()
        return 1

    # ── Fase refactor ──
    engine.log.info("── Fase refactor: Plugins ──")
    t_ref = time.time()
    result_refactor = run_phase("refactor", file_path=args.file)
    engine.metrics.plugin_done("refactor_plugins", round(time.time() - t_ref, 1))
    if result_refactor.get("_aborted_by"):
        engine.log.warn(f"Abortado en refactor ({result_refactor['_aborted_by']})")
        engine.metrics.set_result("aborted_refactor")
        engine.metrics.save()
        return 1

    # ── Decisión: ¿Hay trabajo de refactorización? ──
    hay_trabajo = args.force_refactor or _hay_trabajo_refactor(result_refactor)
    if hay_trabajo:
        engine.log.info("── Decisión: Refactorización necesaria ──")
        import subprocess

        cmd = [
            engine.config.venv_python,
            "scripts/pro/pipeline_refactor.py",
            "--workers", "4",
            "--model", "qwen2.5-coder:14b",
        ]
        t_ref2 = time.time()
        result = subprocess.run(cmd, timeout=3600, check=False, cwd=str(engine.config.ura_root))
        engine.metrics.plugin_done("pipeline_refactor", round(time.time() - t_ref2, 1))
        refactor_ejecutado = True
        PipelineEngine._refactor_ejecutado = True  # R6: proteger contra recursión
        if result.returncode != 0:
            engine.log.warn(f"Pipeline refactor exit={result.returncode}")
        else:
            engine.log.info("Pipeline refactor completado OK")
    else:
        engine.log.info("── Decisión: Sin cambios — refactor omitido ──")

    # ── Fase post ──
    engine.log.info("── Fase post: Validación ──")
    t_post = time.time()
    result_post = run_phase("post", file_path=args.file)
    engine.metrics.plugin_done("post", round(time.time() - t_post, 1))
    if result_post.get("_aborted_by"):
        engine.log.warn(f"Abortado en post ({result_post['_aborted_by']})")

    # ── R1: Política de promoción ──
    ruff_ok = result_post.get("results", {}).get("ruff_check", {}).get("exit_code", 0) == 0
    engine.promotion.record("ruff", ruff_ok, "0 errores" if ruff_ok else "con errores")
    engine.promotion.record("refactor_ejecutado", refactor_ejecutado, "")
    if not engine.promotion.can_promote:
        engine.log.warn("Política de promoción NO superada")
        for line in engine.promotion.summary:
            engine.log.warn(line)

    # ── Snapshot ──
    engine.snapshot.save("ultimo_ciclo")

    # ── Métricas ──
    engine.metrics.set_result("completado" if not hay_trabajo or result.returncode == 0 else "fallido")
    engine.metrics.save()

    # ── Reporte ──
    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report("MEJORA CONTINUA FINALIZADA", [
        f"Duración: {H}h {M}m {S}s",
        f"Refactor ejecutado: {'sí' if refactor_ejecutado else 'no'}",
        f"Plugins pre: {result_pre.get('ok', 0)} OK",
        f"Plugins refactor: {result_refactor.get('ok', 0)} OK",
        f"Plugins post: {result_post.get('ok', 0)} OK",
        f"Promocionable: {'sí' if engine.promotion.can_promote else 'no'}",
    ])
    return 0


if __name__ == "__main__":
    sys.exit(main())
