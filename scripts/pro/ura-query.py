import argparse
import json
import sys

from core.memory_engine import MemoryEngine, get_sources


def main():
    parser = argparse.ArgumentParser(description="URA RAG query — Contexto vectorial")
    parser.add_argument("query", nargs="?", help="Texto de busqueda")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--sources", action="store_true", help="Mostrar fuentes unicas")
    parser.add_argument("-n", type=int, default=3, help="Numero de resultados (default: 3)")

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    me = MemoryEngine()
    resultados = me.query(args.query, n_results=args.n)

    if args.sources:
        fuentes = get_sources(resultados)
        if args.json:
            print(json.dumps(fuentes, indent=2, ensure_ascii=False))
        else:
            for s in fuentes:
                print(f"  [{s['chunks_used']} chunks] {s['source']}")
        return

    if args.json:
        print(json.dumps(resultados, indent=2, ensure_ascii=False))
    else:
        for r in resultados:
            sim = r.get("similarity", 0)
            src = r.get("source", "?")
            print(f"[sim={sim:.3f}] {src}: {r.get('content', '')[:120]}...")


if __name__ == "__main__":
    main()
