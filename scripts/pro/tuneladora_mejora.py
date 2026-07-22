#!/usr/bin/env python3
"""Tuneladora de Mejora Continua — v2.3 con checkpoint, ledger y presupuesto.

Pipeline Refactor solo se inicia desde aquí.
Checkpoint por fase permite reanudación tras interrupción.
ExecutionLedger registra metadatos completos de cada ejecución.
"""

from __future__ import annotations

import subprocess
import sys
import time

from scripts.pro.plugin_registry import discover_all, run_phase
from scripts.pro.tuneladora.engine import PipelineEngine

PHASES = ["pre", "refactor_plugins", "pipeline_refactor", "post"]


def _hay_trabajo_refactor(result_refactor: dict) -> bool:
    plugins = result_refactor.get("results", {})
    return any(isinstance(r, dict) and r.get("status") == "ok" for name, r in plugins.items())


def _check_budget(engine: PipelineEngine) -> int:
    """Cuenta cambios con git diff y verifica presupuesto."""
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(engine.config.ura_root),
            check=False,
        )
        lines = diff.stdout.strip().split("\n")
        if not lines or lines == [""]:
            return 0
        files = len([l for l in lines if l.strip() and "changed" not in l])
        changed = diff.stdout.count("+") + diff.stdout.count("-")
        engine.ledger.set_changes(files, changed)
        engine.promotion.check_budget(files, changed)
        engine.log.info(f"Cambios: {files} archivos, {changed} líneas")
        return files
    except Exception:
        return 0


def _run_phase_with_checkpoint(engine: PipelineEngine, phase: str, file_path: str | None) -> dict:
    """Ejecuta una fase si no está en checkpoint. La registra en ledger."""
    if engine.checkpoint.is_done(phase):
        engine.log.info(f"── Fase '{phase}' ya completada (checkpoint) — omitiendo")
        engine.ledger.phase_skip(phase)
        return {"status": "skipped", "phase": phase}

    engine.log.info(f"── Fase: {phase} ──")
    engine.ledger.phase_start(phase)
    t0 = time.time()

    result = {"status": "noop"} if phase == "pipeline_refactor" else run_phase(phase, file_path=file_path)

    engine.ledger.plugin_done(phase, round(time.time() - t0, 1))
    engine.checkpoint.mark_done(phase)
    return result


