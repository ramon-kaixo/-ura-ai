#!/usr/bin/env python3
"""URA RAG query — Contexto vectorial."""

import argparse
import json
import sys

from core.memory_engine import get_sources, query


def run_query(text: str, top_k: int, json_out: bool, sources_only: bool) -> int:
    """Ejecuta la consulta y retorna código de salida."""
    resultados = query(text, top_k=top_k)

    if sources_only:
        fuentes = get_sources(resultados)
        if json_out:
            print(json.dumps(fuentes, ensure_ascii=False, indent=2))
        else:
            for f in fuentes:
                print(f"{f['source']} (chunks: {f['chunks_used']})")
        return 0

    if json_out:
        print(json.dumps(resultados, ensure_ascii=False, indent=2))
    else:
        for r in resultados:
            sim = r.get("similarity", 0)
            src = r.get("source", "?")
            print(f"[{sim:.2f}] {src}: {r.get('content', '')[:200]}...")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="URA RAG query — Contexto vectorial")
    parser.add_argument("query_text", nargs="?", help="Texto de busqueda")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--sources", action="store_true", help="Mostrar fuentes unicas")
    parser.add_argument("-n", type=int, default=3, help="Numero de resultados (default: 3)")

    args = parser.parse_args(argv)

    if not args.query_text:
        parser.print_help()
        return 1

    return run_query(args.query_text, args.n, args.json, args.sources)


if __name__ == "__main__":
    sys.exit(main())
