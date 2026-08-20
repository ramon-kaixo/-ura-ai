"""Tests cobertura mochila_server — VRAM scheduler (split)."""
from __future__ import annotations

from _mochila_helpers import AsyncMock, Mock, asyncio, httpx, pytest, subprocess, time


class TestVRAMScheduler:
    def test_detect_max_vram_ok(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        fake = Mock(
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="4096\n")
        )
        monkeypatch.setattr(subprocess, "run", fake)
        assert VRAMAwareScheduler._detect_max_vram(100) == 4096

    def test_detect_max_vram_na_stdout(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        fake = Mock(
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="N/A\n")
        )
        monkeypatch.setattr(subprocess, "run", fake)
        assert VRAMAwareScheduler._detect_max_vram(100) == 100

    def test_detect_max_vram_returncode(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        fake = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout=""))
        monkeypatch.setattr(subprocess, "run", fake)
        assert VRAMAwareScheduler._detect_max_vram(100) == 100

    def test_detect_max_vram_excepcion(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        fake = Mock(side_effect=OSError("no nvidia-smi"))
        monkeypatch.setattr(subprocess, "run", fake)
        assert VRAMAwareScheduler._detect_max_vram(100) == 100

    async def test_available_mb(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 40
        assert s.available_mb() == 60

    def test_estimar_vram_explicito(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        assert VRAMAwareScheduler.estimar_vram({"_vram_mb": "123"}) == 123

    def test_estimar_vram_modelos_conocidos(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        assert VRAMAwareScheduler.estimar_vram({"model": "qwen2.5-coder:32b"}) == 18000
        assert VRAMAwareScheduler.estimar_vram({"model": "llama3.2:3b"}) == 2500

    def test_estimar_vram_desconocido_con_overhead(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        prompt = "x" * 2000
        esperado = 512 + int((len(prompt) // 4) * 0.002)
        assert VRAMAwareScheduler.estimar_vram({"model": "otro", "prompt": prompt}) == esperado

    def test_estimar_vram_messages(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        esperado = 512 + int((len(str(["a"])) // 4) * 0.002)
        assert VRAMAwareScheduler.estimar_vram({"model": "x", "messages": ["a"]}) == esperado

    async def test_sync_vram_ok(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            def __init__(self, stdout: bytes) -> None:
                self._stdout = stdout

            async def communicate(self) -> tuple[bytes, bytes]:
                return self._stdout, b""

        proc = FakeProc(b"100\n200\n")
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))

        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = Mock(return_value={"models": [{"name": "llama3"}, {"name": "qwen2"}]})
        s._ollama_client.get = AsyncMock(return_value=resp)

        await s.sync_vram()
        assert s._current_mb == 300
        assert s._hot_models == {"llama3", "qwen2"}
        assert s._consecutive_smi_errors == 0

    async def test_sync_vram_timeout(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        async def fake_wait_for(_coro, *, timeout):  # noqa: ASYNC109
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        s._consecutive_smi_errors = 0
        await s.sync_vram()
        assert s._consecutive_smi_errors == 1
        assert s._current_mb == 0

    async def test_sync_vram_errores_consecutivos_bloquean(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        async def fake_wait_for(_coro, *, timeout):  # noqa: ASYNC109
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        s._consecutive_smi_errors = 2
        await s.sync_vram()
        assert s._consecutive_smi_errors == 3
        assert s._current_mb == 1000

    async def test_sync_vram_wait_for_error_generico(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        async def fake_wait_for(_coro, *, timeout):  # noqa: ASYNC109
            raise OSError("nvidia-smi no existe")

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        s._consecutive_smi_errors = 2
        await s.sync_vram()
        assert s._consecutive_smi_errors == 3
        assert s._current_mb == 1000

    async def test_sync_vram_ollama_ps_error(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"50\n", b""

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        s._ollama_client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        await s.sync_vram()
        assert s._current_mb == 50

    async def test_sync_vram_ollama_ps_no_200(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"50\n", b""

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        resp = AsyncMock()
        resp.status_code = 500
        s._ollama_client.get = AsyncMock(return_value=resp)
        await s.sync_vram()
        assert s._hot_models == set()

    async def test_sync_vram_linea_vacia(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"100\n\n200\n", b""

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = Mock(return_value={"models": []})
        s._ollama_client.get = AsyncMock(return_value=resp)
        await s.sync_vram()
        assert s._current_mb == 300

    async def test_sync_vram_returncode_no_cero(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 1

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"100\n", b""

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = Mock(return_value={"models": []})
        s._ollama_client.get = AsyncMock(return_value=resp)
        await s.sync_vram()
        assert s._current_mb == 0

    async def test_sync_vram_communicate_timeout_kill(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0
            kill_called = False
            wait_called = False

            async def communicate(self) -> tuple[bytes, bytes]:
                raise TimeoutError

            def kill(self) -> None:
                self.kill_called = True

            async def wait(self) -> None:
                self.wait_called = True

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        await s.sync_vram()
        assert proc.kill_called is True
        assert proc.wait_called is True

    async def test_sync_vram_communicate_error_kill(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0
            kill_called = False
            wait_called = False

            async def communicate(self) -> tuple[bytes, bytes]:
                raise OSError("roto")

            def kill(self) -> None:
                self.kill_called = True

            async def wait(self) -> None:
                self.wait_called = True

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        await s.sync_vram()
        assert proc.kill_called is True
        assert proc.wait_called is True

    async def test_sync_vram_kill_lanza_timeout(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                raise TimeoutError

            def kill(self) -> None:
                raise OSError("no se puede matar")

            async def wait(self) -> None:
                return None

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        await s.sync_vram()
        assert s._consecutive_smi_errors == 1

    async def test_sync_vram_kill_lanza_generico(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                raise OSError("roto")

            def kill(self) -> None:
                raise OSError("no se puede matar")

            async def wait(self) -> None:
                return None

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        await s.sync_vram()
        assert s._consecutive_smi_errors == 1

    async def test_sync_vram_bloqueo_generico(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        class FakeProc:
            returncode = 0
            kill_called = False
            wait_called = False

            async def communicate(self) -> tuple[bytes, bytes]:
                raise OSError("roto")

            def kill(self) -> None:
                self.kill_called = True

            async def wait(self) -> None:
                self.wait_called = True

        proc = FakeProc()
        monkeypatch.setattr("asyncio.create_subprocess_exec", AsyncMock(return_value=proc))
        s = VRAMAwareScheduler(default_max_mb=1000)
        s._ollama_client = AsyncMock()
        s._consecutive_smi_errors = 2
        await s.sync_vram()
        assert s._consecutive_smi_errors == 3
        assert s._current_mb == 1000

    async def test_acquire_disponible(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 0
        req_id = await s.acquire(10)
        assert req_id is not None
        assert len(s._active) == 1
        assert req_id in s._active

    async def test_acquire_con_activo_devuelve_none(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._active["ocupado"] = {"mb": 10, "ts": time.time(), "model": "x"}
        assert await s.acquire(5) is None

    async def test_acquire_cola_timeout(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        async def fake_wait_for(_coro, *, timeout):  # noqa: ASYNC109
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 100
        assert await s.acquire(10, deadline_flex=0.05) is None

    async def test_acquire_cola_resuelto(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 100
        task = asyncio.create_task(s.acquire(10, deadline_flex=10))
        await asyncio.sleep(0.05)
        fut, _mb, _dl, _data = s._queue[0]
        fut.set_result("req-7")
        assert await task == "req-7"

    async def test_acquire_boot_vram_timeout(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        async def fake_wait_for(_coro, *, timeout):  # noqa: ASYNC109
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        assert await s.acquire_boot_vram(10) is False

    async def test_acquire_boot_vram_ok(self, monkeypatch):
        from core.mochila.mochila_server import VRAMAwareScheduler

        real_sleep = asyncio.sleep

        async def fake_sleep(delay):
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        task = asyncio.create_task(s.acquire_boot_vram(10))
        await real_sleep(0.05)
        fut, _mb, _dl, _data = s._queue[0]
        fut.set_result("req-8")
        assert await task is True
        await real_sleep(0.05)
        assert "req-8" not in s._active

    async def test_release(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._active["r1"] = {"mb": 1, "ts": 1.0, "model": "x"}
        await s.release("r1")
        assert s._active == {}

    async def test_start_stop_close(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s.sync_vram = AsyncMock()
        await s.start_loop()
        assert s._task is not None
        task = s._task
        await s.stop_loop()
        with pytest.raises(asyncio.CancelledError):
            await task
        await s.close()

    async def test_stop_loop_sin_task(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        await s.stop_loop()
        assert s._task is None

    async def test_scheduler_loop_future_done_no_resuelve(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 50
        s.sync_vram = AsyncMock()

        fut = asyncio.get_running_loop().create_future()
        fut.set_result("ya")
        now = time.time()
        s._queue = [(fut, 10, now + 100, {"model": "done"})]
        task = asyncio.create_task(s._scheduler_loop())
        await asyncio.sleep(0.7)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert s._active == {}

    async def test_scheduler_loop_sin_vram_no_resuelve(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 100
        s.sync_vram = AsyncMock()

        fut = asyncio.get_running_loop().create_future()
        now = time.time()
        s._queue = [(fut, 90, now + 100, {"model": "grande"})]
        task = asyncio.create_task(s._scheduler_loop())
        await asyncio.sleep(0.7)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fut.done() is False
        assert s._active == {}

    async def test_scheduler_loop_resuelve_cola(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()
        s._current_mb = 50
        s.sync_vram = AsyncMock()

        fut1 = asyncio.get_running_loop().create_future()
        fut2 = asyncio.get_running_loop().create_future()
        now = time.time()
        s._queue = [
            (fut1, 10, now - 1, {"model": "vencido"}),
            (fut2, 20, now + 100, {"model": "ok"}),
        ]
        task = asyncio.create_task(s._scheduler_loop())
        await asyncio.sleep(1.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fut1.done() is False
        assert fut2.done() is True
        assert len(s._active) == 1

    async def test_scheduler_loop_error(self):
        from core.mochila.mochila_server import VRAMAwareScheduler

        s = VRAMAwareScheduler(default_max_mb=100)
        s._ollama_client = AsyncMock()

        async def explota() -> None:
            raise RuntimeError("boom")

        s.sync_vram = explota
        task = asyncio.create_task(s._scheduler_loop())
        await asyncio.sleep(0.7)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


