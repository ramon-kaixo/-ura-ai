#!/usr/bin/env python3
"""Dashboard de Salud de URA — métricas del sistema completo.

Indicadores:
  - Tuneladoras (última ejecución, duración, estado)
  - Reuse Detector (recomendaciones, precisión)
  - Memoria semántica (tamaño, crecimiento)
  - ExecutionLedger (ejecuciones, tasa promoción)
  - Swarm (agentes, conflictos)
  - Aprendizaje (conocimiento activo, verificado)
  - Rendimiento (tiempo medio por objetivo)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _fmt(key: str, val) -> str:
    return f"  {key:35} {val}"


def main() -> int:  # noqa: PLR0915
    import argparse

    parser = argparse.ArgumentParser(description="URA Health Dashboard")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--all", action="store_true", help="Todos los indicadores")
    args = parser.parse_args()

    results: dict = {}

    # ── 1. ExecutionLedger ──
    ledger_dir = ROOT / ".nervioso" / "ledger"
    if ledger_dir.exists():
        ledgers = list(ledger_dir.glob("*.json"))
        results["ledger_ejecuciones"] = len(ledgers)
        if ledgers:
            sizes = [f.stat().st_size for f in ledgers]
            results["ledger_tamano_total_kb"] = round(sum(sizes) / 1024, 1)
            results["ledger_tamano_medio_kb"] = round(sum(sizes) / len(sizes) / 1024, 1)

    # ── 2. Memoria semántica ──
    memory_db = ROOT / ".nervioso" / "memory" / "semantic.db"
    if memory_db.exists():
        try:
            conn = sqlite3.connect(str(memory_db))
            results["memoria_ejecuciones"] = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
            results["memoria_plugins"] = conn.execute("SELECT COUNT(*) FROM plugin_durations").fetchone()[0]
            results["memoria_decisiones"] = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            results["memoria_objetivos"] = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
            conn.close()
        except sqlite3.OperationalError:
            pass
        results["memoria_tamano_kb"] = round(memory_db.stat().st_size / 1024, 1)

    # ── 3. Conocimiento ──
    kb_file = ROOT / ".nervioso" / "knowledge" / "knowledge.json"
    if kb_file.exists():
        try:
            kb = json.loads(kb_file.read_text(encoding="utf-8"))
            results["conocimiento_total"] = len(kb)
            results["conocimiento_activo"] = sum(1 for e in kb if e.get("status") == "active")
            results["conocimiento_deprecated"] = sum(1 for e in kb if e.get("status") == "deprecated")
            results["conocimiento_archivado"] = sum(1 for e in kb if e.get("status") == "archived")
            results["conocimiento_verificado"] = sum(1 for e in kb if e.get("verified"))
        except (json.JSONDecodeError, OSError):
            pass

    # ── 4. Reuse Detector ──
    from scripts.pro.reuse.reuse_detector import ReuseDetector

    reuse_metrics = ReuseDetector.metrics()
    results["reuse_recomendaciones"] = reuse_metrics.get("recomendaciones_emitidas", 0)
    results["reuse_tasa_aceptacion"] = reuse_metrics.get("tasa_aceptacion", 0)

    # ── 5. Calidad Gates ──
    from scripts.pro.reuse.quality_gates import QualityGates

    gates = QualityGates(ROOT)
    gates_result = gates.should_run_maintenance()
    results["gates_commits"] = gates_result["commits"]
    results["gates_lineas"] = gates_result["lines_changed"]
    results["gates_debe_ejecutar"] = gates_result["should_run"]

    # ── 6. Registros de canal ──
    log_dir = ROOT / "logs"
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        results["logs_cantidad"] = len(log_files)
        results["logs_tamano_kb"] = round(sum(f.stat().st_size for f in log_files) / 1024, 1)

    # ── 7. Swarm ──
    from scripts.pro.autonomy.goal_manager import GoalManager
    from scripts.pro.tuneladora.engine import PipelineEngine

    engine = PipelineEngine(pipeline="dashboard")
    gm = GoalManager(engine)
    goals = gm.list_all()
    results["swarm_objetivos_total"] = len(goals)
    completed = [g for g in goals if g.get("status") == "completed"]
    results["swarm_objetivos_completados"] = len(completed)
    failed = [g for g in goals if g.get("status") == "failed"]
    results["swarm_objetivos_fallidos"] = len(failed)

    # ── Output ──
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("=" * 55)
        print("  URA HEALTH DASHBOARD")
        print("=" * 55)

        print("\n── ExecutionLedger ──")
        print(_fmt("Ejecuciones", results.get("ledger_ejecuciones", "?")))
        print(_fmt("Tamaño total", f"{results.get('ledger_tamano_total_kb', '?')} KB"))

        print("\n── Memoria Semántica ──")
        print(_fmt("Ejecuciones indexadas", results.get("memoria_ejecuciones", "?")))
        print(_fmt("Plugins registrados", results.get("memoria_plugins", "?")))
        print(_fmt("Decisiones", results.get("memoria_decisiones", "?")))
        print(_fmt("Objetivos", results.get("memoria_objetivos", "?")))
        print(_fmt("Base de datos", f"{results.get('memoria_tamano_kb', '?')} KB"))

        print("\n── Conocimiento ──")
        print(_fmt("Total", results.get("conocimiento_total", "?")))
        print(_fmt("Activo", results.get("conocimiento_activo", "?")))
        print(_fmt("Deprecado", results.get("conocimiento_deprecated", "?")))
        print(_fmt("Archivado", results.get("conocimiento_archivado", "?")))
        print(_fmt("Verificado", results.get("conocimiento_verificado", "?")))

        print("\n── Reuse Detector ──")
        print(_fmt("Recomendaciones", results.get("reuse_recomendaciones", 0)))
        print(_fmt("Tasa aceptación", f"{results.get('reuse_tasa_aceptacion', 0):.0%}"))

        print("\n── Quality Gates ──")
        print(_fmt("Commits desde tag", results.get("gates_commits", "?")))
        print(_fmt("Líneas modificadas", results.get("gates_lineas", "?")))
        print(_fmt("Debe ejecutar", "SÍ" if results.get("gates_debe_ejecutar") else "NO"))

        print("\n── Swarm ──")
        print(_fmt("Objetivos total", results.get("swarm_objetivos_total", "?")))
        print(_fmt("Completados", results.get("swarm_objetivos_completados", "?")))
        print(_fmt("Fallidos", results.get("swarm_objetivos_fallidos", "?")))

        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
