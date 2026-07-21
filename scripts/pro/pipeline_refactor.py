#!/usr/bin/env python3
"""Pipeline de Refactorización — independiente, invocable desde mejora continua.

Uso:
    python3 scripts/pro/pipeline_refactor.py [--workers 4] [--model qwen2.5-coder:14b]
"""

from __future__ import annotations

import sys
import time

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.logger import Logger
from scripts.pro.tuneladora.snapshot import SnapshotService
from scripts.pro.worker_manager import WorkerManager


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline de Refactorización")
    parser.add_argument("--workers", type=int, default=4, help="Número de workers")
    parser.add_argument("--model", default="qwen2.5-coder:14b", help="Modelo de refactor")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout por worker (s)")
    parser.add_argument("--deep", action="store_true", help="Modo profundo (limpia snapshots)")
    args = parser.parse_args()

    config = Configuration()
    log = Logger(config.log_file)
    manager = WorkerManager(config, log)
    snapshot = SnapshotService(config.nervioso, log.info)

    log.info("=" * 55)
    log.info("  PIPELINE DE REFACTORIZACIÓN")
    log.info("=" * 55)
    log.info(f"  Workers: {args.workers}")
    log.info(f"  Modelo: {args.model}")
    log.info(f"  Timeout: {args.timeout}s")

    # ── Handshake ──
    metrics = manager.handshake()
    if metrics.get("activos", 0) == 0:
        log.warn("Sin archivos activos — puede ser un entorno limpio")

    # ── Limpieza ──
    manager.clean_temp_files()

    # ── Modo profundo ──
    if args.deep:
        snapshot.clean()
        log.info("Modo profundo: snapshots limpiados")

    # ── Ejecutar workers ──
    t0 = time.time()
    results = manager.run_workers(
        count=args.workers,
        model=args.model,
        timeout=args.timeout,
    )

    elapsed = time.time() - t0
    ok = sum(1 for r in results if r["ok"])
    err = sum(1 for r in results if not r["ok"])

    # ── Snapshot ──
    snapshot.save("ultimo_ciclo")

    # ── Reporte ──
    H = int(elapsed // 3600)
    M = int((elapsed % 3600) // 60)
    S = int(elapsed % 60)

    log.info("═" * 55)
    log.info("  INFORME DE REFACTORIZACIÓN")
    log.info("═" * 55)
    log.info(f"  Workers OK:    {ok}")
    log.info(f"  Workers ERROR: {err}")
    log.info(f"  Duración:      {H}h {M}m {S}s")
    log.info(f"  Modelo:        {args.model}")
    log.info("═" * 55)

    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
