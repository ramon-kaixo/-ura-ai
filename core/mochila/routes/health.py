from typing import Any

from fastapi import APIRouter


def create_health_router(state: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "providers": {name: await p.health() for name, p in state.providers.items()}}

    return router
