import time
from typing import Any, cast

from fastapi import APIRouter


def create_models_router(state: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/models")
    async def v1_models() -> dict[str, Any]:
        if state.cache_models and time.time() - state.cache_models_ts < 60:
            return cast("dict[str, Any]", state.cache_models)
        models = []
        for name, provider in state.providers.items():
            h = await provider.health()
            if h.get("status") == "ok" and "modelos_disponibles" in h:
                for m in h["modelos_disponibles"][:50]:
                    models.append({"id": f"{name}/{m}", "provider": name, "object": "model"})
            models.append({"id": f"{name}/auto", "provider": name, "object": "model"})
        for ruta in state.router.rutas.values():
            for entrada in ruta:
                mid = f"{entrada['provider']}/{entrada['modelo']}"
                if not any(m["id"] == mid for m in models):
                    models.append({"id": mid, "provider": entrada["provider"], "object": "model"})
        payload: dict[str, Any] = {"object": "list", "data": models}
        state.cache_models = payload
        state.cache_models_ts = time.time()
        return payload

    return router
