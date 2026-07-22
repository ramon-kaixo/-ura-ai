import time

from fastapi import APIRouter


def create_models_router(state) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/models")
    async def v1_models():
        if state.cache_models and time.time() - state.cache_models_ts < 60:
            return state.cache_models
        models = []
        for name, provider in state.providers.items():
            h = await provider.health()
            if h.get("status") == "ok" and "modelos_disponibles" in h:
                for m in h["modelos_disponibles"][:50]:
                    models.append({"id": f"{name}/{m}", "provider": name, "object": "model"})  # noqa: PERF401
            models.append({"id": f"{name}/auto", "provider": name, "object": "model"})
        for ruta in state.router.rutas.values():
            for entrada in ruta:
                mid = f"{entrada['provider']}/{entrada['modelo']}"
                if not any(m["id"] == mid for m in models):
                    models.append({"id": mid, "provider": entrada["provider"], "object": "model"})
        state.cache_models = models
        state.cache_models_ts = time.time()
        return {"object": "list", "data": models}

    return router
