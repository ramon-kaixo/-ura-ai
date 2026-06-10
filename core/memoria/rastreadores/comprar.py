"""Fase Comprar: plataformas comerciales top 5-10 + Agente Crítico."""
import asyncio
import logging

import httpx

from core.mochila.tools import web_search, page_read
from core.memoria.compresor import comprimir_a_ideas
from core.memoria.qdrant_store import almacenar_ideas

log = logging.getLogger("memoria.comprar")

CRITICO_MODEL = "qwen3:32b-q8_0"


async def _agente_critico(texto_web: str, herramienta: str) -> str:
    prompt = f"""Analiza la pagina web de {herramienta} como un critico experto. Busca la letra pequeña, trampas y costes ocultos.

Preguntas a responder:
1. Te dejan exportar tus datos si cierras la cuenta? Hay lock-in?
2. Costes ocultos: que funcionalidades clave NO estan en el plan basico?
3. Que pierdes si dejas de pagar?
4. Limites en el plan barato: cuantas paginas/proyectos/usuarios?
5. Hay garantia de precio? Suben sin avisar?
6. Cancelacion: es facil o te retienen?

Texto de la web:
{texto_web[:4000]}

Responde en formato JSON:
{{"riesgo_lockin": "bajo/medio/alto", "costes_ocultos": ["...", "..."], "perdida_si_bajas": "...", "limites_gratis": "...", "valoracion": "recomendable/precauccion/evitar", "resumen": "1-2 frases"}}

JSON:"""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("http://127.0.0.1:11434/api/chat", json={
                "model": CRITICO_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 1024},
            })
        if resp.is_error:
            return ""
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
    except Exception:
        return ""


async def _buscar_comerciales(keywords: str, max_results: int = 5) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.duckduckgo.com",
                params={"q": f"{keywords} plataforma precio plan", "format": "json", "no_html": "1"},
            )
        if resp.is_error:
            return []
        data = resp.json()
        resultados = []
        for topic in data.get("RelatedTopics", [])[:max_results]:
            url = topic.get("FirstURL", "")
            text = topic.get("Text", "")
            if url and text:
                resultados.append({"nombre": text.split(" - ")[-1][:80], "url": url, "snippet": text[:200]})
        return resultados
    except Exception:
        return []


async def _raspar_pricing(url: str) -> str:
    try:
        result = await page_read(url, max_chars=8000)
        if "error" in result:
            return ""
        return result.get("content", "")
    except Exception:
        return ""


async def fase_comprar(keywords: str) -> dict:
    comerciales = await _buscar_comerciales(keywords)
    if not comerciales:
        # Fallback: web_search
        search = await web_search(keywords + " precios", max_results=5)
        comerciales = [{"nombre": r["title"][:80], "url": r["url"], "snippet": r.get("snippet", "")} for r in search.get("results", [])]

    analizados = 0
    total_ideas = 0
    criticas = []

    for c in comerciales[:5]:
        log.info(f"  Analizando {c['nombre'][:60]}...")

        texto = await _raspar_pricing(c["url"])
        if not texto:
            continue

        analizados += 1
        critica = await _agente_critico(texto, c["nombre"])

        try:
            import json
            analisis = json.loads(critica) if critica.startswith("{") else {}
        except json.JSONDecodeError:
            analisis = {}

        import blake3
        h = blake3.blake3(texto.encode()).hexdigest()
        ideas = await comprimir_a_ideas(
            f"{c['nombre']}: {c.get('snippet','')}\n\n{texto}",
            fuente=c["url"],
            hash_origen=h,
        )
        if ideas:
            for idea in ideas:
                idea.tipo = "plataforma"
                if not idea.herramienta:
                    idea.herramienta = c["nombre"]
                if analisis.get("costes_ocultos"):
                    idea.datos_duros = {"critica": analisis}
            n = await almacenar_ideas(ideas)
            total_ideas += n

        criticas.append({
            "nombre": c["nombre"],
            "url": c["url"],
            "critica": analisis,
        })

        await asyncio.sleep(1)

    return {
        "keywords": keywords,
        "plataformas_encontradas": len(comerciales),
        "analizadas": analizados,
        "ideas": total_ideas,
        "criticas": criticas,
    }
