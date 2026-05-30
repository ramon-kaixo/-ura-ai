#!/usr/bin/env python3
"""
ura_n3_search.py — Punto de entrada N3 (OpenClaw a través del sandbox).

Uso programático:

    from ura_n3_search import n3_search
    payload = await n3_search("regulación IA España 2025")

Uso CLI:

    python ura_n3_search.py "regulación IA España 2025"
    python ura_n3_search.py "regulación IA" --json --learn

Pipeline:
  1) Invoca OpenClaw a través del SandboxBridge (VM si está, host si no).
  2) Si --learn (default True), pasa la respuesta al ObservationalLearner para
     que la registre y, si llegamos al umbral, intente promover una maleta N2.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from core.ura_observational_learner import get_learner
from core.ura_sandbox_bridge import get_sandbox

logger = logging.getLogger("ura_n3_search")


async def n3_search(
    tema: str,
    *,
    contexto: str | None = None,
    learn: bool = True,
    n2_runner=None,
) -> dict[str, Any]:
    """
    Ejecuta N3 (OpenClaw) y opcionalmente registra la observación para aprendizaje.

    Devuelve un payload con:
        - tema, nivel="N3", estado, resultados, razonamiento, modelo, duracion_segundos
        - sandbox: dict con info del entorno
        - aprendizaje: dict con resultado del observational learner (si learn=True)
    """
    sandbox = get_sandbox()
    payload = await sandbox.run_openclaw(tema, contexto=contexto)
    payload["sandbox"] = sandbox.info()

    if learn and payload.get("estado") == "ok":
        try:
            learner = get_learner()
            promotion = await learner.observe(tema, payload, n2_runner=n2_runner)
            payload["aprendizaje"] = promotion.to_dict()
        except Exception as e:  # noqa: BLE001
            logger.warning("Observational learner error: %s", e)
            payload["aprendizaje"] = {"error": str(e)}
    return payload


# ----------------------------------------------------------------- CLI ------


def _print_pretty(payload: dict[str, Any]) -> None:
    print(f"Tema       : {payload.get('tema')}")
    print(f"Estado     : {payload.get('estado')}")
    print(f"Modelo     : {payload.get('modelo')}")
    print(f"Sandbox    : {payload.get('sandbox', {}).get('mode')}")
    print(f"Duración   : {payload.get('duracion_segundos')}s")
    apren = payload.get("aprendizaje") or {}
    if apren:
        promoted = apren.get("promoted")
        print(
            f"Aprendizaje: promovida={promoted} obs={apren.get('observations_count')} score_examen={apren.get('score_examen')}"
        )
    if payload.get("razonamiento"):
        print("\nRazonamiento:")
        print(payload["razonamiento"][:1500])
    print(f"\nResultados ({len(payload.get('resultados', []))}):")
    for i, r in enumerate(payload.get("resultados", [])[:15], 1):
        print(f"{i:2d}. {r.get('titulo')}")
        print(f"    {r.get('url')}")
        if r.get("snippet"):
            print(f"    {r['snippet'][:160]}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Búsqueda N3 (OpenClaw vía sandbox)")
    p.add_argument("tema")
    p.add_argument("--context", default=None)
    p.add_argument("--no-learn", action="store_true", help="No registrar para aprendizaje")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    payload = asyncio.run(n3_search(args.tema, contexto=args.context, learn=not args.no_learn))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_pretty(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
