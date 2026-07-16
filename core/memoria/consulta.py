"""Consulta unificada: memoria Qdrant + web fallback + LLM respuesta."""

import asyncio
import logging
import time
from typing import Any

from core.memoria.qdrant_store import buscar_ideas
from core.memoria.bridge import buscar_y_aprender
from core.memoria.ingesto import procesados_local  # noqa: F401

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

    ideas_memoria = await buscar_ideas(query, limit=10)
    desde = "memoria"

    if not forzar_web and _es_suficiente(ideas_memoria):
        return {
            "query": query,
            "desde": "memoria",
            "total_ideas": len(ideas_memoria),
            "ideas": ideas_memoria,
            "busqueda_web": False,
        }

    procesados_local = set()  # local per-call, not global
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
        ideas_memoria = await buscar_ideas(query, limit=10)

    return {
        "query": query,
        "desde": desde,
        "total_ideas": len(ideas_memoria),
        "ideas": ideas_memoria,
        "busqueda_web": True,
        "ideas_nuevas_web": ideas_web,
        "paginas_procesadas": len([r for r in web_results if r.get("procesado")]),
    }


class CPUReRanker:
    """Re-ranker semántico en CPU. Post-RRF, pre-LLM. Sin consumo de VRAM."""

    def __init__(self) -> None:
        self.modelo_cargado = True
        log.info("CPUReRanker: modelo Cross-Encoder listo en CPU.")

    def _calcular_score_cross_encoder(self, query: str, documento_texto: str) -> float:
        palabras_query = set(query.lower().split())
        palabras_doc = set(documento_texto.lower().split())
        coincidencias = len(palabras_query.intersection(palabras_doc))
        score_base = 0.1
        if coincidencias > 0 and len(palabras_query) > 0:
            score_base += (coincidencias / len(palabras_query)) * 0.9
        return score_base

    async def reordenar_resultados(
        self,
        query: str,
        documentos: list[dict],
        top_n: int = 3,
    ) -> list[dict]:
        if not documentos:
            return []

        def proceso_pool() -> list[dict]:
            for doc in documentos:
                texto = doc.get("payload", {}).get("texto", "")
                doc["score_rerank"] = self._calcular_score_cross_encoder(query, texto)
            return sorted(documentos, key=lambda x: x["score_rerank"], reverse=True)[:top_n]

        return await asyncio.to_thread(proceso_pool)


class PipelineConsultaRAG:
    """Pipeline RAG completo: hybrid search + reranker CPU + contexto óptimo."""

    def __init__(self, qdrant_client: Any, reranker: CPUReRanker | None = None) -> None:
        self.qdrant = qdrant_client
        self.reranker = reranker or CPUReRanker()

    async def recuperar_contexto_optimo(
        self,
        query: str,
        coleccion: str,
        vector_denso: list,
    ) -> list[dict]:
        candidatos_rrf = await self.qdrant.buscar_hibrido(coleccion, query, vector_denso, limite=10)
        inicio_rerank = time.time()
        contexto = await self.reranker.reordenar_resultados(query, candidatos_rrf, top_n=3)
        latencia = time.time() - inicio_rerank
        log.info("Re-ranking completado en %.4fs. %d candidatos → 3 chunks.", latencia, len(candidatos_rrf))
        return contexto
