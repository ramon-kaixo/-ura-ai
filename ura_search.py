#!/usr/bin/env python3
"""
ura_search.py — Punto de entrada UNIFICADO (N1/N2/N3 via NivelRouter).

Este es el endpoint que debes usar desde cualquier punto del proyecto que
necesite hacer una búsqueda inteligente:

    from ura_search import unified_search
    payload = await unified_search("cuota autónomos 2025")

Pipeline:
    1) NivelRouter decide el nivel (N1 / N2 / N2+N3 / N3) según confianza
       de la maleta y el historial de uso.
    2) Despacha a la implementación correspondiente:
        - N3       → ura_n3_search.n3_search (OpenClaw vía sandbox)
        - N2+N3    → N2 responde al usuario, N3 corre en paralelo y aprende
        - N2       → ura_n2_search.n2_search
        - N1       → (todavía no exportado a n8n) cae a N2 con flag
    3) Si la decisión incluye N3, se observa la salida para aprendizaje
       (Observational Learner — promueve maletas tras 10 ejecuciones + examen).
    4) Cuando N2 termina con confianza ≥ 0.95 y uses ≥ 20, sugiere exportar a N1.

CLI:
    python ura_search.py "cuota autónomos 2025"
    python ura_search.py "tema X" --maleta fiscal_autonomos_es_v1 --json
    python ura_search.py "tema Y" --force-level N3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from core.ura_nivel_router import Nivel, get_router

import ura_n2_search
import ura_n3_search

logger = logging.getLogger("ura_search")


# -----------------------------------------------------------------------------
# N2 runner usado por el observational learner: ejecuta una maleta candidata.
# Se le pasa al learner en cada ejecución de N3 para que pueda hacer el examen
# de validación (lanzar N2 con la maleta y comparar contra la salida N3).
# -----------------------------------------------------------------------------


async def _n2_runner_for_exam(tema: str, maleta_data: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta N2 con la maleta candidata. Devuelve un informe compatible con
    el formato esperado por el learner (tiene clave `results` o
    `resultados_por_agente`).
    """
    payload = await ura_n2_search.n2_search(tema, use_cache=False, max_results=10)
    return payload


# -----------------------------------------------------------------------------
# Unified search
# -----------------------------------------------------------------------------


async def unified_search(
    tema: str,
    *,
    maleta_id: str | None = None,
    force_level: str | None = None,
    contexto: str | None = None,
) -> dict[str, Any]:
    """Búsqueda unificada con routing automático N1/N2/N3."""
    router = get_router()
    if force_level:
        decision_nivel = _parse_level(force_level)
        decision = type("ForcedDecision", (), {})()
        decision.nivel = decision_nivel
        decision.maleta_id = maleta_id
        decision.confianza = 0.0
        decision.uses = 0
        decision.razon = f"Forzado por --force-level={force_level}"
        decision.sugerencias = []
        decision.clonada = False
        decision_dict = {
            "nivel": decision_nivel.value,
            "maleta_id": maleta_id,
            "confianza": 0.0,
            "uses": 0,
            "razon": decision.razon,
            "sugerencias": [],
            "clonada": False,
        }
    else:
        decision = await router.decide(tema, maleta_id=maleta_id)
        decision_dict = decision.to_dict()

    nivel = decision.nivel
    output: dict[str, Any] = {
        "tema": tema,
        "decision": decision_dict,
    }

    if nivel == Nivel.N3:
        n3_payload = await ura_n3_search.n3_search(
            tema,
            contexto=contexto,
            learn=True,
            n2_runner=_n2_runner_for_exam,
        )
        output["nivel_ejecutado"] = "N3"
        output["n3"] = n3_payload
        output["resultados"] = n3_payload.get("resultados", [])

    elif nivel == Nivel.N2_N3:
        # N2 responde rápido para el usuario; N3 audita en background y aprende.
        n2_task = asyncio.create_task(ura_n2_search.n2_search(tema, use_cache=True, max_results=10))
        n3_task = asyncio.create_task(
            ura_n3_search.n3_search(
                tema, contexto=contexto, learn=True, n2_runner=_n2_runner_for_exam
            )
        )
        n2_payload = await n2_task
        # Esperamos N3 sólo si termina pronto, sino lo dejamos en background
        try:
            n3_payload = await asyncio.wait_for(asyncio.shield(n3_task), timeout=2)
        except TimeoutError:
            n3_payload = {"estado": "background", "razon": "N3 sigue ejecutándose"}
        output["nivel_ejecutado"] = "N2+N3"
        output["n2"] = n2_payload
        output["n3"] = n3_payload
        output["resultados"] = n2_payload.get("results", [])

    elif nivel == Nivel.N2:
        n2_payload = await ura_n2_search.n2_search(tema, use_cache=True, max_results=10)
        output["nivel_ejecutado"] = "N2"
        output["n2"] = n2_payload
        output["resultados"] = n2_payload.get("results", [])

    elif nivel == Nivel.N1:
        # Pendiente exportar a n8n — por ahora caemos a N2 con flag
        n2_payload = await ura_n2_search.n2_search(tema, use_cache=True, max_results=10)
        output["nivel_ejecutado"] = "N2 (pendiente export N1)"
        output["n2"] = n2_payload
        output["resultados"] = n2_payload.get("results", [])

    # Registrar uso si hay maleta
    if decision.maleta_id and not force_level:
        try:
            await router.record_execution(decision.maleta_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo registrar uso: %s", e)

    return output


def _parse_level(s: str) -> Nivel:
    s = s.upper().strip()
    mapping = {"N1": Nivel.N1, "N2": Nivel.N2, "N3": Nivel.N3, "N2+N3": Nivel.N2_N3}
    if s not in mapping:
        raise ValueError(f"Nivel no válido: {s}. Usa N1, N2, N2+N3, N3.")
    return mapping[s]


# ----------------------------------------------------------------- CLI ------


def _print_pretty(payload: dict[str, Any]) -> None:
    dec = payload.get("decision", {})
    print(f"Tema             : {payload.get('tema')}")
    print(f"Nivel decidido   : {dec.get('nivel')}")
    print(f"Maleta           : {dec.get('maleta_id')}")
    print(f"Confianza        : {dec.get('confianza')}")
    print(f"Uses             : {dec.get('uses')}")
    print(f"Razón            : {dec.get('razon')}")
    if dec.get("sugerencias"):
        print(f"Sugerencias      : {dec['sugerencias']}")
    print(f"Nivel ejecutado  : {payload.get('nivel_ejecutado')}")
    print(f"Resultados       : {len(payload.get('resultados', []))}")
    print()
    for i, r in enumerate(payload.get("resultados", [])[:10], 1):
        title = r.get("titulo") or r.get("title")
        url = r.get("url")
        print(f"{i:2d}. {title}")
        print(f"    {url}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Búsqueda unificada URA (N1/N2/N3)")
    p.add_argument("tema")
    p.add_argument("--maleta", default=None, help="ID de maleta a usar")
    p.add_argument("--force-level", default=None, help="N1 | N2 | N2+N3 | N3")
    p.add_argument("--context", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    payload = asyncio.run(
        unified_search(
            args.tema,
            maleta_id=args.maleta,
            force_level=args.force_level,
            contexto=args.context,
        )
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_pretty(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
