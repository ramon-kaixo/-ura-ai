#!/usr/bin/env python3
"""Tuneladora de Mantenimiento — health checks, limpieza, validaciones.

Nunca modifica código del proyecto.
Usa PipelineEngine + plugins (misma base que mejora continua).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

from motor.observability import HealthRegistry
from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin
from scripts.pro.tuneladora.plugins.code_quality import CodeQualityPlugin
from scripts.pro.tuneladora.plugins.health import HealthPlugin
from scripts.pro.tuneladora.plugins.reporting import ReportingPlugin

_HEALTH_STATE_FILE = "/tmp/ura_tuneladora_health.json"
_health = HealthRegistry()


def _persist_health() -> None:
    try:
        with open(_HEALTH_STATE_FILE, "w") as f:
            json.dump(_health.snapshot(), f)
    except Exception as e:
        _log = __import__("logging").getLogger("ura.tuneladora.mantenimiento")
        _log.warning("health persist failed: %s", e)


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

    _health.register_component("tuneladora")
    _health.set_healthy("tuneladora", f"iniciando mantenimiento nivel {nivel}")

    engine.log.info("=" * 55)
    engine.log.info(f"  MANTENIMIENTO — Nivel: {nivel.upper()}")
    engine.log.info("=" * 55)

    t0 = time.time()
    results: dict = {}

    # ── Preflight: Health checks (todos los niveles) ──
    engine.log.info("── Preflight: Health checks ──")
    results["health"] = health.check_all()
    hr = results.get("health", {})
    ollama_ok = hr.get("ollama", {}).get("ok", False)
    if not ollama_ok:
        _health.set_degraded("tuneladora", "Ollama no disponible en preflight")
    _persist_health()

    # ── Ligero: salud + logs + disco ──
    engine.log.info("── Mantenimiento ligero ──")
    results["health"] = health.check_all()
    results["disk"] = cleanup.check_disk()
    results["logs"] = cleanup.cleanup_logs()

    # ── Medio: embeddings + vacuum + calidad ──
    if nivel in ("medio", "profundo"):
        engine.log.info("── Mantenimiento medio ──")
        results["embeddings"] = cleanup.cleanup_embeddings()
        results["vacuum"] = cleanup.vacuum_sqlite()
        quality.ruff_check("F841,F401")
        quality.ruff_format()
        f821 = quality.ruff_check("F821")
        results["f821"] = f821
        quality.ruff_fix()

    # ── Profundo: duplicados, deuda, forense, auditoria, git ──
    if nivel == "profundo":
        engine.log.info("── Mantenimiento profundo ──")
        results["ollama"] = {"modelos": len(engine.health_ollama())}
        results["forense"] = cleanup.forense_aislamientos()
        results["duplicates"] = cleanup.detect_duplicates()
        results["debt"] = cleanup.tech_debt_report()
        quality.f821_snapshot("pre-mantenimiento")
        results["ruff_profundo"] = quality.ruff_fix(unsafe=True)
        results["auditoria"] = cleanup.auditoria(profundo=True)

        # Git: commit si auditoria ok, rollback si no
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

    current = _health.get_status("tuneladora")
    if current != "degraded":
        _health.set_healthy("tuneladora", f"mantenimiento {nivel} completado en {H}h{M}m{S}s")
    _persist_health()
    return 0


if __name__ == "__main__":
    sys.exit(main())
