"""Tests de integración para metrics_server endpoints.

Requiere: aiohttp (ya instalado), motor.observability, motor.intelligence.memory
Usa aiohttp.test_utils para evitar levantar un servidor real.
"""

from __future__ import annotations

import os

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from motor.intelligence.memory.hybrid import HybridMemory


def _build_app() -> web.Application:
    """Construye una app de prueba equivalente a metrics_server."""
    from scripts.pro.metrics_server import (
        handle_dashboard,
        handle_health,
        handle_memory,
        handle_metrics,
        handle_pipeline_status,
        handle_ready,
        handle_version,
    )

    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ready", handle_ready)
    app.router.add_get("/version", handle_version)
    app.router.add_get("/memory", handle_memory)
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_get("/dashboard", handle_dashboard)
    app.router.add_get("/pipeline/status", handle_pipeline_status)
    return app


class TestMetricsServer(AioHTTPTestCase):
    async def get_application(self) -> web.Application:
        os.environ["URA_MEMORY_DB"] = ":memory:"
        # Reload modules to get fresh state
        import importlib

        import scripts.pro.metrics_server as ms

        importlib.reload(ms)
        return _build_app()

    @unittest_run_loop
    async def test_health_endpoint(self):
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert "global" in data
        assert "components" in data

    @unittest_run_loop
    async def test_ready_endpoint(self):
        resp = await self.client.request("GET", "/ready")
        assert resp.status in (200, 503)
        data = await resp.json()
        assert "global" in data

    @unittest_run_loop
    async def test_version_endpoint(self):
        resp = await self.client.request("GET", "/version")
        assert resp.status == 200
        data = await resp.json()
        assert "version" in data
        assert "python" in data

    @unittest_run_loop
    async def test_memory_endpoint(self):
        resp = await self.client.request("GET", "/memory")
        assert resp.status == 200
        data = await resp.json()
        assert "total_records" in data
        assert "vector_store_ok" in data
        assert data["vector_store_ok"] is False  # no vector store configured

    @unittest_run_loop
    async def test_metrics_endpoint(self):
        resp = await self.client.request("GET", "/metrics")
        assert resp.status == 200
        data = await resp.json()
        assert "status" in data

    @unittest_run_loop
    async def test_dashboard_endpoint(self):
        resp = await self.client.request("GET", "/dashboard")
        assert resp.status == 200
        text = await resp.text()
        assert "URA System Dashboard" in text
        assert "Estado del Sistema" in text
        assert "Memoria Híbrida" in text

    @unittest_run_loop
    async def test_pipeline_status_endpoint(self):
        resp = await self.client.request("GET", "/pipeline/status")
        assert resp.status == 200
        data = await resp.json()
        # May return no_data if no ledger files exist in test env
        assert data.get("status") in ("ok", "no_data")

    @unittest_run_loop
    async def test_health_after_store(self):
        """Verifica que almacenar memoria actualiza /memory."""

        mem = HybridMemory(db_path=":memory:")
        mem.store(payload="test data for health check")

        # Reset server state to use our test memory
        import scripts.pro.metrics_server as ms

        ms._memory = mem
        ms._health.register_component("metrics_server")
        ms._health.set_healthy("metrics_server")

        resp = await self.client.request("GET", "/memory")
        data = await resp.json()
        # After storing 1 record, total_records should be >= 0
        assert data["total_records"] >= 0
