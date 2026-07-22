from fastapi import APIRouter, HTTPException


def create_breaker_router(state) -> APIRouter:
    router = APIRouter()

    @router.get("/breaker")
    async def breaker_status():
        return {p: state.circuit_breaker.estado(p) for p in state.providers}

    @router.post("/breaker/reset/{provider}")
    async def breaker_reset(provider: str):
        if provider not in state.providers:
            raise HTTPException(status_code=404, detail=f"Provider {provider} no encontrado")
        state.circuit_breaker.reset(provider)
        return {"status": "reset", "provider": provider}

    return router
