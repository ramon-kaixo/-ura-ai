#!/usr/bin/env python3
"""Tuneladora de Mejora Continua — instalación, plugins, refactorización.

Usa PipelineEngine (mismo motor que mantenimiento).
Puede invocar pipeline_refactor.py para refactorización pesada.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.plugin_registry import discover_all, run_phase


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Tuneladora de Mejora Continua")
    parser.add_argument("--file", type=str, default=None, help="Archivo específico a procesar")
    parser.add_argument("--list", action="store_true", help="Listar plugins disponibles")
    parser.add_argument("--refactor", action="store_true", help="Ejecutar pipeline de refactorización")
    parser.add_argument("--refactor-workers", type=int, default=4, help="Workers para refactor")
    parser.add_argument("--refactor-model", default="qwen2.5-coder:14b", help="Modelo de refactor")
    args = parser.parse_args()

    engine = PipelineEngine()

    engine.log.info("=" * 55)
    engine.log.info("  MEJORA CONTINUA")
    engine.log.info("=" * 55)

    # ── Descubrir plugins ──
    plugins = discover_all()
    engine.log.info(f"Plugins descubiertos: {len(plugins)}")
    if args.list:
        return 0

    t0 = time.time()

    # ── Fase pre: Validación ──
    engine.log.info("── Fase pre: Validación ──")
    result_pre = run_phase("pre", file_path=args.file)
    if result_pre.get("_aborted_by"):
        engine.log.warn(f"Abortado en pre: {result_pre['_aborted_by']}")
        return 1

    # ── Refactorización (si se solicita) ──
    if args.refactor:
        engine.log.info("── Refactorización ──")
        import subprocess  # noqa: PLC0415

        cmd = [
            engine.config.venv_python,
            "scripts/pro/pipeline_refactor.py",
            "--workers",
            str(args.refactor_workers),
            "--model",
            args.refactor_model,
        ]
        result = subprocess.run(cmd, timeout=3600, check=False, cwd=str(engine.config.ura_root))
        if result.returncode != 0:
            engine.log.warn(f"Refactor exit={result.returncode}")

    # ── Fase refactor: Plugins de transformación ──
    engine.log.info("── Fase refactor: Plugins ──")
    result_refactor = run_phase("refactor", file_path=args.file)
    if result_refactor.get("_aborted_by"):
        engine.log.warn(f"Abortado en refactor: {result_refactor['_aborted_by']}")
        return 1

    # ── Fase post: Validación final ──
    engine.log.info("── Fase post: Validación ──")
    result_post = run_phase("post", file_path=args.file)
    if result_post.get("_aborted_by"):
        engine.log.warn(f"Abortado en post: {result_post['_aborted_by']}")

    # ── Snapshot ──
    engine.snapshot.save("ultimo_ciclo")

    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report(
        "MEJORA CONTINUA FINALIZADA",
        [
            f"Duración: {H}h {M}m {S}s",
            f"Refactor: {'sí' if args.refactor else 'no'}",
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
