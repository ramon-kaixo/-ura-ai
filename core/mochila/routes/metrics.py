from typing import Any

from fastapi import APIRouter, HTTPException


def create_metrics_router(state: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/metrics/rate/{provider}")
    async def rate_limit_status(provider: str) -> Any:
        if provider not in state.providers:
            raise HTTPException(status_code=404, detail=f"Provider {provider} no encontrado")
        return state.rate_limiter.estado(provider)

    @router.get("/metrics/cost")
    async def cost_summary() -> Any:
        return state.cost_tracker.resumen_hoy()

    @router.post("/admin/acquire_boot_vram")
    async def admin_acquire_boot_vram(mb: int) -> dict[str, str]:
        await state.scheduler.acquire_boot_vram(mb)
        return {"status": "granted"}

    return router
