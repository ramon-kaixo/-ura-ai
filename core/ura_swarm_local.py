#!/usr/bin/env python3
"""
URA Swarm Local — N2 Infrastructure (Fase 1)

Async orchestrator that splits a topic into subtemas and runs N agent searches
in parallel using asyncio.Semaphore + asyncio.Queue for bounded concurrency.

Design decisions:
- Uses asyncio.gather + Semaphore instead of ThreadPoolExecutor
  (avoids mixing threads with Playwright/aiohttp event loops).
- Max 10 simultaneous agents globally (Semaphore).
- Max 3 simultaneous swarms (Queue).
- Per-agent timeout 120s (asyncio.wait_for).
- Per-swarm timeout 300s.
- Always runs the validator.

Agent protocol::

    async def agent(subtema: str, maleta: dict) -> list[dict]:
        ...

where each dict has keys: title, url, snippet, fuente_tipo, fecha.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from core.ura_search_cache import get_search_cache
from core.ura_n2_validador import validate_swarm_output

logger = logging.getLogger("ura_swarm_local")

AgentFn = Callable[[str, dict[str, Any]], Awaitable[list[dict[str, Any]]]]

# Concurrency limits
MAX_GLOBAL_AGENTS = 10
MAX_CONCURRENT_SWARMS = 3
AGENT_TIMEOUT_S = 120
SWARM_TIMEOUT_S = 300

# Global coordination primitives (singletons per event loop)
_agent_semaphore: asyncio.Semaphore | None = None
_swarm_queue: asyncio.Queue | None = None


def _ensure_primitives() -> tuple[asyncio.Semaphore, asyncio.Queue]:
    """Lazy-create primitives bound to the current event loop."""
    global _agent_semaphore, _swarm_queue
    if _agent_semaphore is None:
        _agent_semaphore = asyncio.Semaphore(MAX_GLOBAL_AGENTS)
    if _swarm_queue is None:
        _swarm_queue = asyncio.Queue(maxsize=MAX_CONCURRENT_SWARMS)
    return _agent_semaphore, _swarm_queue


@dataclass
class AgentSpec:
    """Specification for a single agent run."""

    agent_id: str
    rol: str
    subtema: str
    fn: AgentFn
    maleta: dict[str, Any]
    max_retries: int = 2


@dataclass
class AgentResult:
    agente_id: str
    rol: str
    subtema_asignado: str
    estado: str  # "ok" | "error" | "timeout"
    resultados: list[dict[str, Any]] = field(default_factory=list)
    herramientas_usadas: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    tiempo_segundos: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agente_id": self.agente_id,
            "rol": self.rol,
            "subtema_asignado": self.subtema_asignado,
            "estado": self.estado,
            "resultados": self.resultados,
            "herramientas_usadas": self.herramientas_usadas,
            "errores": self.errores,
            "tiempo_segundos": round(self.tiempo_segundos, 2),
        }


def _split_tema(tema: str, maleta: dict[str, Any]) -> list[str]:
    """Split the main theme into subtemas based on maleta configuration."""
    division = maleta.get("division_subtemas", {}) or {}
    n = int(division.get("num_agentes_sugerido", 3))
    # If the maleta provides explicit subtemas, use them
    explicit = division.get("subtemas_explicitos")
    if isinstance(explicit, list) and explicit:
        return [str(s) for s in explicit[:n]]
    # Otherwise produce simple angle-variants of the query
    # (this is a Fase 1 placeholder; N3 / LLM will do smarter splits later)
    variants = [
        tema,
        f"{tema} novedades 2025",
        f"{tema} guía oficial",
        f"{tema} normativa vigente",
        f"{tema} errores comunes",
    ]
    return variants[:n]


class URASwarm:
    """N2 swarm orchestrator."""

    def __init__(self) -> None:
        self.cache = get_search_cache()


async def run(
    self,
    *,
    tema: str,
    maleta: dict[str, Any],
    agent_factory: Callable[[str, str, dict[str, Any]], AgentSpec],
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Run a full N2 swarm for the given theme.

    agent_factory(subtema, rol, maleta) -> AgentSpec
    The caller builds the AgentSpec (this keeps the swarm decoupled from
    the specific agent implementation, which in Fase 1 will be a DDG wrapper).
    """
    start = time.monotonic()
    semaphore, swarm_queue = _ensure_primitives()

    # Queue slot (bounded swarms)
    token = object()
    try:
        await asyncio.wait_for(swarm_queue.put(token), timeout=30)
    except TimeoutError:
        return _handle_swarm_rejection(start)

    try:
        # Cache lookup (fingerprint on the main query)
        if use_cache:
            cached = await self.cache.get(tema, maleta_id=maleta.get("maleta_id"))
            if cached:
                payload = cached.get("results")
                if isinstance(payload, dict):
                    # We previously stored a full informe dict
                    return _handle_cached_result(cached)
                return _handle_partial_cache_result(cached)

        subtemas = _split_tema(tema, maleta)
        roles = _agent_roles_from_maleta(maleta, len(subtemas))
        specs = [
            agent_factory(subtemas[i], roles[i % len(roles)], maleta) for i in range(len(subtemas))
        ]

        try:
            resultados = await asyncio.wait_for(
                self._run_agents(specs, semaphore),
                timeout=SWARM_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("Swarm timeout global tras %ds", SWARM_TIMEOUT_S)
            resultados = []

        # Always validate
        resultados_dicts = [r.to_dict() for r in resultados]
        validation = await validate_swarm_output(resultados_dicts)

        duration = time.monotonic() - start
        exito = validation["score_calidad"] >= 0.4 and bool(resultados_dicts)

        informe = {
            "exito": exito,
            "score_calidad": validation["score_calidad"],
            "resumen_ejecutivo": _summary(tema, resultados_dicts, validation),
            "resultados_por_agente": resultados_dicts,
            "contradicciones_detectadas": validation["contradictions"],
            "fuentes_consolidadas": validation["fuentes_consolidadas"],
            "alertas": validation["alertas"],
            "tiempo_total_segundos": round(duration, 2),
            "cache_usado": False,
        }

        # Persist in cache
        if use_cache and exito:
            await self.cache.put(
                tema,
                informe,
                maleta_id=maleta.get("maleta_id"),
                score_calidad=validation["score_calidad"],
                ttl_hours=maleta.get("anti_repeticion", {}).get("cache_duracion_horas", 24),
            )

        return informe
    finally:
        # Release swarm slot
        try:
            swarm_queue.get_nowait()
            swarm_queue.task_done()
        except Exception:  # noqa: BLE001
            pass


def _handle_swarm_rejection(start: float) -> dict[str, Any]:
    return {
        "exito": False,
        "score_calidad": 0.0,
        "resumen_ejecutivo": "Swarm rechazado: demasiados swarms activos",
        "resultados_por_agente": [],
        "contradicciones_detectadas": [],
        "fuentes_consolidadas": [],
        "alertas": ["saturation"],
        "tiempo_total_segundos": 0.0,
        "cache_usado": False,
    }


def _handle_cached_result(cached: dict[str, Any]) -> dict[str, Any]:
    payload = cached.get("results")
    if isinstance(payload, dict):
        # We previously stored a full informe dict
        return dict(payload)
    return {
        "exito": True,
        "score_calidad": cached.get("score_calidad", 0.0),
        "resumen_ejecutivo": f"(cache) {cached['tema']}",
        "resultados_por_agente": payload or [],
        "contradicciones_detectadas": [],
        "fuentes_consolidadas": [],
        "alertas": [],
        "tiempo_total_segundos": round(time.monotonic() - cached["start_time"], 2),
        "cache_usado": True,
    }


def _handle_partial_cache_result(cached: dict[str, Any]) -> dict[str, Any]:
    return {
        "exito": True,
        "score_calidad": cached.get("score_calidad", 0.0),
        "resumen_ejecutivo": f"(cache) {cached['tema']}",
        "resultados_por_agente": cached["results"] or [],
        "contradicciones_detectadas": [],
        "fuentes_consolidadas": [],
        "alertas": [],
        "tiempo_total_segundos": round(time.monotonic() - cached["start_time"], 2),
        "cache_usado": True,
    }


def _summary(tema: str, resultados_dicts: list[dict[str, Any]], validation: dict[str, Any]) -> str:
    return f"Resumen ejecutivo para {tema}: {validation['score_calidad']:.2f} ({len(resultados_dicts)} agentes)"

    async def _run_agents(
        self, specs: list[AgentSpec], semaphore: asyncio.Semaphore
    ) -> list[AgentResult]:
        """Run agent specs with global concurrency bounded by `semaphore`."""
        tasks = [self._run_one_agent(spec, semaphore) for spec in specs]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _run_one_agent(self, spec: AgentSpec, semaphore: asyncio.Semaphore) -> AgentResult:
        async with semaphore:
            start = time.monotonic()
            result = AgentResult(
                agente_id=spec.agent_id,
                rol=spec.rol,
                subtema_asignado=spec.subtema,
                estado="error",
            )
            last_err: str | None = None
            for attempt in range(spec.max_retries):
                try:
                    data = await asyncio.wait_for(
                        spec.fn(spec.subtema, spec.maleta),
                        timeout=AGENT_TIMEOUT_S,
                    )
                    if isinstance(data, list):
                        result.resultados = data
                        result.estado = "ok"
                        break
                    last_err = f"retorno inválido: {type(data).__name__}"
                except TimeoutError:
                    last_err = f"timeout {AGENT_TIMEOUT_S}s"
                    result.estado = "timeout"
                except Exception as e:  # noqa: BLE001
                    last_err = f"{type(e).__name__}: {e}"
                    logger.warning(
                        "Agente %s intento %d falló: %s", spec.agent_id, attempt + 1, last_err
                    )
            if last_err and result.estado != "ok":
                result.errores.append(last_err)
            result.tiempo_segundos = time.monotonic() - start
            return result


def _agent_roles_from_maleta(maleta: dict[str, Any], n: int) -> list[str]:
    """Derive agent roles from the maleta's tool list; fill with 'buscador_generico'."""
    buscadores = (maleta.get("herramientas", {}) or {}).get("buscadores", []) or []
    nombres = [b.get("nombre", "buscador_generico") for b in buscadores]
    if not nombres:
        nombres = ["buscador_generico"]
    # Repeat/pad to length n
    return [nombres[i % len(nombres)] for i in range(n)]


def _summary(tema: str, resultados: list[dict[str, Any]], validation: dict[str, Any]) -> str:
    total_results = sum(len(r.get("resultados", []) or []) for r in resultados)
    alertas = validation.get("alertas", [])
    alertas_txt = f" | Alertas: {', '.join(alertas)}" if alertas else ""
    return (
        f"Tema: {tema} | Agentes: {len(resultados)} | "
        f"Resultados: {total_results} | Score: {validation['score_calidad']:.2f}"
        f"{alertas_txt}"
    )


def default_agent_factory(
    subtema: str,
    rol: str,
    maleta: dict[str, Any],
) -> AgentSpec:
    """Default agent: uses DDGClient. Safe for Fase 1 without SearXNG."""
    from core.ura_ddg_client import get_ddg_client

    client = get_ddg_client()
    max_results = int(maleta.get("division_subtemas", {}).get("resultados_por_agente", 8))

    async def _search(subtema_: str, maleta_: dict[str, Any]) -> list[dict[str, Any]]:
        mode = "news" if "noticias" in (maleta_.get("tema", "").lower()) else "text"
        raw = await client.search(subtema_, max_results=max_results, mode=mode)
        return [
            {
                "titulo": r["title"],
                "url": r["url"],
                "resumen": r["snippet"],
                "fecha": r.get("fecha"),
                "fuente_tipo": r.get("fuente_tipo"),
                "confianza": 0.6,
            }
            for r in raw
            if r.get("url")
        ]

    return AgentSpec(
        agent_id=f"agent_{uuid.uuid4().hex[:8]}",
        rol=rol,
        subtema=subtema,
        fn=_search,
        maleta=maleta,
    )


# Module-level convenience
_swarm: URASwarm | None = None


def get_swarm() -> URASwarm:
    global _swarm
    if _swarm is None:
        _swarm = URASwarm()
    return _swarm
