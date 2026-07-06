"""Analizador: trocea peticiones y decide fases (Saber/Hacer/Comprar)."""
import json
import logging

import httpx

from core.memoria.qdrant_store import buscar_ideas

log = logging.getLogger("memoria.analizador")
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODELO_ANALISIS = "qwen3:32b-q8_0"

PROMPT_ANALIZADOR = """Eres un analizador de peticiones. Tu trabajo es trocear una peticion en lenguaje natural y decidir que fases de busqueda aplicar.

FASES DISPONIBLES:
- saber: buscar teoria, documentacion tecnica, papers, manuales (PDFs, Google Scholar, arXiv)
- hacer: buscar herramientas de software libre, repositorios GitHub, alternativas gratis
- comprar: analizar plataformas comerciales top 5-10, precios, letra pequena

DATOS:
Peticion: {peticion}
Ideas existentes en memoria: {n_ideas} ideas encontradas
Temas cubiertos: {temas}

DECIDE y responde UNICAMENTE con JSON:
{{
  "fases": ["saber", "hacer"],
  "tema_principal": "SEO para bares",
  "palabras_clave": ["SEO local", "Google My Business", "resenas"],
  "skip_memoria": false,
  "razon": "El tema tiene poca cobertura en memoria, necesitamos teoria y herramientas"
}}

JSON:"""


async def analizar(peticion: str) -> dict:
    ideas = buscar_ideas(peticion, limit=10)
    n_ideas = len(ideas)
    temas = list({i.get("tema", "") for i in ideas if i.get("tema")})

    prompt = PROMPT_ANALIZADOR.format(
        peticion=peticion,
        n_ideas=n_ideas,
        temas=", ".join(temas[:5]) if temas else "(ninguno)",
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(OLLAMA, json={
                "model": MODELO_ANALISIS,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 512},
            })

        if resp.is_error:
            return {"error": f"Ollama {resp.status_code}", "peticion": peticion}

        data = resp.json()
        content = data.get("message", {}).get("content", "").strip()

        try:
            plan = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                plan = json.loads(content[start:end + 1])
            else:
                plan = {"fases": ["saber", "hacer"], "tema_principal": peticion, "palabras_clave": [peticion]}

        return {
            "peticion": peticion,
            "fases": plan.get("fases", ["saber", "hacer"]),
            "tema_principal": plan.get("tema_principal", peticion),
            "palabras_clave": plan.get("palabras_clave", [peticion]),
            "hay_memoria": n_ideas > 0,
            "ideas_encontradas": n_ideas,
            "temas_cubiertos": temas[:5],
            "razon": plan.get("razon", ""),
        }
    except Exception as e:
        return {"error": str(e), "peticion": peticion}
