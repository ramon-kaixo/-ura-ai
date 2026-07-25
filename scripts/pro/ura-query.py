import argparse  # noqa: INP001
import sys

from core.memory_engine import get_sources, query


def main() -> None:
    parser = argparse.ArgumentParser(description="URA RAG query — Contexto vectorial")
    parser.add_argument("query", nargs="?", help="Texto de busqueda")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--sources", action="store_true", help="Mostrar fuentes unicas")
    parser.add_argument("-n", type=int, default=3, help="Numero de resultados (default: 3)")

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    resultados = query(args.query, top_k=args.n)

    if args.sources:
        fuentes = get_sources(resultados)
        if args.json:
            pass
        else:
            for _s in fuentes:
                pass
        return

    if args.json:
        pass
    else:
        for r in resultados:
            r.get("similarity", 0)
            r.get("source", "?")


if __name__ == "__main__":
    main()
