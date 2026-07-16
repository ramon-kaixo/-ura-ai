"""Compresor de ideas: texto extraído → LLM → ideas estructuradas."""

import json
import logging

import httpx

from core.memoria.ficha import Idea

log = logging.getLogger("memoria.compresor")

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODELO_COMPRESOR = "qwen2.5-coder:14b"
MAX_CHARS_TEXTO = 8000

PROMPT_COMPRESOR = """Eres un extractor de conocimiento practico. Lee el texto y extrae SOLO ideas accionables: cosas que alguien PUEDE HACER, USAR o SABER para aplicarlo.

REGLAS:
1. NO repitas frases del texto. Sintetiza. Transforma datos en consejos.
2. Cada idea debe responder: "que puedo hacer con esto?" o "por que me importa?"
3. Buenas ideas: "Usa Canva (gratis) para disenar menus con plantillas y exportarlos via API"
4. Malas ideas: "Canva es una herramienta de diseno grafico que permite crear..." (eso es una definicion, no una idea)
5. Se breve: maximo 2 frases por idea.
6. Clasifica: tipo=herramienta|tendencia|tecnica|dato
7. Si la idea recomienda una herramienta, ponla en "herramienta". Si es gratis o de pago, en "coste".
8. Si el texto no tiene ideas accionables, devuelve [].

Responde UNICAMENTE con un array JSON valido, sin markdown ni explicacion:

[
  {{
    "idea": "Idea accionable sintetizada",
    "tema": "categoria",
    "etiquetas": ["tag1", "tag2"],
    "tipo": "herramienta",
    "herramienta": "Nombre",
    "coste": "gratis"
  }}
]

Texto:
{texto}

JSON:"""


async def comprimir_a_ideas(
    texto: str, fuente: str = "", hash_origen: str = "", fecha_fuente: str = "", modelo: str = ""
) -> list[Idea]:
    if not texto.strip():
        return []

    modelo = modelo or MODELO_COMPRESOR
    fragmento = texto[:MAX_CHARS_TEXTO]
    prompt = PROMPT_COMPRESOR.format(texto=fragmento)

    ideas: list[Idea] = []

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            OLLAMA_URL,
            json={
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 2048},
            },
        )

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
                raw = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                log.warning(f"No se pudo parsear JSON del compresor: {content[:200]}")
                return ideas
        else:
            log.warning(f"Respuesta sin JSON: {content[:200]}")
            return ideas

    if not isinstance(raw, list):
        return ideas

    for idx, item in enumerate(raw):
        if not isinstance(item, dict) or "idea" not in item:
            continue
        idea_hash = f"{hash_origen}:{idx}" if hash_origen else ""
        idea = Idea(
            idea=item.get("idea", ""),
            tema=item.get("tema", ""),
            etiquetas=item.get("etiquetas", []) if isinstance(item.get("etiquetas"), list) else [],
            tipo=item.get("tipo", "dato"),
            herramienta=item.get("herramienta", ""),
            coste=item.get("coste", ""),
            fuente=fuente,
            hash_origen=idea_hash,
            fecha_fuente=fecha_fuente,
            version=1,
            vigente=True,
        )
        if idea.idea.strip():
            ideas.append(idea)

    log.info(f"Compresor: {len(raw)} items -> {len(ideas)} ideas validas ({modelo})")
    return ideas
