#!/usr/bin/env python3
"""
Buscadores Adapter — N2 Infrastructure (Fase 2)

Adapta los 6 `core/buscadores/*.py` síncronos preexistentes a la API async que
espera el swarm N2: `agent_search(subtema: str, maleta: dict) -> list[dict]`.

Diseño:
- No modificamos los buscadores originales (estabilidad).
- Cada buscador se invoca en un thread vía `asyncio.to_thread()`.
- Normalizamos su salida al schema URA estándar.
- El factory genera un AgentSpec compatible con `URASwarm`.

Mapeo:
    buscador_noticias       → rol "noticias"
    buscador_estudios       → rol "estudios"
    buscador_aplicaciones   → rol "aplicaciones"
    buscador_documentacion  → rol "documentacion"
    buscador_manuales       → rol "manuales"
    buscador_tendencias     → rol "tendencias"
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable

from core.ura_swarm_local import AgentSpec

logger = logging.getLogger("buscadores_adapter")

AgentFn = Callable[[str, dict[str, Any]], Awaitable[list[dict[str, Any]]]]


def _normalize_result(raw: dict[str, Any], rol: str) -> dict[str, Any]:
    """Map a buscador raw output to the URA standard schema."""
    return {
        "titulo": raw.get("titulo") or raw.get("title") or raw.get("nombre") or "",
        "url": raw.get("url") or raw.get("link") or "",
        "resumen": raw.get("resumen") or raw.get("descripcion") or raw.get("body") or "",
        "fecha": raw.get("fecha") or raw.get("date") or None,
        "fuente_tipo": rol,
        "confianza": raw.get("confianza", 0.55),
        "_raw_keys": list(raw.keys()),
    }


# -----------------------------------------------------------------------------
# Async wrappers: each calls the legacy sync class in a worker thread
# -----------------------------------------------------------------------------


async def _call_sync_method(instance: Any, method: str, *args: Any) -> list[dict[str, Any]]:
    """Run `instance.method(*args)` in a thread and return the list result."""
    fn = getattr(instance, method, None)
    if fn is None:
        logger.error("Buscador %s carece de método %s", type(instance).__name__, method)
        return []
    try:
        return await asyncio.to_thread(fn, *args)
    except Exception as e:  # noqa: BLE001
        logger.warning("Buscador %s.%s falló: %s", type(instance).__name__, method, e)
        return []


async def agent_search_noticias(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_noticias import BuscadorNoticias

    inst = BuscadorNoticias()
    raw = await _call_sync_method(inst, "buscar_noticias")
    return [_normalize_result(r, "noticias") for r in (raw or []) if isinstance(r, dict)]


async def agent_search_estudios(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_estudios import BuscadorEstudios

    inst = BuscadorEstudios()
    raw = await _call_sync_method(inst, "buscar_estudios")
    return [_normalize_result(r, "estudios") for r in (raw or []) if isinstance(r, dict)]


async def agent_search_aplicaciones(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_aplicaciones import BuscadorAplicaciones

    inst = BuscadorAplicaciones()
    raw = await _call_sync_method(inst, "buscar_aplicaciones")
    return [_normalize_result(r, "aplicaciones") for r in (raw or []) if isinstance(r, dict)]


async def agent_search_documentacion(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_documentacion import BuscadorDocumentacion

    inst = BuscadorDocumentacion()
    categoria = maleta.get("categoria_documentacion") or "general"
    raw = await _call_sync_method(inst, "buscar_documentacion", subtema, categoria)
    return [_normalize_result(r, "documentacion") for r in (raw or []) if isinstance(r, dict)]


async def agent_search_manuales(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_manuales import BuscadorManuales

    inst = BuscadorManuales()
    # Buscador de manuales no expone un método unificado — intentamos los más comunes
    for method in ("buscar_manuales", "buscar", "ejecutar"):
        if hasattr(inst, method):
            raw = await _call_sync_method(inst, method)
            return [_normalize_result(r, "manuales") for r in (raw or []) if isinstance(r, dict)]
    return []


async def agent_search_tendencias(subtema: str, maleta: dict[str, Any]) -> list[dict[str, Any]]:
    from core.buscadores.buscador_tendencias import BuscadorTendencias

    inst = BuscadorTendencias()
    for method in ("buscar_tendencias", "buscar", "ejecutar"):
        if hasattr(inst, method):
            raw = await _call_sync_method(inst, method)
            return [_normalize_result(r, "tendencias") for r in (raw or []) if isinstance(r, dict)]
    return []


# -----------------------------------------------------------------------------
# Registry + factory
# -----------------------------------------------------------------------------


AGENT_REGISTRY: dict[str, AgentFn] = {
    "noticias": agent_search_noticias,
    "estudios": agent_search_estudios,
    "aplicaciones": agent_search_aplicaciones,
    "documentacion": agent_search_documentacion,
    "manuales": agent_search_manuales,
    "tendencias": agent_search_tendencias,
}


def buscadores_agent_factory(
    subtema: str,
    rol: str,
    maleta: dict[str, Any],
) -> AgentSpec:
    """
    Factory compatible con `URASwarm.run(agent_factory=...)`.

    El `rol` (definido por la maleta) selecciona el buscador legacy.
    Si el rol no está registrado, cae al DDG default.
    """
    rol_key = rol.lower()
    fn = AGENT_REGISTRY.get(rol_key)

    if fn is None:
        # fallback to DDG default if rol unknown
        from core.ura_swarm_local import default_agent_factory

        return default_agent_factory(subtema, rol, maleta)

    return AgentSpec(
        agent_id=f"buscador_{rol_key}_{uuid.uuid4().hex[:6]}",
        rol=rol_key,
        subtema=subtema,
        fn=fn,
        maleta=maleta,
    )


def list_available_roles() -> list[str]:
    """Return the list of buscador roles registered for the swarm."""
    return sorted(AGENT_REGISTRY.keys())
