#!/usr/bin/env python3
"""
SearchOrchestrator — Coordinación de los buscadores N2.

- Recibe una query, decide qué buscadores son relevantes (filtro por keywords).
- Lanza cada buscador en paralelo usando `asyncio.to_thread`.
- Consolida resultados, elimina duplicados por URL y por similitud de
  contenido (>0.9 con `difflib.SequenceMatcher`).
- Devuelve resultados rankeados.

Diferencia con `core/ura_swarm_local.py`:
- El swarm trabaja con maletas (sistema F2/F3) y agentes async genéricos.
- Este orquestador es ligero, síncrono-friendly, sin maletas, pensado como
  punto de entrada simple desde `ura_n2_search.py`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

from core.buscadores.base import BaseSearchAgent, SearchResult
from core.buscadores.buscador_aplicaciones import BuscadorAplicaciones
from core.buscadores.buscador_documentacion import BuscadorDocumentacion
from core.buscadores.buscador_estudios import BuscadorEstudios
from core.buscadores.buscador_manuales import BuscadorManuales
from core.buscadores.buscador_noticias import BuscadorNoticias
from core.buscadores.buscador_tendencias import BuscadorTendencias

logger = logging.getLogger("search_orchestrator")

DEFAULT_AGENT_CLASSES: list[type[BaseSearchAgent]] = [
    BuscadorNoticias,
    BuscadorEstudios,
    BuscadorAplicaciones,
    BuscadorDocumentacion,
    BuscadorManuales,
    BuscadorTendencias,
]

# Similitud por encima de la cual dos snippets se consideran duplicados
DEFAULT_SIM_THRESHOLD = 0.9
DEFAULT_TIMEOUT_S = 60


@dataclass
class OrchestratorReport:
    """Resultado consolidado del orquestador."""

    query: str
    results: list[SearchResult]
    by_agent: dict[str, list[SearchResult]]
    duplicates_removed: int
    agents_used: list[str]
    errors: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": self.results,
            "by_agent": self.by_agent,
            "duplicates_removed": self.duplicates_removed,
            "agents_used": self.agents_used,
            "errors": self.errors,
        }


class SearchOrchestrator:
    """Despacha la query a los buscadores y consolida la salida."""

    def __init__(
        self,
        agent_classes: Iterable[type[BaseSearchAgent]] | None = None,
        *,
        sim_threshold: float = DEFAULT_SIM_THRESHOLD,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.agent_classes = list(agent_classes) if agent_classes else list(DEFAULT_AGENT_CLASSES)
        self.sim_threshold = sim_threshold
        self.timeout_s = timeout_s

    # ----------------------------------------------------------- selection
    def select_agents(self, query: str) -> list[type[BaseSearchAgent]]:
        """
        Devuelve los agentes que aceptan la query (por keyword match).
        Si ninguno acepta, se lanzan TODOS (cobertura amplia).
        """
        matches = [c for c in self.agent_classes if c.acepta_query(query)]
        return matches or list(self.agent_classes)

    # ----------------------------------------------------------- execution
    async def search(self, query: str, max_results: int = 10) -> OrchestratorReport:
        """Ejecuta la búsqueda en todos los agentes seleccionados, en paralelo."""
        selected = self.select_agents(query)
        agents_used = [c.__name__ for c in selected]
        by_agent: dict[str, list[SearchResult]] = {}
        errors: dict[str, str] = {}

        async def _run(
            cls: type[BaseSearchAgent],
        ) -> tuple[str, list[SearchResult] | None, str | None]:
            name = cls.__name__
            try:
                # cada buscador es síncrono → lo movemos a un thread
                instance = cls()
                results = await asyncio.wait_for(
                    asyncio.to_thread(instance.search, query, max_results),
                    timeout=self.timeout_s,
                )
                return name, results, None
            except TimeoutError:
                return name, None, f"timeout {self.timeout_s}s"
            except Exception as e:  # noqa: BLE001
                return name, None, f"{type(e).__name__}: {e}"

        coros = [_run(cls) for cls in selected]
        for fut in asyncio.as_completed(coros):
            name, results, err = await fut
            if err is not None:
                errors[name] = err
                continue
            by_agent[name] = list(results or [])

        # Consolidación
        flat: list[SearchResult] = []
        for r_list in by_agent.values():
            flat.extend(r_list)
        deduped, removed = self._dedup(flat)
        ranked = self._rank(query, deduped)

        return OrchestratorReport(
            query=query,
            results=ranked,
            by_agent=by_agent,
            duplicates_removed=removed,
            agents_used=agents_used,
            errors=errors,
        )

    # ----------------------------------------------------------- dedup
    def _dedup(self, results: list[SearchResult]) -> tuple[list[SearchResult], int]:
        """Elimina duplicados por URL exacta y por similitud de contenido (>threshold)."""
        seen_urls: set[str] = set()
        deduped: list[SearchResult] = []
        removed = 0

        for r in results:
            url = (r.get("url") or "").strip().lower().rstrip("/")
            if url and url in seen_urls:
                removed += 1
                continue
            # similarity check on titulo+snippet
            text = self._text_signature(r)
            is_similar = False
            for existing in deduped:
                if self._similarity(text, self._text_signature(existing)) >= self.sim_threshold:
                    is_similar = True
                    break
            if is_similar:
                removed += 1
                continue
            if url:
                seen_urls.add(url)
            deduped.append(r)
        return deduped, removed

    @staticmethod
    def _text_signature(r: SearchResult) -> str:
        return f"{r.get('titulo', '')} | {r.get('snippet', '')}".strip().lower()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(a=a, b=b).ratio()

    # ----------------------------------------------------------- ranking
    @staticmethod
    def _rank(query: str, results: list[SearchResult]) -> list[SearchResult]:
        """Ordena por score_relevancia descendente; desempata por aparición de
        palabras de la query en el título."""
        q_terms = {t for t in query.lower().split() if len(t) > 2}

        def _key(r: SearchResult) -> tuple[float, int]:
            title = (r.get("titulo") or "").lower()
            term_hits = sum(1 for t in q_terms if t in title)
            return (-float(r.get("score_relevancia", 0.0)), -term_hits)

        return sorted(results, key=_key)


def get_orchestrator() -> SearchOrchestrator:
    return SearchOrchestrator()
