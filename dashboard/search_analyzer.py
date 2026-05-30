#!/usr/bin/env python3
"""
Analizador de Búsquedas + Fábrica de Mochilas

1. ANALIZA: Un tema → lo parte en subtemas con Ollama
2. DIVIDE: Decide cuántos agentes hacen falta y qué busca cada uno
3. EJECUTA: Todos los agentes buscan en paralelo
4. EMPAQUETA: Guarda la mochila (metodología + resultados) para reutilizar
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agentes_busqueda import buscar_con_agente

logger = logging.getLogger("search_analyzer")

# Dónde guardar las mochilas
MOCHILAS_DIR = Path(__file__).parent.parent / "biblioteca" / "mochilas_busqueda"
MOCHILAS_DIR.mkdir(parents=True, exist_ok=True)


def analizar_tema(tema: str) -> dict:
    """
    FASE 1: Ollama analiza el tema y lo descompone.
    Devuelve subtemas, número de agentes necesarios, y tipos de búsqueda.
    """
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": (
                f"Eres un analizador de búsquedas. El usuario quiere investigar: '{tema}'\n\n"
                f"1. Divide este tema en 3-5 subtemas concretos para buscar.\n"
                f"2. Para cada subtema, indica qué tipo de búsqueda harías (técnica, noticias, ciencia, negocio, general).\n"
                f"3. Estima cuántos agentes de búsqueda harían falta (mínimo 2, máximo 5).\n\n"
                f"Responde en formato JSON:\n"
                f'{{"subtemas": ["sub1","sub2","sub3"], "tipos_busqueda": ["tecnico","general",...], "agentes_necesarios": 3}}'
            ),
            "stream": False,
            "options": {"temperature": 0.3, "max_tokens": 300},
        },
        timeout=30,
    )
    resp = r.json().get("response", "{}")
    try:
        # Intentar parsear JSON
        import re

        json_match = re.search(r"\{.*\}", resp, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except json.JSONDecodeError:
        pass

    # Fallback: división manual
    return {
        "subtemas": [f"{tema} fundamentos", f"{tema} avanzado", f"{tema} herramientas"],
        "tipos_busqueda": ["tecnico", "general", "tecnico"],
        "agentes_necesarios": 3,
    }


async def ejecutar_busqueda_paralela(
    tema: str, subtemas: list[str], tipos: list[str]
) -> list[dict]:
    """FASE 2 + 3: TODOS los agentes buscan EN PARALELO (asyncio.gather)."""

    async def buscar_uno(subtema: str, tipo: str) -> dict | None:
        agente_map = {
            "tecnico": "buscador-tecnico",
            "noticias": "buscador-noticias",
            "ciencia": "buscador-ciencia",
            "negocio": "buscador-negocio",
            "general": "buscador-general",
        }
        agente = agente_map.get(tipo, "buscador-general")
        try:
            r = buscar_con_agente(agente, subtema)
            if not r.get("error"):
                return {
                    "subtema": subtema,
                    "agente": agente,
                    "fuentes": r.get("fuentes", []),
                    "respuesta": r.get("respuesta", "")[:500],
                }
        except Exception as e:
            logger.warning(f"Error en {subtema}: {e}")
        return None

    # Ejecutar TODOS en paralelo
    tareas = [buscar_uno(subtemas[i], tipos[i % len(tipos)]) for i in range(len(subtemas))]
    resultados_raw = await asyncio.gather(*tareas)
    return [r for r in resultados_raw if r is not None]


def empaquetar_mochila(tema: str, analisis: dict, resultados: list[dict]) -> dict:
    """FASE 4: Guarda la mochila completa para reutilizar."""
    mochila = {
        "tema_original": tema,
        "timestamp": datetime.now(UTC).isoformat(),
        "analisis": analisis,
        "metodologia": {
            "subtemas_usados": analisis.get("subtemas", []),
            "agentes_necesarios": analisis.get("agentes_necesarios", 0),
            "tipos_busqueda": analisis.get("tipos_busqueda", []),
        },
        "resultados": resultados,
        "total_fuentes": sum(len(r.get("fuentes", [])) for r in resultados),
    }

    # Guardar en disco
    filename = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M')}_{tema[:40].replace(' ', '_')}.json"
    filepath = MOCHILAS_DIR / filename
    with open(filepath, "w") as f:
        json.dump(mochila, f, ensure_ascii=False, indent=2)

    return mochila


async def investigar_con_mochila(tema: str) -> dict:
    """Pipeline completo: Analizar → Dividir → Ejecutar → Empaquetar."""
    # 1. Analizar
    logger.info(f"🔍 Analizando tema: {tema}")
    analisis = analizar_tema(tema)

    # 2-3. Ejecutar en paralelo
    subtemas = analisis.get("subtemas", [])
    tipos = analisis.get("tipos_busqueda", [])
    logger.info(f"📋 Dividido en {len(subtemas)} subtemas con {len(tipos)} tipos de búsqueda")

    resultados = await ejecutar_busqueda_paralela(tema, subtemas, tipos)

    # 4. Empaquetar mochila
    mochila = empaquetar_mochila(tema, analisis, resultados)
    logger.info(f"🎒 Mochila guardada: {mochila['total_fuentes']} fuentes")

    return mochila


def listar_mochilas() -> list[dict]:
    """Lista todas las mochilas guardadas."""
    mochilas = []
    for f in sorted(MOCHILAS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
                mochilas.append(
                    {
                        "archivo": f.name,
                        "tema": data.get("tema_original", "")[:80],
                        "fecha": data.get("timestamp", ""),
                        "fuentes": data.get("total_fuentes", 0),
                        "subtemas": len(data.get("resultados", [])),
                    }
                )
        except Exception:
            pass
    return mochilas[:10]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    # Probar con un tema de ejemplo
    tema = "agentes IA para automatización de restaurantes"
    print(f"🔬 Investigando: {tema}")
    print()

    mochila = asyncio.run(investigar_con_mochila(tema))

    print("\n✅ Mochila creada:")
    print(f"   Tema: {mochila['tema_original']}")
    print(f"   Subtemas: {len(mochila['metodologia']['subtemas_usados'])}")
    print(f"   Agentes usados: {mochila['metodologia']['agentes_necesarios']}")
    print(f"   Total fuentes: {mochila['total_fuentes']}")

    print(f"\n📚 Mochilas guardadas: {len(listar_mochilas())}")
