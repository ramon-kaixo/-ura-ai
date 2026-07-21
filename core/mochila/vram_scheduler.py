import asyncio
import logging
import os
import subprocess
import time
import uuid
from typing import Any

import httpx

_OH = os.environ.get("URA_OLLAMA_HOST", "127.0.0.1")
_OP = os.environ.get("URA_OLLAMA_PORT", "11434")
OLLAMA_SOCKET = f"http://{_OH}:{_OP}"

log = logging.getLogger(__name__)


class VRAMAwareScheduler:
    def __init__(self, default_max_mb: int = 100000, queue_timeout: float = 60.0) -> None:
        self.max_mb = self._detect_max_vram(default_max_mb)
        self.queue_timeout = queue_timeout
        self._queue: list[tuple[asyncio.Future, int, float, dict[str, Any]]] = []
        self._active: dict[str, dict[str, Any]] = {}
        self._current_mb = 0
        self._hot_models: set = set()
        self._consecutive_smi_errors = 0
        self._lock = asyncio.Lock()
        self._ollama_client = httpx.AsyncClient(base_url=OLLAMA_SOCKET)
        self._scheduler_log = logging.getLogger("mochila.vram")
        self._task: asyncio.Task | None = None

    @staticmethod
    def _detect_max_vram(default_mb: int) -> int:
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip() and "N/A" not in res.stdout:
                return int(res.stdout.strip())
        except Exception as e:
            log.warning("mochila: detect_max_vram falló: %s", e)
        return default_mb

    def available_mb(self) -> int:
        return self.max_mb - self._current_mb

    @staticmethod
    def estimar_vram(body: dict) -> int:
        if "_vram_mb" in body:
            return int(body["_vram_mb"])
        model = body.get("model", "")
        base_weights = {
            "qwen2.5-coder:32b": 18000,
            "qwen2.5-coder:14b": 9000,
            "qwen2-vl-7b": 6000,
            "llama3.2:3b": 2500,
        }
        base = base_weights.get(model, 512)
        prompt = body.get("prompt", "") or str(body.get("messages", ""))
        kv_cache_overhead = int((len(prompt) // 4) * 0.002)
        return base + kv_cache_overhead

    async def sync_vram(self) -> None:
        proc = None
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "nvidia-smi",
                    "--query-compute-apps=used_memory",
                    "--format=csv,noheader",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                ),
                timeout=0.2,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                total = 0
                for line in stdout.decode().strip().split("\n"):
                    if line.strip():
                        total += int(line.strip().split()[0])
                self._current_mb = total
                self._consecutive_smi_errors = 0
        except TimeoutError:
            self._consecutive_smi_errors += 1
            self._scheduler_log.warning("nvidia-smi timeout (%d/3)", self._consecutive_smi_errors)
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception as e:
                    log.debug("mochila: kill proc falló: %s", e)
        except Exception as e:
            self._consecutive_smi_errors += 1
            self._scheduler_log.warning("nvidia-smi error (%d/3): %s", self._consecutive_smi_errors, e)
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception as e2:
                    log.debug("mochila: kill proc falló: %s", e2)
        if self._consecutive_smi_errors >= 3:
            self._scheduler_log.critical("nvidia-smi caido persistentemente. Bloqueando VRAM.")
            self._current_mb = self.max_mb
        try:
            resp = await self._ollama_client.get("/api/ps")
            if resp.status_code == 200:
                data = resp.json()
                self._hot_models = {m["name"] for m in data.get("models", [])}
        except Exception as e:
            log.warning("mochila: ollama ps falló: %s", e)

    async def acquire(self, mb: int, deadline_flex: float = 10.0, data: dict | None = None) -> str | None:
        async with self._lock:
            if len(self._active) > 0:
                return None
            if self.available_mb() < mb:
                future = asyncio.get_running_loop().create_future()
                deadline = time.time() + max(deadline_flex, 5.0)
                self._queue.append((future, mb, deadline, data or {}))
            else:
                req_id = str(uuid.uuid4())
                self._active[req_id] = {"mb": mb, "ts": time.time(), "model": (data or {}).get("model", "")}
                return req_id
        try:
            return await asyncio.wait_for(future, timeout=deadline_flex + 1.0)
        except TimeoutError:
            return None

    async def acquire_boot_vram(self, mb: int) -> bool:
        async with self._lock:
            future = asyncio.get_running_loop().create_future()
            self._queue.append((future, mb, time.time() + 120.0, {"model": "static_boot_service"}))
        try:
            req_id = await asyncio.wait_for(future, timeout=90.0)
        except TimeoutError:
            return False

        async def _release() -> None:
            try:
                await asyncio.sleep(3.0)
            finally:
                async with self._lock:
                    self._active.pop(req_id, None)

        asyncio.create_task(_release())  # noqa: RUF006
        return True

    async def release(self, req_id: str) -> None:
        async with self._lock:
            self._active.pop(req_id, None)

    async def start_loop(self) -> None:
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop_loop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _scheduler_loop(self) -> None:
        while True:
            try:
                await self.sync_vram()
                async with self._lock:
                    now = time.time()
                    self._queue = [(f, mb, dl, d) for f, mb, dl, d in self._queue if dl > now]
                    if len(self._active) == 0 and self._queue:
                        fut, mb, _deadline, data = self._queue[0]
                        if not fut.done() and mb <= self.available_mb():
                            self._queue.pop(0)
                            req_id = str(uuid.uuid4())
                            self._active[req_id] = {"mb": mb, "ts": now, "model": data.get("model", "")}
                            fut.set_result(req_id)
            except Exception as e:
                self._scheduler_log.error("scheduler_loop error: %s", e)
            await asyncio.sleep(0.5)
