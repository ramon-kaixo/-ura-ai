#!/usr/bin/env python3
"""TUNELADORA DE MEJORA CONTINUA — Sistema auto-descubrible.

FLUJO AUTOMÁTICO (descubre scripts via plugin_registry):
  Fase "pre":     Validación inicial (token_screen, scanner)
  Fase "refactor": Transformación de código (poda, refactor, watchdog)
  Fase "post":    Validación final (auto_reglas, inspectores)

AGREGAR SCRIPTS SIN EDITAR ESTE ARCHIVO:
  1. Copiar PLUGIN_TEMPLATE.py → mi_script.py
  2. Editar PLUGIN = {"name": ..., "phase": ..., "timeout": ...}
  3. Ejecutar: python3 tuneladora_mejora.py
  4. El script se ejecuta automáticamente en su fase
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

from plugin_registry import discover_all, list_plugins, log, run_phase

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
LOG_DIR = Path("/tmp/tuneladora_mejora")  # noqa: S108
REPORT_FILE = LOG_DIR / f"report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 55)
    log("  TUNELADORA DE MEJORA CONTINUA (auto-descubrible)")
    log("=" * 55)

    # Obtener archivo a procesar (opcional)
    file_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--") and arg.endswith(".py"):
            file_path = arg
            break

    # Descubrir plugins
    plugins = discover_all()
    log(f"\nPlugins descubiertos: {len(plugins)}")
    list_plugins()

    reporte = {
        "tuneladora": "mejora_continua",
        "fecha": datetime.now(UTC).isoformat(),
        "plugins_total": len(plugins),
        "fases": {},
        "resultado": "pendiente",
    }

    t_inicio = time.time()

    # ── Fase pre: Validación inicial ──
    result_pre = run_phase("pre", file_path=file_path)
    reporte["fases"]["pre"] = result_pre

    if result_pre.get("_aborted_by"):
        reporte["resultado"] = f"ABORTADO en pre ({result_pre['_aborted_by']})"
        _guardar_reporte(reporte, t_inicio)
        return reporte

    # ── Fase refactor: Transformación de código ──
    result_refactor = run_phase("refactor", file_path=file_path)
    reporte["fases"]["refactor"] = result_refactor

    if result_refactor.get("_aborted_by"):
        reporte["resultado"] = f"ABORTADO en refactor ({result_refactor['_aborted_by']})"
        _guardar_reporte(reporte, t_inicio)
        return reporte

    # ── Fase post: Validación final ──
    result_post = run_phase("post", file_path=file_path)
    reporte["fases"]["post"] = result_post

    # ── Resumen ──
    reporte["resultado"] = "completado"
    _guardar_reporte(reporte, t_inicio)

    return reporte


def _guardar_reporte(reporte, t_inicio) -> None:
    t_total = time.time() - t_inicio
    reporte["tiempo_total_s"] = round(t_total, 1)

    REPORT_FILE.write_text(json.dumps(reporte, indent=2, ensure_ascii=False))
    log(f"\n{'=' * 55}")
    log("  MEJORA CONTINUA FINALIZADA")
    log(f"  Tiempo: {t_total:.1f}s")
    log(f"  Resultado: {reporte['resultado']}")
    log(f"  Reporte: {REPORT_FILE}")
    log(f"{'=' * 55}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        discover_all()
        list_plugins()
    else:
        main()
