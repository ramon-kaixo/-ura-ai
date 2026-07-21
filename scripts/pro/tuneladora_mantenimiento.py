#!/usr/bin/env python3
"""Tuneladora de Mantenimiento — health checks, limpieza, validaciones.

Nunca modifica código del proyecto.
Usa PipelineEngine + plugins (misma base que mejora continua).
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin
from scripts.pro.tuneladora.plugins.code_quality import CodeQualityPlugin
from scripts.pro.tuneladora.plugins.health import HealthPlugin
from scripts.pro.tuneladora.plugins.reporting import ReportingPlugin


def _detectar_nivel() -> str:
    """Determina el nivel de mantenimiento según hora/día."""
    now = datetime.now(UTC)
    hora, dia = now.hour, now.weekday()
    if dia == 0 and 2 <= hora <= 4:
        return "profundo"
    if hora in (6, 12, 18):
        return "medio"
    return "ligero"


def main() -> int:  # noqa: PLR0915
    import argparse

    parser = argparse.ArgumentParser(description="Tuneladora de Mantenimiento")
    parser.add_argument("--nivel", choices=["ligero", "medio", "profundo"], default=None)
    parser.add_argument("--force", action="store_true", help="Ignorar nivel, ejecutar todo")
    args = parser.parse_args()

    engine = PipelineEngine()
    health = HealthPlugin(engine)
    quality = CodeQualityPlugin(engine)
    cleanup = CleanupPlugin(engine)
    reporting = ReportingPlugin(engine)

    nivel = args.nivel or _detectar_nivel()
    if args.force:
        nivel = "profundo"

    engine.log.info("=" * 55)
    engine.log.info(f"  MANTENIMIENTO — Nivel: {nivel.upper()}")
    engine.log.info("=" * 55)

    t0 = time.time()
    results: dict = {}

    # ── Preflight: Health checks (todos los niveles) ──
    engine.log.info("── Preflight: Health checks ──")
    results["health"] = health.check_all()

    # ── Ligero: calidad básica ──
    engine.log.info("── Calidad básica ──")
    results["token_screen"] = quality.token_screen()
    quality.scanner(mode="json")
    quality.ruff_check("F841,F401")
    quality.ruff_format()
    f821 = quality.ruff_check("F821")
    results["f821"] = f821
    quality.compactadora()
    quality.scanner(mode="diff")

    # ── Medio: añade poda, inspectores, orphan scanner ──
    if nivel in ("medio", "profundo"):
        engine.log.info("── Calidad media ──")
        results["orphan_scanner"] = engine.run_script(
            "scripts/pro/systemd_orphan_scanner.py", args=["--json"], timeout=30
        ).returncode
        quality.ruff_fix()
        quality.poda()
        results["inspectores"] = quality.inspectores()

    # ── Profundo: refactor, forense, snapshot, auditoria, git ──
    if nivel == "profundo":
        engine.log.info("── Mantenimiento profundo ──")
        results["ollama"] = {"modelos": len(engine.health_ollama())}
        results["forense"] = cleanup.forense_aislamientos()
        quality.f821_snapshot("pre-mantenimiento")

        results["ruff_profundo"] = quality.ruff_fix(unsafe=True)

        # Auditoría
        results["auditoria"] = cleanup.auditoria(profundo=True)

        # Git: commit si auditoría ok, rollback si no
        aud = results.get("auditoria", {})
        if aud.get("bloqueante"):
            cleanup.git_rollback()
            results["git"] = "rollback_by_auditor"
        else:
            commit_ok = cleanup.git_commit()
            if commit_ok["ok"]:
                f821_post = quality.f821_compare("pre-mantenimiento")
                results["f821_post"] = f821_post
                results["git"] = "committed" if f821_post["ok"] else "rollback_f821"
            else:
                results["git"] = "no_changes"

    # ── Reporte ──
    elapsed = time.time() - t0
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    engine.log.report(
        "INFORME DE MANTENIMIENTO",
        [
            f"Nivel: {nivel.upper()}",
            f"Duración: {H}h {M}m {S}s",
        ],
    )
    reporting.save_maintenance_state(results, nivel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
