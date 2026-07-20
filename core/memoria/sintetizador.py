"""Sintetizador: ideas de Qdrant → informe estructurado con fuentes."""

import logging
import os

import httpx

from core.memoria.qdrant_store import buscar_ideas

log = logging.getLogger("memoria.sintetizador")
_OLLAMA_HOST = os.environ.get("URA_OLLAMA_HOST", "localhost")
_OLLAMA_PORT = os.environ.get("URA_OLLAMA_PORT", "11434")
OLLAMA = f"http://{_OLLAMA_HOST}:{_OLLAMA_PORT}/api/chat"
MODELO_SINTESIS = "qwen2.5-coder:14b"

PROMPT_SINTESIS = """Eres Aura, una asistente que sintetiza conocimiento desde su memoria.

Tienes estas ideas recuperadas de tu memoria semantica. Organizalas en un informe estructurado:

SECCIONES:
1. LO QUE DICE LA CIENCIA (teoria, documentacion, datos, tendencias)
2. COMO HACERLO GRATIS (herramientas open source, tecnicas sin coste, software libre)
3. OPCIONES DE PAGO (plataformas comerciales, con sus precios y letra pequeña)
4. LO QUE NECESITAS SABER (datos clave, requisitos legales, tramites)

REGLAS:
- Cada afirmacion debe citar su [fuente] entre corchetes.
- Si no hay ideas para alguna seccion, escribe "No hay datos en memoria para esta seccion."
- Se breve: 3-5 puntos por seccion.
- Incluye un RESUMEN EJECUTIVO de 3 lineas al principio.
- Formato Markdown con ## para secciones.

Peticion del usuario: {peticion}

Ideas en memoria:
{ideas}

Informe:"""


async def sintetizar(peticion: str) -> dict:
    ideas = await buscar_ideas(peticion, limit=15)
    if not ideas:
        return {
            "peticion": peticion,
            "informe": "No tengo informacion en memoria sobre este tema. Prueba a buscar en internet con /memoria/consultar?forzar_web=true",
            "total_ideas": 0,
            "fuentes": [],
        }

    ideas_texto = []
    for i, idea in enumerate(ideas):
        fuente = idea.get("fuente", "")
        tipo = idea.get("tipo", "dato")
        coste = f" ({idea.get('coste')})" if idea.get("coste") else ""
        herramienta = f" [{idea.get('herramienta')}]" if idea.get("herramienta") else ""
        linea = f"{i + 1}. [{tipo}{coste}{herramienta}] {idea['idea']}"
        if fuente:
            linea += f" -- fuente: {fuente}"
        ideas_texto.append(linea)

    prompt = PROMPT_SINTESIS.format(
        peticion=peticion,
        ideas="\n".join(ideas_texto),
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                OLLAMA,
                json={
                    "model": MODELO_SINTESIS,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 2048},
                },
            )

        if resp.is_error:
            informe = f"Error generando informe: HTTP {resp.status_code}"
        else:
            data = resp.json()
            informe = data.get("message", {}).get("content", "").strip()

    except Exception as e:
        informe = f"Error generando informe: {e}"

    fuentes = list({i.get("fuente", "") for i in ideas if i.get("fuente")})

    return {
        "peticion": peticion,
        "informe": informe,
        "total_ideas": len(ideas),
        "fuentes": fuentes,
    }
