"""Consulta unificada: memoria Qdrant + web fallback + LLM respuesta."""
import logging

from core.memoria.qdrant_store import buscar_ideas
from core.memoria.bridge import buscar_y_aprender
from core.memoria.ingesto import PROCESADOS

log = logging.getLogger("memoria.consulta")

MIN_SCORE_MEMORIA = 0.5
MIN_IDEAS_MEMORIA = 3


def _es_suficiente(resultados_qdrant: list[dict]) -> bool:
    if not resultados_qdrant:
        return False
    buenas = [r for r in resultados_qdrant if r.get("score", 0) >= MIN_SCORE_MEMORIA]
    return len(buenas) >= MIN_IDEAS_MEMORIA


async def consultar(query: str, forzar_web: bool = False) -> dict:
    """Busca en memoria Qdrant. Si no hay suficientes ideas, busca en internet
    y las incorpora a la memoria antes de responder."""

    ideas_memoria = buscar_ideas(query, limit=10)
    desde = "memoria"

    if not forzar_web and _es_suficiente(ideas_memoria):
        return {
            "query": query,
            "desde": "memoria",
            "total_ideas": len(ideas_memoria),
            "ideas": ideas_memoria,
            "busqueda_web": False,
        }

    PROCESADOS.clear()
    web_results = await buscar_y_aprender(query, max_resultados=2)

    ideas_web = 0
    for r in web_results:
        if r.get("procesado") and r["procesado"].get("extraido"):
            ex = r["procesado"]["extraido"]
            if ex.get("texto_plano"):
                try:
                    from core.memoria.compresor import comprimir_a_ideas
                    from core.memoria.qdrant_store import almacenar_ideas

                    ideas = await comprimir_a_ideas(
                        ex["texto_plano"],
                        fuente=r.get("fuente", ""),
                        hash_origen=r["procesado"]["hash"],
                    )
                    if ideas:
                        n = await almacenar_ideas(ideas)
                        ideas_web += n
                except Exception as e:
                    log.error(f"Error comprimiendo web result: {e}")

    desde = "web" if not ideas_memoria else "memoria+web"

    if ideas_web:
        ideas_memoria = buscar_ideas(query, limit=10)

    return {
        "query": query,
        "desde": desde,
        "total_ideas": len(ideas_memoria),
        "ideas": ideas_memoria,
        "busqueda_web": True,
        "ideas_nuevas_web": ideas_web,
        "paginas_procesadas": len([r for r in web_results if r.get("procesado")]),
    }
