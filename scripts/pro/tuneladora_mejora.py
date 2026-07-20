#!/usr/bin/env python3
"""Tuneladora de Mejora Continua — plugins, optimización, refactorización.

Solo se puede invocar después de mantenimiento.
Si hay cambios detectados en la fase refactor, lanza pipeline_refactor.
Pipeline de Refactorización solo se inicia desde aquí.
"""

from __future__ import annotations

import sys
import time

from scripts.pro.plugin_registry import discover_all, run_phase
from scripts.pro.tuneladora.engine import PipelineEngine


def _hay_trabajo_refactor(result_refactor: dict) -> bool:
    """Determina si hay trabajo de refactorización pendiente."""
    plugins = result_refactor.get("plugins", {})
    for name, result in plugins.items():
        ok = result.get("ok", 0)
        err = result.get("errors", 0)
        if ok > 0 or err > 0:
            return True
    return False


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Tuneladora de Mejora Continua")
    parser.add_argument("--file", type=str, default=None, help="Archivo específico")
    parser.add_argument("--list", action="store_true", help="Listar plugins")
    parser.add_argument("--force-refactor", action="store_true", help="Forzar refactor aunque no haya cambios")
    args = parser.parse_args()

    engine = PipelineEngine()

    engine.log.info("=" * 55)
    engine.log.info("  MEJORA CONTINUA")
    engine.log.info("=" * 55)

    plugins = discover_all()
    engine.log.info(f"Plugins descubiertos: {len(plugins)}")
    if args.list:
        return 0

    t0 = time.time()
    refactor_ejecutado = False

    # ── Fase pre: Validación ──
    engine.log.info("── Fase pre: Validación ──")
    result_pre = run_phase("pre", file_path=args.file)
    if result_pre.get("_aborted_by"):
        engine.log.warn(f"Abortado en pre ({result_pre['_aborted_by']})")
        return 1

    # ── Fase refactor: Plugins de transformación ──
    engine.log.info("── Fase refactor: Plugins ──")
    result_refactor = run_phase("refactor", file_path=args.file)
    if result_refactor.get("_aborted_by"):
        engine.log.warn(f"Abortado en refactor ({result_refactor['_aborted_by']})")
        return 1

    # ── Decisión: ¿Hay trabajo de refactorización? ──
    if args.force_refactor or _hay_trabajo_refactor(result_refactor):
        engine.log.info("── Decisión: Refactorización necesaria ──")
        import subprocess  # noqa: PLC0415

        cmd = [
            engine.config.venv_python,
            "scripts/pro/pipeline_refactor.py",
            "--workers",
            "4",
            "--model",
            "qwen2.5-coder:14b",
        ]
        result = subprocess.run(cmd, timeout=3600, check=False, cwd=str(engine.config.ura_root))
        refactor_ejecutado = True
        if result.returncode != 0:
            engine.log.warn(f"Pipeline refactor exit={result.returncode}")
        else:
            engine.log.info("Pipeline refactor completado OK")
    else:
        engine.log.info("── Decisión: Sin cambios — refactor omitido ──")

    # ── Fase post: Validación final ──
    engine.log.info("── Fase post: Validación ──")
    result_post = run_phase("post", file_path=args.file)
    if result_post.get("_aborted_by"):
        engine.log.warn(f"Abortado en post ({result_post['_aborted_by']})")

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
            f"Refactor ejecutado: {'sí' if refactor_ejecutado else 'no'}",
            f"Plugins pre: {result_pre.get('ok', 0)} OK",
            f"Plugins refactor: {result_refactor.get('ok', 0)} OK",
            f"Plugins post: {result_post.get('ok', 0)} OK",
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
