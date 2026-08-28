from typing import Any

from fastapi import APIRouter, HTTPException


def create_breaker_router(state: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/breaker")
    async def breaker_status() -> dict[str, Any]:
        return {p: state.circuit_breaker.estado(p) for p in state.providers}

    @router.post("/breaker/reset/{provider}")
    async def breaker_reset(provider: str) -> dict[str, str]:
        if provider not in state.providers:
            raise HTTPException(status_code=404, detail=f"Provider {provider} no encontrado")
        state.circuit_breaker.reset(provider)
        return {"status": "reset", "provider": provider}

    return router
