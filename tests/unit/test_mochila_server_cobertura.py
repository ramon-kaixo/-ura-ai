"""Tests de cobertura para core/mochila/mochila_server.py — TASK-20260815-003 P2.

Cubre las zonas sin testear del servidor FastAPI de la mochila:
scheduler VRAM (todo el ciclo de vida), lifespan, helpers de stream/guardian,
tool calls, proxy gateway, endpoints de memoria y ramas del router/models.
"""

import asyncio
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


class FakeProvider:
    def __init__(self, nombre: str, modelos: list[str] | None = None) -> None:
        self.nombre = nombre
        self.modelos = modelos or [f"{nombre}-modelo-1", f"{nombre}-modelo-2"]
        self.llamadas: list[dict] = []

    async def health(self) -> dict:
        return {"status": "ok", "modelos_disponibles": self.modelos, "latencia_ms": 1.0}

    async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
        self.llamadas.append({"modelo": modelo, "stream": stream, "mensajes": mensajes})
        if stream:
            yield {
                "choices": [{"index": 0, "delta": {"content": "hola"}, "finish_reason": None}],
                "usage": None,
            }
            yield {
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            return
        yield {
            "id": "resp-1",
            "object": "chat.completion",
            "created": 1,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "respuesta"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


@pytest.fixture(scope="module")
def ms():
    import core.mochila.mochila_server as module
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter

    tmp = Path(tempfile.mkdtemp(prefix="mochila_cov_"))

    originales = {
        "_API_KEY": module._API_KEY,
        "PROVIDERS": module.PROVIDERS,
        "PROVIDER_TIMEOUTS": module.PROVIDER_TIMEOUTS,
        "CACHE_MODELS": module.CACHE_MODELS,
        "CACHE_MODELS_TS": module.CACHE_MODELS_TS,
        "scheduler": module.scheduler,
        "cost_tracker": module.cost_tracker,
        "rate_limiter": module.rate_limiter,
        "circuit_breaker": module.circuit_breaker,
        "router": module.router,
    }

    module._API_KEY = "test-key"
    module.PROVIDERS = {
        "ollama": FakeProvider("ollama"),
        "openrouter": FakeProvider("openrouter"),
        "gemini": FakeProvider("gemini"),
    }
    module.PROVIDER_TIMEOUTS = {"ollama": 120.0, "openrouter": 60.0, "gemini": 30.0}
    module.CACHE_MODELS = []
    module.CACHE_MODELS_TS = 0
    module.cost_tracker = CostTracker(cost_file=tmp / "costs.jsonl")
    module.rate_limiter = RateLimiter()
    module.circuit_breaker = CircuitBreaker(health_file=tmp / "health.json")

    scheduler = AsyncMock()
    scheduler.estimar_vram = lambda body: 10
    scheduler.acquire = AsyncMock(return_value="req-1")
    scheduler.release = AsyncMock()
    module.scheduler = scheduler

    module.router = module.Router(providers=module.PROVIDERS)

    yield module

    for nombre, valor in originales.items():
        setattr(module, nombre, valor)


@pytest.fixture
def client(ms):
    return TestClient(ms.app)


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


class TestLifespan:
    def test_lifespan_arranca_y_cierra(self, ms, monkeypatch):
        monkeypatch.setattr(ms, "init_guardian", lambda: None)

        class ConAenter:
            def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            async def health(self) -> dict:
                return {"status": "ok"}

        ms.PROVIDERS["extra"] = ConAenter()
        try:
            with TestClient(ms.app) as c:
                resp = c.get("/health")
                assert resp.status_code == 200
        finally:
            ms.PROVIDERS.pop("extra")


class TestChatNoStream:
    async def test_ok_devuelve_chunk(self, ms):
        resp = await ms._chat_no_stream(ms.PROVIDERS["ollama"], "m", [{"role": "user", "content": "x"}], None, 100, 0.0)
        assert resp["id"] == "resp-1"

    async def test_provider_error_raise_http(self, ms):
        from core.mochila.providers import ProviderError

        class Explosivo(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("fuego", "ollama", 500)
                yield None  # pragma: no cover

        with pytest.raises(HTTPException) as excinfo:
            await ms._chat_no_stream(Explosivo("e"), "m", [], None, 100, 0.0)
        assert excinfo.value.status_code == 500

    async def test_provider_error_sin_status(self, ms):
        from core.mochila.providers import ProviderError

        class SinStatus(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("mal", "ollama")
                yield None  # pragma: no cover

        with pytest.raises(HTTPException) as excinfo:
            await ms._chat_no_stream(SinStatus("s"), "m", [], None, 100, 0.0)
        assert excinfo.value.status_code == 502

    async def test_vacio_devuelve_none(self, ms):
        class Vacio(FakeProvider):
            async def chat(self, *a, **k):
                if False:  # pragma: no cover
                    yield None

        assert await ms._chat_no_stream(Vacio("v"), "m", [], None, 100, 0.0) is None


class TestAbortajeGuardianSSE:
    async def test_no_aborta(self, ms):
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        ab, texto, sse = await ms._abortaje_guardian_sse(G(), {"choices": [{"delta": {"content": "a"}}]}, "acum", "m")
        assert ab is False
        assert texto == "acuma"
        assert sse == b""

    async def test_aborta(self, ms, monkeypatch):
        monkeypatch.setattr("core.mochila.mochila_server.log_event", lambda *a, **k: None)

        class G:
            def evaluar_texto_stream(self, texto):
                return False

            def generar_penalizacion(self):
                return {"pen": 1}

        _ab, _texto, sse = await ms._abortaje_guardian_sse(G(), {"choices": [{"delta": {"content": "malo"}}]}, "", "m")
        assert sse
        assert b"STREAM_ABORTED_BY_GUARDIAN" in sse
        assert b"[DONE]" in sse


class TestStreamProviderDirecto:
    async def _recoger(self, ms, provider, **kwargs):
        ms.PROVIDERS["directo"] = provider
        try:
            out = b""
            async for chunk in ms._stream_from_provider("directo", "m", [], None, 100, 0.0, **kwargs):
                out += chunk
            return out
        finally:
            ms.PROVIDERS.pop("directo", None)

    async def test_chunk_none_continua(self, ms):
        class ConNone(FakeProvider):
            async def chat(self, *a, **k):
                yield None
                yield {"choices": [{"index": 0, "delta": {"content": "x"}, "finish_reason": None}]}
                yield {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}

        out = await self._recoger(ms, ConNone("c"))
        assert b"[DONE]" in out
        assert b"x" in out

    async def test_fin_normal_con_registros(self, ms):
        out = await self._recoger(ms, FakeProvider("f"))
        assert b"[DONE]" in out

    async def test_fin_sin_done_y_finally(self, ms):
        class SinFin(FakeProvider):
            async def chat(self, *a, **k):
                yield {"choices": [{"index": 0, "delta": {"content": "parcial"}, "finish_reason": None}]}

        out = await self._recoger(ms, SinFin("s"))
        assert b"data: [DONE]" in out

    async def test_guardian_aborta_stream(self, ms, monkeypatch):
        class G:
            def evaluar_texto_stream(self, texto):
                return False

            def generar_penalizacion(self):
                return {"pen": 1}

        monkeypatch.setattr("core.mochila.mochila_server.log_event", lambda *a, **k: None)
        out = await self._recoger(ms, FakeProvider("f"), is_opencode=True, guardian=G())
        assert b"STREAM_ABORTED_BY_GUARDIAN" in out
        assert b"[DONE]" in out

    async def test_guardian_no_aborta_stream(self, ms):
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        out = await self._recoger(ms, FakeProvider("f"), is_opencode=True, guardian=G())
        assert b"[DONE]" in out
        assert b"hola" in out

    async def test_timeout_error(self, ms):
        class TimeoutProvider(FakeProvider):
            async def chat(self, *a, **k):
                raise TimeoutError
                yield None  # pragma: no cover

        out = await self._recoger(ms, TimeoutProvider("t"))
        assert b"timeout_error" in out
        assert b"[DONE]" in out

    async def test_provider_error(self, ms):
        from core.mochila.providers import ProviderError

        class ErrorProvider(FakeProvider):
            async def chat(self, *a, **k):
                raise ProviderError("cae", "directo", 502)
                yield None  # pragma: no cover

        out = await self._recoger(ms, ErrorProvider("e"))
        assert b"provider_error" in out

    async def test_internal_error(self, ms):
        class Roto(FakeProvider):
            async def chat(self, *a, **k):
                raise RuntimeError("boom")
                yield None  # pragma: no cover

        out = await self._recoger(ms, Roto("r"))
        assert b"internal_error" in out


class TestProcesarUsage:
    def test_none_no_llama(self, ms):
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage(None, "ollama", "m")
        spy.assert_not_called()

    def test_con_uso(self, ms):
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage({"usage": {"prompt_tokens": 7, "completion_tokens": 3}}, "ollama", "m")
        spy.assert_called_once_with("ollama", "m", 7, 3)

    def test_uso_none_ceros(self, ms):
        spy = Mock()
        ms.cost_tracker.registrar = spy
        ms._procesar_usage({"usage": None}, "ollama", "m")
        spy.assert_called_once_with("ollama", "m", 0, 0)


class TestEvaluarGuardian:
    def test_delta_no_bloquea(self, ms):
        class G:
            def evaluar_texto_stream(self, texto):
                return True

        ab, texto, penalty = ms._evaluar_guardian(G(), {"choices": [{"delta": {"content": "ok"}}]}, "previo", "m")
        assert ab is False
        assert texto == "previook"
        assert penalty is None


class TestV1Models:
    def test_health_error_solo_auto(self, client, ms):
        class HealthErrorProvider(FakeProvider):
            async def health(self) -> dict:
                return {"status": "error"}

        ms.PROVIDERS["gemini"] = HealthErrorProvider("gemini")
        ms.CACHE_MODELS = []
        ms.CACHE_MODELS_TS = 0
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        ids = [m["id"] for m in resp.json()["data"]]
        assert "gemini/auto" in ids

    def test_health_ok_sin_modelos(self, client, ms):
        class SinModelos(FakeProvider):
            async def health(self) -> dict:
                return {"status": "ok"}

        ms.PROVIDERS["gemini"] = SinModelos("gemini")
        ms.CACHE_MODELS = []
        ms.CACHE_MODELS_TS = 0
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        ids = [m["id"] for m in resp.json()["data"]]
        assert "gemini/auto" in ids

    def test_cache_hit(self, client, ms):
        ms.CACHE_MODELS = [{"id": "ollama/auto", "provider": "ollama", "object": "model"}]
        ms.CACHE_MODELS_TS = time.time()
        resp = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
        assert resp.json()["data"][0]["id"] == "ollama/auto"


class TestResolverRuta:
    async def test_no_provider_503(self, ms, monkeypatch):
        from core.mochila.mochila_server import ChatRequest
        from core.mochila.router import NoProviderAvailable

        def explota(*a, **k):
            raise NoProviderAvailable("nada")

        monkeypatch.setattr(ms.router, "route", explota)
        with pytest.raises(HTTPException) as excinfo:
            await ms._resolver_ruta(ChatRequest(model="auto", messages=[]))
        assert excinfo.value.status_code == 503


class TestToolCalls:
    def test_tool_calls_ok(self, client, ms, monkeypatch):

        class ToolProvider(FakeProvider):
            async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
                if not any(m.get("role") == "tool" for m in mensajes):
                    yield {
                        "id": "r1",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "function": {"name": "get_time", "arguments": '{"tz": "UTC"}'},
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                    }
                else:
                    yield {
                        "id": "r2",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "final"}}],
                        "usage": {"prompt_tokens": 6, "completion_tokens": 3},
                    }

        tool_mock = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(ms, "ejecutar_tool", tool_mock)
        ms.PROVIDERS["ollama"] = ToolProvider("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "que hora es"}], "tools": True},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200
            assert resp.json()["choices"][0]["message"]["content"] == "final"
            tool_mock.assert_awaited_once_with("get_time", {"tz": "UTC"})
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")

    def test_tool_call_arguments_invalidos(self, client, ms, monkeypatch):
        class ToolProvider(FakeProvider):
            async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
                if not any(m.get("role") == "tool" for m in mensajes):
                    yield {
                        "id": "r1",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "index": 2,
                                            "function": {"name": "get_time", "arguments": "{mal"},
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": None,
                    }
                else:
                    yield {
                        "id": "r2",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "final2"}}],
                        "usage": None,
                    }

        tool_mock = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(ms, "ejecutar_tool", tool_mock)
        ms.PROVIDERS["ollama"] = ToolProvider("ollama")
        try:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "auto", "messages": [{"role": "user", "content": "x"}], "tools": True},
                headers={"Authorization": "Bearer test-key"},
            )
            assert resp.status_code == 200
            tool_mock.assert_awaited_once_with("get_time", {})
        finally:
            ms.PROVIDERS["ollama"] = FakeProvider("ollama")


