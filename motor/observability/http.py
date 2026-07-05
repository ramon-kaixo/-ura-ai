from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.observability.health import HealthRegistry
    from motor.observability.metrics import MetricsRegistry
    from motor.observability.readiness import ReadinessRegistry

log = logging.getLogger("ura.observability.http")


def create_router(
    metrics: MetricsRegistry,
    health: HealthRegistry,
    readiness: ReadinessRegistry,
):
    try:
        from fastapi import APIRouter
    except ImportError:
        log.error("FastAPI no disponible — no se puede crear router HTTP")
        return None

    router = APIRouter()

    @router.get("/metrics")
    def get_metrics():
        return metrics.snapshot()

    @router.get("/health")
    def get_health():
        return health.snapshot()

    @router.get("/ready")
    def get_ready():
        return readiness.snapshot()

    return router
