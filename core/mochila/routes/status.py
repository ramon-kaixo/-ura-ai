from fastapi import APIRouter

from core.mochila.status_endpoint import system_status
from core.mochila.tools import TOOL_SCHEMAS


def create_status_router(state) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    async def system_status_endpoint():
        return await system_status(state.providers, state.cost_tracker, state.circuit_breaker, len(TOOL_SCHEMAS), state.router)

    @router.get("/metrics")
    async def metrics():
        return {
            "providers": list(state.providers.keys()),
            "timeouts": state.provider_timeouts,
            "rutas": {k: [e["provider"] + "/" + e["modelo"] for e in v] for k, v in state.router.rutas.items()},
            "clasificador": type(state.router.clasificador).__name__,
            "circuit_breaker": {p: state.circuit_breaker.estado(p) for p in state.providers},
            "cost_hoy": state.cost_tracker.resumen_hoy(),
            "tools_disponibles": len(TOOL_SCHEMAS),
        }

    return router
