"""Tests for core/mochila/vram_scheduler.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mochila.vram_scheduler import VRAMAwareScheduler


@pytest.fixture
def scheduler(monkeypatch):
    with patch.object(VRAMAwareScheduler, "_detect_max_vram", return_value=100000):
        s = VRAMAwareScheduler()
    s._ollama_client = AsyncMock()
    return s


class TestDetectMaxVram:
    def test_nvidia_smi_ok(self):
        with patch("core.mochila.vram_scheduler.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "128000\n"
            assert VRAMAwareScheduler._detect_max_vram(50000) == 128000

    def test_nvidia_smi_fallo_devuelve_default(self):
        with patch("core.mochila.vram_scheduler.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            assert VRAMAwareScheduler._detect_max_vram(50000) == 50000

    def test_nvidia_smi_na_devuelve_default(self):
        with patch("core.mochila.vram_scheduler.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "N/A\n"
            assert VRAMAwareScheduler._detect_max_vram(50000) == 50000

    def test_excepcion_devuelve_default(self):
        with patch("core.mochila.vram_scheduler.subprocess.run", side_effect=OSError("boom")):
            assert VRAMAwareScheduler._detect_max_vram(50000) == 50000


class TestEstimarVram:
    def test_vram_explicito(self):
        assert VRAMAwareScheduler.estimar_vram({"_vram_mb": 4000}) == 4000

    def test_modelo_conocido(self):
        assert VRAMAwareScheduler.estimar_vram({"model": "qwen2.5-coder:14b"}) == 9000

    def test_modelo_desconocido_base_512(self):
        assert VRAMAwareScheduler.estimar_vram({"model": "otro"}) == 512

    def test_prompt_largo_incrementa(self):
        a = VRAMAwareScheduler.estimar_vram({"model": "otro", "prompt": ""})
        b = VRAMAwareScheduler.estimar_vram({"model": "otro", "prompt": "x" * 8000})
        assert b > a

    def test_messages_como_fuente(self):
        v = VRAMAwareScheduler.estimar_vram({"model": "otro", "messages": "x" * 8000})
        assert v == 512 + int((8000 // 4) * 0.002)


class TestAvailableMb:
    def test_inicial(self, scheduler):
        assert scheduler.available_mb() == 100000

    def test_tras_fijar_current(self, scheduler):
        scheduler._current_mb = 25000
        assert scheduler.available_mb() == 75000


class TestAcquireRelease:
    @pytest.mark.asyncio
    async def test_adquiere_inmediato(self, scheduler):
        req_id = await scheduler.acquire(1000, data={"model": "llama3.2:3b"})
        assert req_id is not None
        assert req_id in scheduler._active
        assert scheduler._active[req_id]["model"] == "llama3.2:3b"

    @pytest.mark.asyncio
    async def test_no_permite_segunda_activa(self, scheduler):
        await scheduler.acquire(1000)
        req2 = await scheduler.acquire(1000)
        assert req2 is None

    @pytest.mark.asyncio
    async def test_release_libera(self, scheduler):
        req_id = await scheduler.acquire(1000)
        await scheduler.release(req_id)
        req2 = await scheduler.acquire(1000)
        assert req2 is not None

    @pytest.mark.asyncio
    async def test_release_inexistente_no_rompe(self, scheduler):
        await scheduler.release("nope")

    @pytest.mark.asyncio
    async def test_sin_vram_se_encola_y_timeout(self, scheduler):
        scheduler._current_mb = 99900
        req = await scheduler.acquire(500, deadline_flex=0.1)
        assert req is None

    @pytest.mark.asyncio
    async def test_encolado_resuelto_por_scheduler_loop(self, scheduler):
        scheduler._current_mb = 99990
        async def run():
            task = asyncio.create_task(scheduler.acquire(100, deadline_flex=5))
            await asyncio.sleep(0.01)
            scheduler._current_mb = 0
            scheduler._queue[0][3]["model"] = "test"
            await scheduler._scheduler_loop_once()
            return await asyncio.wait_for(task, timeout=2)
        req_id = await run()
        assert req_id is not None
        assert req_id in scheduler._active


class TestSyncVram:
    @pytest.mark.asyncio
    async def test_actualiza_current_mb(self, scheduler):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"1234\n567\n", b"")
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", return_value=proc):
            await scheduler.sync_vram()
        assert scheduler._current_mb == 1801

    @pytest.mark.asyncio
    async def test_timeout_incrementa_contador(self, scheduler):
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", side_effect=TimeoutError):
            await scheduler.sync_vram()
        assert scheduler._consecutive_smi_errors == 1

    @pytest.mark.asyncio
    async def test_bloquea_tras_3_errores(self, scheduler):
        scheduler._consecutive_smi_errors = 2
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", side_effect=TimeoutError):
            await scheduler.sync_vram()
        assert scheduler._current_mb == scheduler.max_mb

    @pytest.mark.asyncio
    async def test_error_generico(self, scheduler):
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", side_effect=OSError("boom")):
            await scheduler.sync_vram()
        assert scheduler._consecutive_smi_errors == 1

    @pytest.mark.asyncio
    async def test_ollama_ps_actualiza_hot_models(self, scheduler):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"", b"")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"models": [{"name": "llama3:8b"}, {"name": "qwen2:7b"}]}
        scheduler._ollama_client.get = AsyncMock(return_value=resp)
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", return_value=proc):
            await scheduler.sync_vram()
        assert scheduler._hot_models == {"llama3:8b", "qwen2:7b"}

    @pytest.mark.asyncio
    async def test_ollama_ps_error_no_rompe(self, scheduler):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"", b"")
        scheduler._ollama_client.get = AsyncMock(side_effect=OSError("conn"))
        with patch("core.mochila.vram_scheduler.asyncio.create_subprocess_exec", return_value=proc):
            await scheduler.sync_vram()
        assert scheduler._hot_models == set()


class TestBootVRAM:
    @pytest.mark.asyncio
    async def test_adquiere_boot(self, scheduler):
        async def run():
            task = asyncio.create_task(scheduler.acquire_boot_vram(100))
            await asyncio.sleep(0.01)
            scheduler._current_mb = 0
            scheduler._queue[0][3]["model"] = "static_boot_service"
            await scheduler._scheduler_loop_once()
            return await asyncio.wait_for(task, timeout=2)
        assert await run() is True

    @pytest.mark.asyncio
    async def test_boot_timeout(self, scheduler):
        scheduler._current_mb = 99999
        with patch("core.mochila.vram_scheduler.asyncio.wait_for", side_effect=TimeoutError):
            assert await scheduler.acquire_boot_vram(500) is False


class TestLoopControl:
    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        await scheduler.start_loop()
        assert scheduler._task is not None
        await scheduler.stop_loop()
        try:
            await scheduler._task
        except asyncio.CancelledError:
            pass
        assert scheduler._task.cancelled()

    @pytest.mark.asyncio
    async def test_close(self, scheduler):
        await scheduler.start_loop()
        await scheduler.close()
        scheduler._ollama_client.aclose.assert_awaited_once()
