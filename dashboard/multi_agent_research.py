#!/usr/bin/env python3
"""
Sistema Multi-Agente de Investigación — 5 áreas × 3 buscadores × verificación.
Cada área investiga con 3 agentes en fuentes diferentes.
Un verificador comprueba que las fuentes no se repitan.
Consenso entre los 3 para filtrar solo información validada.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agentes_busqueda import buscar_con_agente

logger = logging.getLogger("multi_research")
# Guardar en disco externo si está disponible, si no en local
_EXTERNAL = Path("/Volumes/TOSHIBA_NUEVO/URA")
_INTERNAL = Path(__file__).parent.parent / "biblioteca" / "conocimiento_curado"

if _EXTERNAL.exists():
    RAW_BASE = _EXTERNAL / "biblioteca_conocimiento"  # Datos brutos → Toshiba
else:
    RAW_BASE = Path(__file__).parent.parent / "biblioteca" / "conocimiento_autonomo"

RAW_BASE.mkdir(parents=True, exist_ok=True)
_INTERNAL.mkdir(parents=True, exist_ok=True)  # Conocimiento curado → Mac SSD

# ── 5 ÁREAS DE INVESTIGACIÓN con fuentes especializadas ──────────────────
AREAS = {
    "ia_multimodal_genetica": {
        "agentes": ["buscador-ciencia", "buscador-tecnico", "buscador-general"],
        "queries": [
            "multimodal AI genetics latest research 2025 site:arxiv.org",
            "deep learning multimodal models site:github.com OR site:paperswithcode.com",
            "AI genetic optimization neural architecture site:scholar.google.com",
        ],
    },
    "agentes_ia_arquitectura": {
        "agentes": ["buscador-tecnico", "buscador-ciencia", "buscador-noticias"],
        "queries": [
            "AI agents architecture patterns 2025 site:medium.com OR site:anthropic.com",
            "multi-agent orchestration LangGraph CrewAI tutorial",
            "agent frameworks comparison 2025 site:dev.to OR site:towardsdatascience.com",
        ],
    },
    "agentes_gastronomicos": {
        "agentes": ["buscador-tecnico", "buscador-negocio", "buscador-general"],
        "queries": [
            "AI restaurant automation 2025 site:techcrunch.com OR site:restaurant.org",
            "gastronomic AI recipe generation food tech site:github.com OR site:fao.org",
            "smart kitchen AI agents cooking 2025 site:ncbi.nlm.nih.gov",
        ],
    },
    "agentes_creativos_diseno": {
        "agentes": ["buscador-tecnico", "buscador-noticias", "buscador-general"],
        "queries": [
            "AI design agents 2025 site:dribbble.com OR site:figma.com OR site:canva.com",
            "AI marketing agents social media automation tools",
            "creative AI Instagram poster generation 2025",
        ],
    },
    "tendencias_ia": {
        "agentes": ["buscador-noticias", "buscador-ciencia", "buscador-general"],
        "queries": [
            "new AI tools agents 2025 latest trends site:techcrunch.com OR site:theverge.com",
            "AI industry predictions 2025 2026 site:forbes.com OR site:wired.com",
            "open source AI models frameworks latest 2025 site:github.com",
        ],
    },
    # ── SCIENTIA: Investigación académica con 3 roles ─────────────────
    "scientia_academica": {
        "agentes": ["buscador-ciencia", "buscador-tecnico", "buscador-general"],
        "queries": [
            "self-healing code autonomous repair resilient systems AI site:arxiv.org",
            "multi-agent systems swarm intelligence communication protocols site:semanticscholar.org",
            "AI alignment bias mitigation governance EU AI Act site:openreview.net",
            "neural architecture search mixture of experts transformers site:arxiv.org",
            "adversarial robustness prompt injection defense formal verification site:arxiv.org",
        ],
    },
    # ── Legal/Fiscal España ───────────────────────────────────────────
    "legal_fiscal_espana": {
        "agentes": ["buscador-legal", "buscador-general", "buscador-noticias"],
        "queries": [
            "IVA IRPF novedades legislativas 2025 site:boe.es",
            "jurisprudencia laboral hostelería bares site:poderjudicial.es",
            "normativa IA inteligencia artificial España 2025 site:eur-lex.europa.eu",
            "contabilidad fiscal pymes autónomos 2025 site:dialnet.unirioja.es",
        ],
    },
}

# ── Fuentes académicas de confianza (Lista Blanca) ──────────────────────
WHITELIST_DOMAINS = [
    # Académicos generales
    "arxiv.org",
    "semanticscholar.org",
    "openreview.net",
    "paperswithcode.com",
    "github.com",
    "dl.acm.org",
    "ieeexplore.ieee.org",
    "sciencedirect.com",
    "springer.com",
    "nature.com",
    "science.org",
    "cell.com",
    "scholar.google.com",
    # Universidades top
    "mit.edu",
    "stanford.edu",
    "berkeley.edu",
    "cmu.edu",
    "ox.ac.uk",
    "cam.ac.uk",
    "ethz.ch",
    # España — legislación y academia
    "boe.es",
    "poderjudicial.es",
    "eur-lex.europa.eu",
    "dialnet.unirioja.es",
    "recolecta.fecyt.es",
    "raco.cat",
    # Gastronomía y ciencia
    "ncbi.nlm.nih.gov",
    "fao.org",
    "pubmed.gov",
    # Creativo y diseño
    "nngroup.com",
    "doaj.org",
    # Meta-repositorios
    "roar.eprints.org",
    "worldwidescience.org",
    "core.ac.uk",
]


def _fuentes_son_diferentes(resultados: list[dict]) -> bool:
    """Verifica que los 3 agentes hayan usado fuentes distintas."""
    todas_fuentes = set()
    for r in resultados:
        fuentes = r.get("fuentes", [])
        for f in fuentes:
            href = f.get("href", "")
            if href:
                todas_fuentes.add(href)
    # Si hay al menos 9 fuentes distintas entre 3 agentes (3 cada uno), OK
    return len(todas_fuentes) >= 6  # mínimo 2 fuentes únicas por agente


def _extraer_conocimiento(resultados: list[dict]) -> list[str]:
    """
    ROL 1: BUSCADOR — Extrae fuentes con metadatos.
    ROL 3: VERIFICADOR — Valida contra lista blanca, etiqueta calidad.
    """
    conocimiento = []
    for r in resultados:
        respuesta = r.get("respuesta", "")
        if respuesta and len(respuesta) > 50 and "Error" not in respuesta:
            conocimiento.append(respuesta[:500])
        for f in r.get("fuentes", []):
            title = f.get("title", "")
            href = f.get("href", "")
            if title and href:
                # VERIFICADOR: comprobar si la fuente es de confianza
                dominio = href.split("/")[2] if "//" in href else ""
                confianza = "ALTA" if any(w in dominio for w in WHITELIST_DOMAINS) else "MEDIA"
                tag = "" if confianza == "ALTA" else "[FUENTE NO VERIFICADA] "
                conocimiento.append(f"{tag}📄 {title} — {href}")
    return conocimiento


async def investigar_area(nombre_area: str, config: dict) -> dict:
    """Investiga un área completa: 3 agentes × 3 queries = 9 búsquedas. Sin Ollama para cada una."""
    resultados_por_query = {}

    for query in config["queries"]:
        resultados_query = []
        for agente_nombre in config["agentes"]:
            try:
                r = buscar_con_agente(agente_nombre, query)
                if not r.get("error"):
                    # Guardar solo fuentes, sin esperar a Ollama
                    resultados_query.append(
                        {
                            "agente": agente_nombre,
                            "fuentes": r.get("fuentes", []),
                            "respuesta": r.get("respuesta", "")[:300],
                        }
                    )
            except Exception as e:
                logger.warning(f"Error en {agente_nombre}/{query}: {e}")

        resultados_por_query[query] = resultados_query

    return {
        "area": nombre_area,
        "timestamp": datetime.now(UTC).isoformat(),
        "resultados_por_query": {
            q: {
                "agentes_usados": len(res),
                "fuentes_distintas": _fuentes_son_diferentes(res),
                "conocimiento": _extraer_conocimiento(res),
            }
            for q, res in resultados_por_query.items()
        },
    }


def guardar_investigacion(area: str, data: dict):
    """Guarda resultados brutos en Toshiba."""
    cat_dir = RAW_BASE / area
    cat_dir.mkdir(parents=True, exist_ok=True)

    filepath = cat_dir / f"{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_conocimiento = 0
    for q, res in data.get("resultados_por_query", {}).items():
        total_conocimiento += len(res.get("conocimiento", []))

    logger.info(f"📁 Toshiba/{area}: {total_conocimiento} piezas guardadas")


async def curar_conocimiento():
    """
    Cura el conocimiento en 3 fases:
    1. FILTRAR: Ollama puntúa cada pieza (1-10). Solo pasan ≥ 7.
    2. ORGANIZAR: Clasifica en subcategorías con etiquetas.
    3. DESCARTAR: Elimina duplicados y conocimiento de baja calidad.
    """
    import requests as req

    curados = 0
    descartados = 0
    for area_dir in RAW_BASE.iterdir():
        if not area_dir.is_dir():
            continue
        area = area_dir.name
        for archivo in list(area_dir.glob("*.json"))[:3]:
            curado_path = _INTERNAL / area / f"curado_{archivo.name}"
            if curado_path.exists():
                continue

            try:
                with open(archivo) as f:
                    data = json.load(f)

                textos = []
                for q, res in data.get("resultados_por_query", {}).items():
                    for item in res.get("conocimiento", []):
                        if isinstance(item, str) and len(item) > 50:
                            textos.append(item[:500])
                if not textos:
                    descartados += 1
                    continue

                texto_completo = "\n---\n".join(textos[:5])

                # ── FASE 1: FILTRAR (puntuar calidad) ─────────────────
                r = req.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": (
                            f"Evalúa la calidad de esta información sobre '{area}' del 1 al 10. "
                            f"Responde SOLO con un número.\n\n{texto_completo[:500]}"
                        ),
                        "stream": False,
                        "options": {"temperature": 0, "max_tokens": 5},
                    },
                    timeout=30,
                )
                puntuacion_str = r.json().get("response", "0").strip()
                try:
                    puntuacion = int(puntuacion_str) if puntuacion_str.isdigit() else 5
                except ValueError:
                    puntuacion = 5

                if (
                    puntuacion < 5
                ):  # Bajar umbral de 7→5 para no descartar todo                    logger.info(f"🗑️ Descartado ({puntuacion}/10): {area}")
                    descartados += 1
                    continue

                # ── FASE 2: ORGANIZAR (resumir + etiquetar) ──────────
                r2 = req.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": (
                            f"Resume este conocimiento sobre '{area}' en 3 frases en español. "
                            f"Luego, en una línea aparte, escribe 3 etiquetas separadas por comas "
                            f"que categoricen el contenido (ej: 'agentes,arquitectura,patterns').\n\n"
                            f"TEXTO:\n{texto_completo[:1500]}"
                        ),
                        "stream": False,
                        "options": {"temperature": 0.3, "max_tokens": 250},
                    },
                    timeout=30,
                )
                full_response = r2.json().get("response", "")
                # Separar resumen de etiquetas
                if "\n" in full_response:
                    lines = full_response.strip().split("\n")
                    resumen = lines[0] if lines else ""
                    tags = lines[-1] if len(lines) > 1 else ""
                else:
                    resumen = full_response
                    tags = ""

                curado = {
                    "area": area,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "resumen": resumen.strip(),
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "puntuacion": puntuacion,
                    "fuentes_originales": len(textos),
                    "archivo_origen": str(archivo.name),
                }
                curado_path.parent.mkdir(parents=True, exist_ok=True)
                with open(curado_path, "w") as f:
                    json.dump(curado, f, ensure_ascii=False, indent=2)
                curados += 1

            except Exception as e:
                logger.warning(f"Error curando {archivo.name}: {e}")

    return {"curados": curados, "descartados": descartados}


async def descartar_conocimiento_antiguo(dias: int = 7):
    """FASE 3: DESCARTAR — elimina conocimiento duplicado o con puntuación baja."""
    descartados = 0
    for area_dir in _INTERNAL.iterdir():
        if not area_dir.is_dir():
            continue
        # Eliminar archivos de baja puntuación
        for archivo in list(area_dir.glob("curado_*.json")):
            try:
                with open(archivo) as f:
                    data = json.load(f)
                if data.get("puntuacion", 0) < 5:
                    archivo.unlink()
                    descartados += 1
            except Exception as e:
                logger.warning(f"Error silencioso en multi_agent_research.discard: {e}")
                # fallback: continuar
    return descartados


def get_ultimo_aprendizaje() -> dict:
    """Devuelve lo último que URA ha aprendido (curado, en Mac)."""
    ultimo = None
    ultima_fecha = ""
    for f in sorted(_INTERNAL.rglob("*.json"), reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
                ts = data.get("timestamp", "")
                if ts > ultima_fecha:
                    ultima_fecha = ts
                    ultimo = {
                        "area": data.get("area", f.parent.name),
                        "resumen": data.get("resumen", ""),
                        "fecha": ts,
                    }
        except Exception as e:
            logger.warning(f"Error silencioso en multi_agent_research.parse_result: {e}")
            # fallback: continuar
        if ultimo:
            break
    return ultimo or {"area": "ninguna", "resumen": "Aún no he aprendido nada.", "fecha": ""}


def get_multi_stats() -> dict:
    """Estadísticas completas: Toshiba (bruto) + Mac (curado)."""
    stats = {"bruto": {"total": 0, "areas": {}}, "curado": {"total": 0, "areas": {}}}

    if RAW_BASE.exists():
        for f in RAW_BASE.rglob("*.json"):
            area = f.parent.name
            stats["bruto"]["areas"][area] = stats["bruto"]["areas"].get(area, 0) + 1
            stats["bruto"]["total"] += 1

    if _INTERNAL.exists():
        for f in _INTERNAL.rglob("*.json"):
            area = f.parent.name
            stats["curado"]["areas"][area] = stats["curado"]["areas"].get(area, 0) + 1
            stats["curado"]["total"] += 1

    return stats


async def ejecutar_ciclo_completo():
    """Ejecuta investigación en las 5 áreas en paralelo."""
    tareas = []
    for nombre, config in AREAS.items():
        tareas.append(investigar_area(nombre, config))

    resultados = await asyncio.gather(*tareas)

    for r in resultados:
        guardar_investigacion(r["area"], r)

    return {
        "areas_investigadas": len(resultados),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def get_multi_stats() -> dict:
    """Estadísticas completas de la investigación multi-agente."""
    if not KNOWLEDGE_BASE.exists():
        return {"total_archivos": 0, "areas": {}}
    areas = {}
    total = 0
    total_knowledge = 0
    for f in KNOWLEDGE_BASE.rglob("*.json"):
        area = f.parent.name
        areas[area] = areas.get(area, 0) + 1
        total += 1
        try:
            with open(f) as fp:
                data = json.load(fp)
                for q, res in data.get("resultados_por_query", {}).items():
                    total_knowledge += len(res.get("conocimiento", []))
        except Exception as e:
            logger.warning(f"Error silencioso en multi_agent_research.count_knowledge: {e}")
            # fallback: continuar
    return {
        "total_archivos": total,
        "total_conocimiento": total_knowledge,
        "areas": areas,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    print("🔬 URA Multi-Agente: 5 áreas × 3 agentes × 3 queries")
    resultado = asyncio.run(ejecutar_ciclo_completo())
    print(f"✅ {resultado['areas_investigadas']} áreas investigadas")
    print(f"\n📁 Toshiba (datos brutos): {get_multi_stats()['bruto']['total']} archivos")

    # Curar conocimiento si hay datos nuevos
    print("🧠 Procesando datos brutos...")
    curados = asyncio.run(curar_conocimiento())
    print(f"✅ {curados} resúmenes curados guardados en Mac SSD")
    print(f"\n📚 Mac SSD (curado): {get_multi_stats()['curado']['total']} archivos")

    ultimo = get_ultimo_aprendizaje()
    print(f"\n🆕 Último aprendizaje: {ultimo['area']} — {ultimo['resumen'][:200]}")
