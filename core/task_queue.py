import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None
        self.running = False

    async def start_worker(self, handler: Any) -> None:
        self.running = True
        self.worker_task = asyncio.create_task(self._worker(handler))

    async def stop_worker(self) -> None:
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    async def add_task(self, task: dict[str, Any]) -> None:
        await self.queue.put(task)
        logger.info("Tarea anadida: %s", task.get("name", "sin_nombre"))

    async def _worker(self, handler: Any) -> None:
        while self.running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                logger.info("Ejecutando tarea: %s", task.get("name", "sin_nombre"))
                result = await handler(task)
                logger.info("Resultado: %s", result)
            except Exception as exc:
                logger.error("Tarea fallo: %s", exc)
            finally:
                self.queue.task_done()

    async def join(self) -> None:
        await self.queue.join()