class TestProxyGateway:
    def test_get_ok(self, client, ms, monkeypatch):
        async def fake_get(request, headers):
            return JSONResponse(content={"ok": True}, status_code=200)

        monkeypatch.setattr(ms, "_get_upstream", fake_get)
        resp = client.get("/api/foo", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_get_connect_error(self, client, ms, monkeypatch):
        async def fake_get(request, headers):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(ms, "_get_upstream", fake_get)
        resp = client.get("/api/foo", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 502

    def test_post_stream(self, client, ms, monkeypatch):
        async def fake_proxy_stream(request, body, headers, is_opencode, guardian, path):
            yield b'{"x": 1}\n'

        monkeypatch.setattr(ms, "_proxy_stream", fake_proxy_stream)
        resp = client.post(
            "/api/chat",
            json={"model": "llama3", "stream": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert b'"x": 1' in resp.content

    def test_post_stream_opencode_guardian(self, client, ms, monkeypatch):
        capturado: dict = {}

        async def fake_proxy_stream(request, body, headers, is_opencode, guardian, path):
            capturado["is_opencode"] = is_opencode
            capturado["guardian"] = guardian
            yield b'{"x": 2}\n'

        monkeypatch.setattr(ms, "_proxy_stream", fake_proxy_stream)
        resp = client.post(
            "/api/chat",
            json={"model": "opencode/llama3", "stream": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert capturado["is_opencode"] is True
        assert capturado["guardian"] is not None

    def test_post_no_stream(self, client, ms, monkeypatch):
        async def fake_post(request, body, headers):
            return JSONResponse(content={"ok": 2}, status_code=200)

        monkeypatch.setattr(ms, "_post_upstream", fake_post)
        resp = client.post(
            "/api/embed",
            json={"model": "m", "stream": False},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": 2}

    def test_vram_denegada(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "_adquirir_vram", AsyncMock(return_value=None))
        resp = client.post("/api/chat", json={"model": "m"}, headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 503
        assert "VRAM admission denied" in resp.json()["error"]


class TestAdquirirVram:
    async def test_con_modelo(self, ms):
        req = await ms._adquirir_vram({"model": "llama3"}, "chat")
        assert req == "req-1"
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "llama3"

    async def test_path_con_slash(self, ms):
        await ms._adquirir_vram(None, "api/chat")
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "api"

    async def test_path_sin_slash(self, ms):
        await ms._adquirir_vram(None, "single")
        ms.scheduler.acquire.assert_awaited()
        _kwargs = ms.scheduler.acquire.await_args.kwargs
        assert _kwargs["data"]["model"] == "single"


class TestAdminVRAM:
    def test_acquire_boot_grant(self, client, ms):
        ms.scheduler.acquire_boot_vram = AsyncMock(return_value=True)
        resp = client.post("/admin/acquire_boot_vram?mb=100", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "granted"}


class TestMemoriaEndpoints:
    def test_analizar(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "analizar", AsyncMock(return_value={"resultado": "analizado"}))
        resp = client.post(
            "/memoria/analizar", json={"peticion": "x"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "analizado"

    def test_sintetizar(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "sintetizar", AsyncMock(return_value={"resultado": "sintesis"}))
        resp = client.post(
            "/memoria/sintetizar", json={"peticion": "x"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_saber(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "fase_saber", AsyncMock(return_value={"resultado": "saber"}))
        resp = client.post(
            "/memoria/fase/saber", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_hacer(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "fase_hacer", AsyncMock(return_value={"resultado": "hacer"}))
        resp = client.post(
            "/memoria/fase/hacer", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_fase_comprar(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "fase_comprar", AsyncMock(return_value={"resultado": "comprar"}))
        resp = client.post(
            "/memoria/fase/comprar", json={"keywords": "k"}, headers={"Authorization": "Bearer test-key"}
        )
        assert resp.status_code == 200

    def test_vigilancia_parte(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "generar_parte", AsyncMock(return_value={"parte": "ok"}))
        resp = client.get("/memoria/vigilancia/parte", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200

    def test_consultar(self, client, ms, monkeypatch):
        spy = AsyncMock(return_value={"resultado": "q"})
        monkeypatch.setattr(ms, "memoria_consultar", spy)
        resp = client.post(
            "/memoria/consultar",
            json={"query": "pregunta", "forzar_web": True},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 200
        spy.assert_awaited_once_with("pregunta", True)

    def test_ingestar(self, client, ms, monkeypatch):
        monkeypatch.setattr(ms, "procesar_inbox_completo", AsyncMock(return_value={"ok": 1}))
        resp = client.post("/memoria/ingestar", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200

    def test_ingestar_video_404(self, client):
        resp = client.post(
            "/memoria/ingestar/video",
            json={"path": "/no/existe/ruta.mp4"},
            headers={"Authorization": "Bearer test-key"},
        )
        assert resp.status_code == 404

    def test_ingestar_video_ok(self, client):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            resp = client.post(
                "/memoria/ingestar/video",
                json={"path": f.name},
                headers={"Authorization": "Bearer test-key"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stub"

    def test_memoria_health_ok(self, client, ms, monkeypatch):
        info = MagicMock()
        info.points_count = 42
        info.config.params.vectors = MagicMock()
        fake_client = MagicMock()
        fake_client.get_collection = Mock(return_value=info)
        monkeypatch.setattr("core.memoria.qdrant_store._get_client", lambda: fake_client)
        resp = client.get("/memoria/health", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["puntos"] == 42

    def test_memoria_health_error(self, client, ms, monkeypatch):
        def explota():
            raise RuntimeError("qdrant caido")

        monkeypatch.setattr("core.memoria.qdrant_store._get_client", explota)
        resp = client.get("/memoria/health", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"


class TestStatusEndpoint:
    def test_status_ok(self, client):
        resp = client.get("/status", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert "mochila" in resp.json()


class TestMotorV2:
    def test_branch_motor_v2(self, monkeypatch):
        import importlib.util

        ruta = Path(__file__).resolve().parents[2] / "core/mochila/mochila_server.py"
        spec = importlib.util.spec_from_file_location("mochila_server_v2_test", str(ruta))
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["mochila_server_v2_test"] = mod
        monkeypatch.setenv("URA_MOCHILA_MOTOR_V2", "1")
        spec.loader.exec_module(mod)
        assert mod._USAR_MOTOR_V2 is True
        assert sorted(mod.PROVIDERS) == ["gemini", "ollama", "openrouter"]
