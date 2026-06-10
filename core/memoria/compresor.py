"""Compresor de ideas: texto extraído → LLM → ideas estructuradas."""
import json
import logging
from typing import Any

import httpx

from core.memoria.ficha import Idea

log = logging.getLogger("memoria.compresor")

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODELO_COMPRESOR = "qwen2.5-coder:14b"
MAX_CHARS_TEXTO = 8000

PROMPT_COMPRESOR = """Eres un extractor de ideas. Analiza el texto y extrae SOLO ideas concretas, accionables y con valor practico.

REGLAS:
1. Cada idea debe ser 1-2 frases utiles, no un resumen.
2. Clasifica cada idea: tipo=herramienta|tendencia|tecnica|dato
3. Si la idea habla de una herramienta concreta, pon su nombre en "herramienta".
4. Si menciona coste (gratis/pago/freemium), ponlo en "coste". Si no, dejalo vacio.
5. Asigna un tema principal corto y etiquetas relevantes.
6. NO inventes nada. Solo ideas que salgan del texto.
7. Si el texto no tiene ideas utiles, devuelve lista vacia.

Responde UNICAMENTE con un array JSON valido, sin explicacion, sin markdown:

[
  {{
    "idea": "Frase concreta con la idea extraida",
    "tema": "categoria corta",
    "etiquetas": ["tag1", "tag2"],
    "tipo": "herramienta",
    "herramienta": "NombreHerramienta",
    "coste": "gratis"
  }}
]

Texto a analizar:
{texto}

Responde SOLO con el array JSON:"""


async def comprimir_a_ideas(texto: str, fuente: str = "", hash_origen: str = "", fecha_fuente: str = "", modelo: str = "") -> list[Idea]:
    if not texto.strip():
        return []

    modelo = modelo or MODELO_COMPRESOR
    fragmento = texto[:MAX_CHARS_TEXTO]
    prompt = PROMPT_COMPRESOR.format(texto=fragmento)

    ideas: list[Idea] = []

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OLLAMA_URL, json={
            "model": modelo,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 2048},
        })

    if resp.is_error:
        log.error(f"Ollama error comprimiendo: {resp.status_code}")
        return ideas

    data = resp.json()
    content = data.get("message", {}).get("content", "").strip()

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("[")
        end = content.rfind("]")
        if start >= 0 and end > start:
            try:
                raw = json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                log.warning(f"No se pudo parsear JSON del compresor: {content[:200]}")
                return ideas
        else:
            log.warning(f"Respuesta sin JSON: {content[:200]}")
            return ideas

    if not isinstance(raw, list):
        return ideas

    for item in raw:
        if not isinstance(item, dict) or "idea" not in item:
            continue
        idea = Idea(
            idea=item.get("idea", ""),
            tema=item.get("tema", ""),
            etiquetas=item.get("etiquetas", []) if isinstance(item.get("etiquetas"), list) else [],
            tipo=item.get("tipo", "dato"),
            herramienta=item.get("herramienta", ""),
            coste=item.get("coste", ""),
            fuente=fuente,
            hash_origen=hash_origen,
            fecha_fuente=fecha_fuente,
            version=1,
            vigente=True,
        )
        if idea.idea.strip():
            ideas.append(idea)

    log.info(f"Compresor: {len(raw)} items -> {len(ideas)} ideas validas ({modelo})")
    return ideas
