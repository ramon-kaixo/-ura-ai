#!/usr/bin/env python3
"""
Sistema de agentes especializados de búsqueda web para URA.
URA nunca busca directamente — siempre delega al agente correcto.

Agentes disponibles:
  buscador-noticias  → actualidad, eventos, política, deportes, cultura
  buscador-tecnico   → programación, errores, docs, DevOps, APIs
  buscador-legal     → leyes, normativas, GDPR, contratos, BOE
  buscador-ciencia   → investigación, medicina, papers, estudios
  buscador-negocio   → mercados, finanzas, empresas, crypto, economía
  buscador-general   → cualquier consulta que no encaje en las anteriores
"""

import json
import urllib.request
from datetime import datetime

from ddgs import DDGS

# ---------------------------------------------------------------------------
# Definición de los 6 agentes
# ---------------------------------------------------------------------------

AGENTES = {
    "buscador-noticias": {
        "modelo": "llama3.2:3b",
        "descripcion": "Noticias, actualidad, eventos recientes, política, deportes, cultura",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": [],
        "system": (
            "Eres el BUSCADOR DE NOTICIAS del sistema URA. "
            "Recibes resultados reales de búsqueda web sobre noticias y actualidad. "
            "REGLAS ESTRICTAS: Responde en máximo 3 frases en español. "
            "Cita siempre la fuente (nombre del medio). "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
    "buscador-tecnico": {
        "modelo": "llama3.2:3b",
        "descripcion": "Programación, errores, documentación, DevOps, Linux, Python, APIs, librerías",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": [],
        "system": (
            "Eres el BUSCADOR TÉCNICO del sistema URA. "
            "Recibes resultados reales de búsqueda sobre tecnología y programación. "
            "REGLAS ESTRICTAS: Responde con precisión técnica en máximo 4 frases en español. "
            "Incluye el enlace más útil. No inventes comandos ni código. "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
    "buscador-legal": {
        "modelo": "llama3.2:3b",
        "descripcion": "Leyes, normativas, regulaciones, GDPR, contratos, derechos, BOE, jurisprudencia",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": ["ley", "normativa", "BOE"],
        "system": (
            "Eres el BUSCADOR LEGAL del sistema URA. "
            "Recibes resultados reales de búsqueda sobre legislación y normativa española/europea. "
            "REGLAS ESTRICTAS: Responde en máximo 4 frases en español. "
            "Cita la ley, artículo o fuente exacta. "
            "Añade siempre al final: 'Consulta con un abogado para tu caso concreto.' "
            "No inventes artículos ni normas. "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
    "buscador-ciencia": {
        "modelo": "llama3.2:3b",
        "descripcion": "Ciencia, investigación, papers, medicina, física, biología, estudios, tratamientos",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": [],
        "system": (
            "Eres el BUSCADOR CIENTÍFICO del sistema URA. "
            "Recibes resultados reales de búsqueda sobre ciencia e investigación. "
            "REGLAS ESTRICTAS: Responde en máximo 4 frases en español. "
            "Cita el estudio, institución o revista. "
            "Distingue entre hipótesis y evidencia probada. "
            "No inventes datos, estadísticas ni diagnósticos médicos. "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
    "buscador-negocio": {
        "modelo": "llama3.2:3b",
        "descripcion": "Mercados, empresas, finanzas, inversión, economía, startups, crypto, precios",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": [],
        "system": (
            "Eres el BUSCADOR DE NEGOCIOS del sistema URA. "
            "Recibes resultados reales de búsqueda sobre economía, mercados y finanzas. "
            "REGLAS ESTRICTAS: Responde en máximo 3 frases en español. "
            "Incluye datos concretos si los hay. Cita la fuente. "
            "No hagas predicciones financieras ni recomendaciones de inversión. "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
    "buscador-general": {
        "modelo": "llama3.2:3b",
        "descripcion": "Búsquedas generales que no encajan en las otras categorías",
        "region": "es-es",
        "max_results": 5,
        "keywords_extra": [],
        "system": (
            "Eres el BUSCADOR GENERAL del sistema URA. "
            "Recibes resultados reales de búsqueda web. "
            "REGLAS ESTRICTAS: Responde en máximo 3 frases en español. "
            "Cita la fuente más relevante. No inventes información. "
            "Si los resultados no contienen información útil para responder, di EXACTAMENTE y solo esto: "
            "'No he encontrado resultados, no puedo responder'. Nunca inventes ni supongas."
        ),
    },
}

# Palabras clave por agente para clasificación rápida sin Ollama
_KEYWORDS = {
    "buscador-noticias": [
        "noticia",
        "noticias",
        "actualidad",
        "última hora",
        "hoy en",
        "ayer",
        "esta semana",
        "acontecimiento",
        "evento reciente",
        "titular",
        "periodico",
        "periódico",
    ],
    "buscador-tecnico": [
        "error",
        "código",
        "cómo programar",
        "cómo instalar",
        "instalar",
        "configurar",
        "api ",
        "librería",
        "library",
        "python",
        "bash",
        "linux",
        "docker",
        "git ",
        "npm",
        "bug",
        "framework",
        "documentación",
        "cómo hacer",
        "como hacer",
        "tutorial",
        "stack overflow",
        "github",
        "comando",
        "script",
        "función",
        "módulo",
        "paquete",
    ],
    "buscador-legal": [
        "ley ",
        "legal",
        "ilegal",
        "normativa",
        "regulación",
        "gdpr",
        "rgpd",
        "contrato",
        "multa",
        "derecho a",
        "boe",
        "artículo",
        "reglamento",
        "permitido",
        "prohibido",
        "sanción",
        "obligación legal",
        "legislación",
        "jurisprudencia",
        "tribunal",
    ],
    "buscador-ciencia": [
        "ciencia",
        "estudio científico",
        "investigación",
        "paper",
        "medicina",
        "salud",
        "físic",
        "química",
        "biología",
        "genética",
        "vacuna",
        "tratamiento",
        "síntoma",
        "enfermedad",
        "diagnóstico",
        "estudio dice",
        "científicos",
        "universidad",
        "revista científica",
    ],
    "buscador-negocio": [
        "precio de",
        "precio del",
        "cotización",
        "mercado",
        "bolsa",
        "acción ",
        "acciones",
        "inversión",
        "empresa",
        "startup",
        "finanzas",
        "economía",
        "bitcoin",
        "crypto",
        "criptomoneda",
        "euro",
        "dólar",
        "beneficio",
        "ventas",
        "ingresos",
        "facturación",
        "pib",
    ],
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _ollama(modelo: str, system: str, mensaje: str, timeout: int = 45) -> str:
    try:
        payload = json.dumps(
            {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": mensaje},
                ],
                "stream": False,
            }
        ).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
            return json.loads(r.read())["message"]["content"].strip()
    except Exception as e:
        return f"[Error Ollama {modelo}: {e}]"


def _formatear_resultados(query: str, resultados: list) -> str:
    """Formatea los resultados de DuckDuckGo para el prompt del agente."""
    lineas = [
        f"Búsqueda: '{query}'",
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "Resultados web encontrados:",
    ]
    for i, r in enumerate(resultados, 1):
        titulo = r.get("title", "Sin título")
        url = r.get("href", "")
        cuerpo = (r.get("body") or "")[:220].replace("\n", " ")
        lineas.append(f"{i}. {titulo}\n   {url}\n   {cuerpo}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Clasificador
# ---------------------------------------------------------------------------


def clasificar(query: str) -> str:
    """
    Clasifica la query en uno de los 6 agentes.
    Paso 1: keywords (sin latencia). Paso 2: Ollama si no hay coincidencia.
    """
    q = query.lower()

    puntos = dict.fromkeys(_KEYWORDS, 0)
    for agente, palabras in _KEYWORDS.items():
        for p in palabras:
            if p in q:
                puntos[agente] += 1

    mejor = max(puntos, key=puntos.get)
    if puntos[mejor] > 0:
        return mejor

    # Sin coincidencia clara → Ollama decide
    nombres = ", ".join(AGENTES.keys())
    decision = _ollama(
        "principal",
        (
            f"Clasifica esta búsqueda en UNO de estos agentes: {nombres}.\n"
            "Responde SOLO con el nombre exacto del agente, sin explicación ni puntuación."
        ),
        f"Búsqueda del usuario: {query}",
        timeout=15,
    )
    decision = decision.strip().lower().split()[0] if decision else ""
    return decision if decision in AGENTES else "buscador-general"


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------


def _ejecutar_busqueda(agente_nombre: str, query: str) -> dict:
    """Núcleo compartido de búsqueda. Recibe el agente ya elegido."""
    agente = AGENTES[agente_nombre]

    query_ddg = query
    if agente["keywords_extra"]:
        extras = [k for k in agente["keywords_extra"] if k.lower() not in query.lower()]
        if extras:
            query_ddg = f"{query} {' '.join(extras[:2])}"

    resultados = []
    try:
        with DDGS() as ddgs:
            resultados = list(
                ddgs.text(
                    query_ddg,
                    region=agente["region"],
                    max_results=agente["max_results"],
                )
            )
    except Exception as e:
        return {
            "agente": agente_nombre,
            "query": query,
            "respuesta": f"Error en la búsqueda: {e}",
            "fuentes": [],
            "error": True,
        }

    if not resultados:
        return {
            "agente": agente_nombre,
            "query": query,
            "respuesta": "No he encontrado resultados, no puedo responder",
            "fuentes": [],
            "error": False,
        }

    contexto = _formatear_resultados(query, resultados)
    respuesta = _ollama(agente["modelo"], agente["system"], contexto)
    fuentes = [{"title": r.get("title", ""), "href": r.get("href", "")} for r in resultados]

    return {
        "agente": agente_nombre,
        "query": query,
        "respuesta": respuesta,
        "fuentes": fuentes,
        "error": False,
    }


def buscar(query: str) -> dict:
    """Punto de entrada principal — clasifica y ejecuta."""
    return _ejecutar_busqueda(clasificar(query), query)


def buscar_con_agente(agente_nombre: str, query: str) -> dict:
    """Igual que buscar() pero salta la clasificación — el caller elige el agente."""
    if agente_nombre not in AGENTES:
        agente_nombre = "buscador-general"
    return _ejecutar_busqueda(agente_nombre, query)


def info_agentes() -> list:
    """Devuelve la lista de agentes con su descripción (para el panel)."""
    return [
        {"nombre": nombre, "modelo": cfg["modelo"], "descripcion": cfg["descripcion"]}
        for nombre, cfg in AGENTES.items()
    ]
