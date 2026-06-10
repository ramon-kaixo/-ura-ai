"""Fase Hacer: busca repos GitHub/GitLab open source con filtro de licencia."""
import asyncio
import logging

import httpx

from core.mochila.tools import page_read
from core.memoria.compresor import comprimir_a_ideas
from core.memoria.qdrant_store import almacenar_ideas

log = logging.getLogger("memoria.hacer")

GITHUB_API = "https://api.github.com"
LICENCIAS_VALIDAS = {"mit", "apache-2.0", "gpl-2.0", "gpl-3.0", "bsd-2-clause", "bsd-3-clause", "mpl-2.0"}


async def buscar_github(keywords: str, max_results: int = 10) -> list[dict]:
    resultados = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{GITHUB_API}/search/repositories",
                params={"q": keywords, "sort": "stars", "order": "desc", "per_page": max_results},
                headers={"Accept": "application/vnd.github.v3+json"},
            )
        if resp.is_error:
            log.error(f"GitHub API error: {resp.status_code}")
            return resultados

        for repo in resp.json().get("items", []):
            licencia = (repo.get("license") or {}).get("spdx_id", "").lower()
            if licencia not in LICENCIAS_VALIDAS:
                continue

            resultados.append({
                "nombre": repo.get("full_name", ""),
                "descripcion": (repo.get("description") or "")[:300],
                "url": repo.get("html_url", ""),
                "estrellas": repo.get("stargazers_count", 0),
                "lenguaje": repo.get("language", ""),
                "licencia": licencia,
                "readme_url": f"https://raw.githubusercontent.com/{repo.get('full_name','')}/main/README.md",
                "topics": repo.get("topics", []),
            })
    except Exception as e:
        log.error(f"GitHub search: {e}")
    return resultados


async def _leer_readme(readme_url: str) -> str | None:
    try:
        result = await page_read(readme_url, max_chars=10000)
        if "error" in result:
            alt_url = readme_url.replace("/main/", "/master/")
            result = await page_read(alt_url, max_chars=10000)
            if "error" in result:
                return None
        return result.get("content", "")
    except Exception:
        return None


async def fase_hacer(keywords: str) -> dict:
    repos = await buscar_github(keywords)
    if not repos:
        return {"keywords": keywords, "repos_encontrados": 0, "analizados": 0, "ideas": 0}

    analizados = 0
    total_ideas = 0

    for repo in repos:
        log.info(f"  {repo['nombre']} ({repo['licencia']}, {repo['estrellas']}*)")

        readme_text = await _leer_readme(repo["readme_url"])
        if not readme_text:
            continue

        analizados += 1
        texto = f"# {repo['nombre']}\n{repo['descripcion']}\n\n{readme_text}"

        try:
            import blake3
            h = blake3.blake3(texto.encode()).hexdigest()
            ideas = await comprimir_a_ideas(
                texto, fuente=repo["url"],
                hash_origen=h,
            )
            if ideas:
                for idea in ideas:
                    if not idea.herramienta:
                        idea.herramienta = repo["nombre"]
                    if not idea.coste:
                        idea.coste = "gratis"
                n = await almacenar_ideas(ideas)
                total_ideas += n
        except Exception as e:
            log.error(f"  Error: {e}")

        await asyncio.sleep(1)

    return {
        "keywords": keywords,
        "repos_encontrados": len(repos),
        "analizados": analizados,
        "ideas": total_ideas,
    }
