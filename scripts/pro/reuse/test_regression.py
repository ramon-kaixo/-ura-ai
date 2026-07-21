#!/usr/bin/env python3
"""Regression tests para el Reuse Detector.

Estas consultas nunca deberían romperse. Cada vez que cambie el algoritmo
de similitud, ejecutar este script para verificar que no hay regresiones.
Construye el índice una sola vez para rendimiento.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
_detector = None


def get_detector():
    global _detector
    if _detector is None:
        from scripts.pro.reuse.reuse_detector import ReuseDetector
        _detector = ReuseDetector(ROOT)
        print("  Indexando...")
        t0 = time.time()
        _detector.build_index()
        print(f"  {len(_detector._index)} funciones en {time.time()-t0:.1f}s")
    return _detector


REGRESSION_TESTS = [
    ("run_ruff", 1, 0.4, "Encontrar run_ruff (exacta)"),
    ("ruff", 3, 0.4, "Encontrar funciones con 'ruff'"),
    ("main", 5, 0.4, "Encontrar funciones main"),
    ("PipelineEngine", 1, 0.4, "Encontrar PipelineEngine"),
    ("ExecutionLedger", 1, 0.4, "Encontrar ExecutionLedger"),
    ("GoalManager", 1, 0.4, "Encontrar GoalManager"),
    ("Planner", 1, 0.4, "Encontrar Planner"),
    ("Evaluator", 1, 0.4, "Encontrar Evaluator"),
    ("save", 5, 0.4, "Encontrar funciones save"),
    ("execute", 3, 0.4, "Encontrar funciones execute"),
    ("load", 3, 0.4, "Encontrar funciones load"),
    ("run", 10, 0.4, "Encontrar funciones run"),
]


def main() -> int:
    passed = 0
    failed = 0

    d = get_detector()
    for name, min_results, min_score, desc in REGRESSION_TESTS:
        try:
            results = d.search(name, min_score=min_score)
            if results and len(results) >= min_results:
                best = results[0]
                print(f"  ✅ {desc}: {len(results)} resultados (mejor: {best['existing_name']} @ {best['score']:.0%})")
                passed += 1
            else:
                print(f"  ❌ {desc}: 0 resultados (esperados ≥{min_results})")
                failed += 1
        except Exception as e:
            print(f"  ❌ {desc}: error ({e})")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed de {len(REGRESSION_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