def main() -> int:  # noqa: PLR0915
    import argparse

    parser = argparse.ArgumentParser(description="Tuneladora de Mejora Continua v2.3")
    parser.add_argument("--file", type=str, default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--force-refactor", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignorar checkpoint, ejecutar completo")
    parser.add_argument("--trigger", default="manual")
    args = parser.parse_args()

    engine = PipelineEngine(pipeline="mejora")
    engine.ledger.set_trigger(args.trigger)
    engine.ledger.set_git_commit()
    engine.ledger.resource_sample()

    # R6: protección recursiva
    if engine._refactor_ejecutado:
        engine.log.warn("Refactor ya ejecutado en este ciclo — omitiendo")
        return 0

    engine.log.info("=" * 55)
    engine.log.info("  MEJORA CONTINUA v2.3")
    engine.log.info("=" * 55)

    # ── Checkpoint: intentar reanudación ──
    if not args.force and engine.checkpoint.resume():
        engine.log.info(f"Checkpoint encontrado: reanudando desde fase '{engine.checkpoint.last_completed}'")
    elif not args.force:
        engine.checkpoint.clear()

    plugins = discover_all()
    engine.log.info(f"Plugins descubiertos: {len(plugins)}")
    if args.list:
        return 0

    t0 = time.time()
    refactor_ejecutado = False
    result_pre = {}
    result_refactor = {}
    result_post = {}

    # ── Fase pre ──
    result_pre = _run_phase_with_checkpoint(engine, "pre", args.file)
    if result_pre.get("_aborted_by"):
        engine.log.warn(f"Abortado en pre ({result_pre['_aborted_by']})")
        engine.ledger.set_result("aborted_pre")
        engine.ledger.save()
        return 1

    # ── Fase refactor_plugins ──
    result_refactor = _run_phase_with_checkpoint(engine, "refactor_plugins", args.file)
    if result_refactor.get("_aborted_by"):
        engine.log.warn(f"Abortado en refactor ({result_refactor['_aborted_by']})")
        engine.ledger.set_result("aborted_refactor")
        engine.ledger.save()
        return 1

    # ── Decisión: ¿Hay trabajo de refactorización? ──
    hay_trabajo = args.force_refactor or _hay_trabajo_refactor(result_refactor)
    if hay_trabajo:
        if not engine.checkpoint.is_done("pipeline_refactor"):
            engine.log.info("── Decisión: Refactorización necesaria ──")
            engine.ledger.phase_start("pipeline_refactor")
            t_ref = time.time()
            cmd = [
                engine.config.venv_python,
                "scripts/pro/pipeline_refactor.py",
                "--workers",
                "4",
                "--model",
                "qwen2.5-coder:14b",
            ]
            result = subprocess.run(cmd, timeout=3600, check=False, cwd=str(engine.config.ura_root))
            engine.ledger.plugin_done("pipeline_refactor", round(time.time() - t_ref, 1))
            refactor_ejecutado = True
            PipelineEngine._refactor_ejecutado = True
            engine.checkpoint.mark_done("pipeline_refactor")
            if result.returncode != 0:
                engine.log.warn(f"Pipeline refactor exit={result.returncode}")
            else:
                engine.log.info("Pipeline refactor completado OK")
        else:
            engine.log.info("── Pipeline refactor ya completado (checkpoint) — omitiendo")
            engine.ledger.phase_skip("pipeline_refactor")
    else:
        engine.log.info("── Decisión: Sin cambios — refactor omitido ──")
        engine.ledger.phase_skip("pipeline_refactor")

    # ── Presupuesto de cambios ──
    _check_budget(engine)

    # ── Fase post ──
    result_post = _run_phase_with_checkpoint(engine, "post", args.file)
    if result_post.get("_aborted_by"):
        engine.log.warn(f"Abortado en post ({result_post['_aborted_by']})")

    # ── R1: Política de promoción ──
    ruff_ok = result_post.get("results", {}).get("post", {}).get("exit_code", 0) == 0
    engine.promotion.record("ruff", ruff_ok, "0 errores" if ruff_ok else "con errores")
    engine.promotion.record("refactor_ejecutado", refactor_ejecutado, "")

    if not engine.promotion.can_promote:
        engine.log.warn("Política de promoción NO superada")
        for line in engine.promotion.summary:
            engine.log.warn(line)
        engine.ledger.set_promotion(False)
    else:
        engine.ledger.set_promotion(True)

    # ── Snapshot ──
    snap = engine.snapshot.save("ultimo_ciclo")
    if snap:
        engine.ledger.set_snapshot_id(snap.name)

    # ── Ledger ──
    engine.ledger.resource_sample()
    engine.ledger.set_git_commit(after="HEAD")
    engine.ledger.set_result("completado")
    ledger_path = engine.ledger.save()

    # ── Cleanup checkpoint ──
    engine.checkpoint.clear()

    # ── Reporte ──
    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report(
        "MEJORA CONTINUA v2.3 FINALIZADA",
        [
            f"Duración: {H}h {M}m {S}s",
            f"Refactor: {'sí' if refactor_ejecutado else 'no'}",
            f"Plugins pre: {result_pre.get('ok', 0) if isinstance(result_pre, dict) else 0} OK",
            f"Plugins refactor: {result_refactor.get('ok', 0) if isinstance(result_refactor, dict) else 0} OK",
            f"Plugins post: {result_post.get('ok', 0) if isinstance(result_post, dict) else 0} OK",
            f"Promocionable: {'sí' if engine.promotion.can_promote else 'no'}",
            f"Ledger: {ledger_path}",
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
