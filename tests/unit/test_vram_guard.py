"""Tests para core/model_router/vram_guard.py — ConcurrentVRAMGuard."""
from __future__ import annotations

import asyncio
from unittest import mock

import pytest

from core.model_router.vram_guard import ConcurrentVRAMGuard, vram_guard


@pytest.fixture
def guard() -> ConcurrentVRAMGuard:
    return ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=1.0)


class TestPropiedades:
    def test_slots_iniciales(self, guard: ConcurrentVRAMGuard) -> None:
        assert guard.slots_disponibles == 1

    def test_esperando_cola_inicial(self, guard: ConcurrentVRAMGuard) -> None:
        assert guard.esperando_cola == 0

    def test_metricas(self, guard: ConcurrentVRAMGuard) -> None:
        m = guard.metricas()
        assert m["max_concurrent"] == 1
        assert m["slots_disponibles"] == 1
        assert m["ttl_segundos"] == 1.0
        assert m["total_enqueue"] == 0
        assert m["total_timeout"] == 0
        assert m["total_processed"] == 0


class TestEjecutarInferenciaSegura:
    @pytest.mark.asyncio
    async def test_ejecuta_corutina(self, guard: ConcurrentVRAMGuard) -> None:
        async def dummy():
            return "resultado"

        r = await guard.ejecutar_inferencia_segura(dummy)
        assert r == "resultado"
        assert guard.metricas()["total_processed"] == 1
        assert guard.metricas()["total_enqueue"] == 1

    @pytest.mark.asyncio
    async def test_respeta_semaphore(self, guard: ConcurrentVRAMGuard) -> None:
        liberaciones = []

        async def dummy():
            liberaciones.append(1)
            await asyncio.sleep(0.05)
            return "ok"

        async def lanzador():
            return await guard.ejecutar_inferencia_segura(dummy)

        resultados = await asyncio.gather(lanzador(), lanzador())
        assert len(resultados) == 2
        # Ambos procesados (el segundo espera al primero)
        assert guard.metricas()["total_processed"] == 2

    @pytest.mark.asyncio
    async def test_sin_espera_no_timeout(self, guard: ConcurrentVRAMGuard) -> None:
        async def dummy():
            return "ok"

        with mock.patch.object(guard, "_ttl", 0.0001):
            # Sin contención no hay espera -> no timeout
            r = await guard.ejecutar_inferencia_segura(dummy)
        assert r == "ok"
        assert guard.metricas()["total_timeout"] == 0


class TestAdquirirLiberar:
    @pytest.mark.asyncio
    async def test_adquirir_ok(self, guard: ConcurrentVRAMGuard) -> None:
        ok = await guard.adquirir_slot_vram("modelo1")
        assert ok is True
        assert guard.slots_disponibles == 0
        assert guard.metricas()["total_processed"] == 1

    @pytest.mark.asyncio
    async def test_adquirir_timeout(self) -> None:
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=0.05)
        await g.adquirir_slot_vram("m1")  # ocupa el slot
        ok = await g.adquirir_slot_vram("m2")  # debe expirar
        assert ok is False
        assert g.metricas()["total_timeout"] == 1

    @pytest.mark.asyncio
    async def test_adquirir_cancelado(self, guard: ConcurrentVRAMGuard) -> None:
        await guard.adquirir_slot_vram("m1")
        tarea = asyncio.create_task(guard.adquirir_slot_vram("m2"))
        await asyncio.sleep(0.05)
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    @pytest.mark.asyncio
    async def test_liberar(self, guard: ConcurrentVRAMGuard) -> None:
        await guard.adquirir_slot_vram("m1")
        await guard.liberar_slot_vram("m1")
        assert guard.slots_disponibles == 1

    @pytest.mark.asyncio
    async def test_ttl_personalizado(self) -> None:
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5.0)
        await g.adquirir_slot_vram("m1")
        # ttl corto para esta llamada -> timeout rapido
        ok = await g.adquirir_slot_vram("m2", ttl=0.01)
        assert ok is False


class TestSingleton:
    def test_vram_guard_instancia(self) -> None:
        assert isinstance(vram_guard, ConcurrentVRAMGuard)
        assert vram_guard._max_jobs == 1


class TestCrossLoop:
    """Regression: asyncio.run() por peticion crea loops efimeros distintos;
    el semaforo no debe quedar ligado a un event loop concreto."""

    def test_dos_loops_consecutivos_sin_contencion(self) -> None:
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=5.0)

        async def dummy() -> str:
            return "ok"

        # Loop A (primera peticion)
        r1 = asyncio.run(g.ejecutar_inferencia_segura(dummy))
        # Loop B (segunda peticion, loop nuevo)
        r2 = asyncio.run(g.ejecutar_inferencia_segura(dummy))
        assert r1 == "ok"
        assert r2 == "ok"

    def test_dos_loops_con_contencion(self) -> None:
        g = ConcurrentVRAMGuard(max_concurrent_jobs=1, ttl_segundos=2.0)

        def worker(delay: float) -> str:
            async def tarea() -> str:
                ok = await g.adquirir_slot_vram("m")
                if not ok:
                    return "timeout"
                try:
                    await asyncio.sleep(delay)
                    return "ok"
                finally:
                    await g.liberar_slot_vram("m")

            return asyncio.run(tarea())

        import threading

        resultados: list[str] = []

        def t1() -> None:
            resultados.append(worker(0.1))

        def t2() -> None:
            resultados.append(worker(0.01))

        h1 = threading.Thread(target=t1)
        h2 = threading.Thread(target=t2)
        h1.start()
        h2.start()
        h1.join()
        h2.join()
        assert sorted(resultados) == ["ok", "ok"]
        assert g.slots_disponibles == 1
