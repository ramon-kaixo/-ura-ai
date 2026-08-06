#!/usr/bin/env python3
"""Reuse Detector — busca código duplicado antes de crear código nuevo.

Uso:
  python3 scripts/pro/reuse/reuse.py index             → indexar el proyecto
  python3 scripts/pro/reuse/reuse.py search "load_config"  → buscar similitudes
  python3 scripts/pro/reuse/reuse.py check archivo.py  → analizar código nuevo
  python3 scripts/pro/reuse/reuse.py gates             → verificar quality gates
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.pro.reuse.quality_gates import QualityGates
from scripts.pro.reuse.reuse_detector import ReuseDetector


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Reuse Detector + Quality Gates")
    parser.add_argument("action", choices=["index", "search", "check", "gates"], help="Acción a ejecutar")
    parser.add_argument("target", nargs="?", default="", help="Nombre o archivo a buscar")
    parser.add_argument("--min-score", type=float, default=0.4, help="Score mínimo (0-1)")
    parser.add_argument("--commit-threshold", type=int, default=10)
    parser.add_argument("--lines-threshold", type=int, default=2000)
    args = parser.parse_args()

    root = Path(__file__).parent.parent.parent

    if args.action == "gates":
        gates = QualityGates(root)
        result = gates.should_run_maintenance(
            commit_threshold=args.commit_threshold,
            lines_threshold=args.lines_threshold,
        )
        print(f"Commits desde último tag: {result['commits']}")
        print(f"Líneas modificadas: {result['lines_changed']}")
        print(f"¿Ejecutar pipeline?: {'SÍ' if result['should_run'] else 'NO'}")
        for r in result["reasons"]:
            print(f"  Motivo: {r}")
        return 0 if not result["should_run"] else 1

    detector = ReuseDetector(root)

    if args.action == "index":
        count = detector.build_index()
        print(f"Indexadas {count} funciones/clases en {root}")
        return 0

    if args.action == "search" and args.target:
        detector.build_index()
        results = detector.search(args.target, min_score=args.min_score)
        if results:
            print(f"Coincidencias para '{args.target}':")
            for r in results:
                print(
                    f"  {r['categoria']:10} score={r['score']:.0%}  {r['existing_name']:30} {r['existing_file']}:{r['existing_line']}"
                )
        else:
            print(f"Sin coincidencias para '{args.target}'")
        return 0

    if args.action == "check" and args.target:
        detector.build_index()
        code = Path(args.target).read_text(encoding="utf-8")
        results = detector.analyze_new_code(code, min_score=args.min_score)
        if results:
            print(f"Posible duplicación en {args.target}:")
            for r in results:
                cat = r.get("categoria_desc", r["categoria"])
                print(
                    f"  {r['categoria']:10} score={r['score']:.0%}  → {r['existing_name']:30} {r['existing_file']}:{r['existing_line']}"
                )
                print(f"    {cat}")
        else:
            print(f"Sin duplicación detectada en {args.target}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
