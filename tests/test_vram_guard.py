"""Tests para ConcurrentVRAMGuard (core/model_router.py)."""
import asyncio
import time

import pytest

from core.model_router import ConcurrentVRAMGuard, vram_guard


class TestVRAMGuard:
    def test_metricas_structure(self):
        m = vram_guard.metricas()
        assert "max_concurrent" in m
        assert "slots_disponibles" in m
        assert "esperando_cola" in m
        assert "ttl_segundos" in m
        assert "total_enqueue" in m
        assert "total_timeout" in m
        assert "total_processed" in m

    def test_slots_disponibles_property(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=2)
        assert g.slots_disponibles == 2

    @pytest.mark.asyncio
    async def test_acquire_release_happy_path(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5)
        ok = await g.adquirir_slot_vram("test-model")
        assert ok is True
        assert g.slots_disponibles == 0
        await g.liberar_slot_vram("test-model")
        assert g.slots_disponibles == 1

    @pytest.mark.asyncio
    async def test_timeout_returns_false(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=0.1)
        ok1 = await g.adquirir_slot_vram("m1")
        assert ok1 is True
        ok2 = await g.adquirir_slot_vram("m2")
        assert ok2 is False

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5)
        adquirido = await g.adquirir_slot_vram("m1")
        assert adquirido is True

        task = asyncio.create_task(g.adquirir_slot_vram("m2"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)
        await g.liberar_slot_vram("m1")

    @pytest.mark.asyncio
    async def test_metricas_after_operations(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5)
        await g.adquirir_slot_vram("m1")
        await g.liberar_slot_vram("m1")
        m = g.metricas()
        assert m["total_processed"] >= 1
        assert m["total_timeout"] == 0
        assert m["max_concurrent"] == 1

    @pytest.mark.asyncio
    async def test_ejecutar_inferencia_segura_happy(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5)

        async def dummy():
            return "ok"

        result = await g.ejecutar_inferencia_segura(dummy)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_ejecutar_inferencia_segura_enqueue_metric(self):
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5)

        async def dummy():
            return "ok"

        result = await g.ejecutar_inferencia_segura(dummy)
        assert result == "ok"
        assert g._total_enqueue >= 1
