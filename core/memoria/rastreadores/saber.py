"""Fase Saber: busca papers en Semantic Scholar y arXiv, filtra por calidad."""
import asyncio
import logging
from pathlib import Path

import httpx

from core.memoria.compresor import comprimir_a_ideas
from core.memoria.ingesto import procesar_archivo
from core.memoria.qdrant_store import almacenar_ideas

log = logging.getLogger("memoria.saber")
TEORIA_DIR = Path.home() / ".nervioso" / "teoria"

SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
ARXIV_API = "http://export.arxiv.org/api/query"

MIN_CALIDAD = 7


async def _puntuar_abstract(abstract: str, titulo: str, keywords: str) -> int:
    prompt = f"""Evalua la calidad de este paper para un proyecto sobre "{keywords}".

Titulo: {titulo}
Abstract: {abstract[:1000]}

Puntua del 1 al 10 donde:
- 1-3: irrelevante o basura
- 4-6: relevante pero superficial
- 7-8: util, aporta valor
- 9-10: imprescindible, alta calidad

Responde SOLO con el numero (ej: 8):"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("http://127.0.0.1:11434/api/chat", json={
                "model": "qwen2.5:7b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 10},
            })
        if resp.is_error:
            return 5
        data = resp.json()
        text = data["message"]["content"].strip()
        import re
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 5
    except Exception:
        return 5


async def buscar_semantic_scholar(keywords: str, max_results: int = 5) -> list[dict]:
    resultados = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{SEMANTIC_SCHOLAR}/paper/search",
                params={"query": keywords, "limit": max_results, "fields": "title,abstract,url,year,authors,openAccessPdf"},
            )
        if resp.is_error:
            log.error(f"Semantic Scholar error: {resp.status_code}")
            return resultados

        for paper in resp.json().get("data", []):
            abstract = paper.get("abstract") or ""
            titulo = paper.get("title", "")
            if not abstract:
                continue
            puntuacion = await _puntuar_abstract(abstract, titulo, keywords)
            if puntuacion < MIN_CALIDAD:
                continue
            pdf_url = ""
            if paper.get("openAccessPdf"):
                pdf_url = paper["openAccessPdf"].get("url", "")
            autores = [a.get("name", "") for a in paper.get("authors", [])]
            resultados.append({
                "titulo": titulo,
                "autores": autores[:3],
                "year": paper.get("year", ""),
                "url": paper.get("url", ""),
                "pdf_url": pdf_url,
                "abstract": abstract[:500],
                "puntuacion": puntuacion,
                "fuente": "semantic_scholar",
            })
    except Exception as e:
        log.error(f"Semantic Scholar: {e}")
    return resultados


async def buscar_arxiv(keywords: str, max_results: int = 5) -> list[dict]:
    resultados = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(ARXIV_API, params={
                "search_query": f"all:{keywords}",
                "max_results": max_results,
                "sortBy": "relevance",
            })
        if resp.is_error:
            log.error(f"arXiv error: {resp.status_code}")
            return resultados

        import re
        entries = re.split(r"<entry>", resp.text)[1:]
        for entry in entries:
            titulo = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            abstract = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            link = re.search(r"<id>(.*?)</id>", entry)
            titulo_text = titulo.group(1).strip() if titulo else ""
            abstract_text = abstract.group(1).strip() if abstract else ""
            link_text = link.group(1).strip() if link else ""

            if not abstract_text:
                continue
            puntuacion = await _puntuar_abstract(abstract_text, titulo_text, keywords)
            if puntuacion < MIN_CALIDAD:
                continue

            resultados.append({
                "titulo": titulo_text,
                "abstract": abstract_text[:500],
                "url": link_text.replace("abs", "pdf") if "abs" in link_text else link_text,
                "puntuacion": puntuacion,
                "fuente": "arxiv",
            })
    except Exception as e:
        log.error(f"arXiv: {e}")
    return resultados


async def fase_saber(keywords: str) -> dict:
    papers_s2 = await buscar_semantic_scholar(keywords)
    papers_arxiv = await buscar_arxiv(keywords)
    papers = papers_s2 + papers_arxiv

    if not papers:
        return {"keywords": keywords, "papers_encontrados": 0, "papers_guardados": 0, "ideas": 0}

    TEORIA_DIR.mkdir(parents=True, exist_ok=True)
    guardados = 0
    total_ideas = 0

    for paper in papers:
        pdf_url = paper.get("pdf_url", "") or paper.get("url", "")
        log.info(f"  {paper['titulo'][:80]} (score={paper['puntuacion']})")

        if pdf_url and paper["puntuacion"] >= MIN_CALIDAD:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    pdf_resp = await client.get(pdf_url if pdf_url.startswith("http") else f"https:{pdf_url}")
                if pdf_resp.status_code == 200:
                    nombre = paper["titulo"][:60].replace("/", "_").replace(" ", "_")
                    ruta = TEORIA_DIR / f"{nombre}.pdf"
                    ruta.write_bytes(pdf_resp.content)
                    proc = procesar_archivo(ruta)
                    if proc and proc.get("extraido") and proc["extraido"].get("texto_plano"):
                        ideas = await comprimir_a_ideas(
                            proc["extraido"]["texto_plano"],
                            fuente=paper["url"],
                            hash_origen=proc["hash"],
                        )
                        if ideas:
                            await almacenar_ideas(ideas)
                            total_ideas += len(ideas)
                    guardados += 1
            except Exception as e:
                log.warning(f"  No se pudo descargar PDF: {e}")

        await asyncio.sleep(1)

    return {
        "keywords": keywords,
        "papers_encontrados": len(papers),
        "papers_guardados": guardados,
        "ideas": total_ideas,
        "papers_raw": papers,
    }
