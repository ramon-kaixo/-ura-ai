#!/usr/bin/env python3
"""
ura_n2_search.py — Punto de entrada N2 (búsqueda local con swarm de buscadores).

Uso programático:

    from ura_n2_search import n2_search
    informe = await n2_search("agentes IA en local", use_cache=True)

Uso desde CLI:

    python ura_n2_search.py "agentes IA en local"
    python ura_n2_search.py "agentes IA" --no-cache --max-results 8 --json

Pipeline:
  1) Mira si la query está en cache (`SearchCache`). Si está y no expiró → cache hit.
  2) Lanza el `SearchOrchestrator` (paralelo de los 6 buscadores N2 refactorizados).
  3) Aplica deduplicación (URL + similitud > 0.9).
  4) Persiste en cache para futuras invocaciones.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from core.buscadores.orchestrator import OrchestratorReport, get_orchestrator
from core.ura_search_cache import get_search_cache

logger = logging.getLogger("ura_n2_search")

DEFAULT_TTL_HOURS = 1  # 3600 s, según el prompt original


async def n2_search(
    query: str,
    *,
    use_cache: bool = True,
    max_results: int = 10,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> dict[str, Any]:
    """
    Búsqueda N2 unificada.

    Devuelve un diccionario serializable con:
        query, results, by_agent, duplicates_removed, agents_used,
        errors, cache_hit (bool).
    """
    cache = get_search_cache()
    if use_cache:
        cached = await cache.get(query, maleta_id="__n2_search__")
        if cached:
            payload = cached.get("results")
            if isinstance(payload, dict):
                payload = dict(payload)
                payload["cache_hit"] = True
                return payload

    orch = get_orchestrator()
    report: OrchestratorReport = await orch.search(query, max_results=max_results)
    payload = report.to_dict()
    payload["cache_hit"] = False

    if use_cache and payload.get("results"):
        await cache.put(
            query,
            payload,
            maleta_id="__n2_search__",
            score_calidad=_avg_score(payload["results"]),
            ttl_hours=ttl_hours,
        )
    return payload


def _avg_score(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    vals = [float(r.get("score_relevancia", 0.0)) for r in results]
    return round(sum(vals) / len(vals), 3)


# ----------------------------------------------------------------- CLI ------


def _print_pretty(payload: dict[str, Any]) -> None:
    print(f"Query        : {payload['query']}")
    print(f"Cache hit    : {payload.get('cache_hit')}")
    print(f"Agentes      : {payload.get('agents_used')}")
    print(f"Duplicados   : {payload.get('duplicates_removed')}")
    if payload.get("errors"):
        print(f"Errores      : {payload['errors']}")
    print(f"Resultados   : {len(payload.get('results', []))}")
    print("-" * 60)
    for i, r in enumerate(payload.get("results", [])[:20], 1):
        print(f"{i:2d}. {r.get('titulo', '(sin título)')}")
        print(f"    {r.get('url', '')}")
        snippet = r.get("snippet", "") or ""
        if snippet:
            print(f"    {snippet[:200]}")
        print()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ura_n2_search",
        description="Búsqueda N2 (swarm local de buscadores URA)",
    )
    parser.add_argument("query", help="Texto de la búsqueda")
    parser.add_argument("--no-cache", action="store_true", help="Saltar cache")
    parser.add_argument("--max-results", type=int, default=10, help="Resultados por agente")
    parser.add_argument("--ttl-hours", type=int, default=DEFAULT_TTL_HOURS, help="TTL del cache")
    parser.add_argument("--json", action="store_true", help="Salida JSON pura (machine-readable)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging detallado")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    payload = asyncio.run(
        n2_search(
            args.query,
            use_cache=not args.no_cache,
            max_results=args.max_results,
            ttl_hours=args.ttl_hours,
        )
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_pretty(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
