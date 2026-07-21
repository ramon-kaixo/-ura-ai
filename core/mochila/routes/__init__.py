from fastapi import APIRouter

from core.mochila.routes.breaker import create_breaker_router
from core.mochila.routes.chat import create_chat_router
from core.mochila.routes.health import create_health_router
from core.mochila.routes.memoria import create_memoria_router
from core.mochila.routes.metrics import create_metrics_router
from core.mochila.routes.models import create_models_router
from core.mochila.routes.proxy import create_proxy_router
from core.mochila.routes.status import create_status_router


def create_api_router(state) -> APIRouter:
    router = APIRouter()
    router.include_router(create_health_router(state))
    router.include_router(create_models_router(state))
    router.include_router(create_chat_router(state))
    router.include_router(create_breaker_router(state))
    router.include_router(create_metrics_router(state))
    router.include_router(create_proxy_router(state))
    router.include_router(create_memoria_router(state))
    router.include_router(create_status_router(state))
    return router
