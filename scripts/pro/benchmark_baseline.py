#!/usr/bin/env python3
"""Run benchmark and compare against stored baseline (Fase 8 — B08).

Usage:
  python3 scripts/pro/benchmark_baseline.py              # run + compare
  python3 scripts/pro/benchmark_baseline.py --save       # run + overwrite baseline
  python3 scripts/pro/benchmark_baseline.py --compare    # compare only (no run)
  python3 scripts/pro/benchmark_baseline.py --help       # this message

Exits 0 if all targets meet baseline, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_BASELINE_FILE = Path(__file__).resolve().parent.parent.parent / "benchmark_baseline.json"
_BENCHMARK_FILE = Path(__file__).resolve().parent.parent.parent / "tests" / "benchmark_fase7.py"
_TARGET_LABELS = [
    "FTS5 1 asset",
    "FTS5 1000 assets",
    "LIKE 1000 assets",
    "FTS5 memory 10 records",
    "Lineage edge lookup",
    "Migration v13→v14",
    "E2E Fase 7 (2 docs)",
]


def _parse_results(output: str) -> dict[str, float]:
    results = {}
    for line in output.splitlines():
        for label in _TARGET_LABELS:
            if label in line and ":" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        val_str = parts[-1].strip().rstrip("ms")
                        results[label] = float(val_str)
                    except ValueError:
                        continue
    return results


def run_benchmark() -> dict[str, float]:
    result = subprocess.run(
        [sys.executable, str(_BENCHMARK_FILE), "--verbose"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return _parse_results(result.stdout)


def save_baseline(results: dict[str, float]) -> None:
    _BASELINE_FILE.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Baseline guardada: {_BASELINE_FILE}")


def load_baseline() -> dict[str, float]:
    if not _BASELINE_FILE.exists():
        return {}
    return json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))


def compare(current: dict[str, float], baseline: dict[str, float]) -> int:
    issues = 0
    print(f"\n{'=' * 60}")
    print("COMPARATIVA vs BASELINE")
    print(f"{'=' * 60}")
    print(f"{'Métrica':<30} {'Actual':>10} {'Baseline':>10} {'Diff':>10}  {'Estado'}")
    print("-" * 75)
    for label in _TARGET_LABELS:
        cur = current.get(label)
        base = baseline.get(label)
        if cur is None:
            continue
        cur_ms = f"{cur * 1000:.2f}ms" if isinstance(cur, float) else "N/A"
        if base is not None:
            base_ms = f"{base * 1000:.2f}ms"
            ratio = cur / base if base > 0 else 0
            pct = f"{(ratio - 1) * 100:+.1f}%"
            status = "✅" if ratio <= 1.1 else "⚠️" if ratio <= 1.25 else "❌"
            if ratio > 1.1:
                issues += 1
        else:
            base_ms = "—"
            pct = "—"
            status = "[+]"
        print(f"{label:<30} {cur_ms:>10} {base_ms:>10} {pct:>10}  {status}")
    print(f"\n{issues} discrepancia(s) detectada(s)")
    return 0 if issues == 0 else 1


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    save = "--save" in sys.argv
    compare_only = "--compare" in sys.argv

    if not compare_only:
        print("Ejecutando benchmark...")
        current = run_benchmark()
        print(f"\nResultados: {len(current)} métricas capturadas")
    else:
        current = load_baseline()
        if not current:
            print("No hay baseline guardada. Ejecute sin --compare primero.")
            return 1

    if save or not _BASELINE_FILE.exists():
        save_baseline(current)

    baseline = load_baseline() if _BASELINE_FILE.exists() else {}
    if baseline and not save:
        return compare(current, baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
