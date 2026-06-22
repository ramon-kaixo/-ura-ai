import asyncio
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

log = logging.getLogger("ura.scraper_pool")

_MAX_QUEUE_SIZE = 1000


class DomainDecoupledPool:
    def __init__(self, delay: float = 1.0):
        self.queues: dict[str, asyncio.Queue] = {}
        self.delay = delay
        self._workers: set[asyncio.Task] = set()
        self._scrape_fn: Callable[[str], Awaitable[None]] | None = None
        self._init_lock = asyncio.Lock()

    async def run(
        self,
        urls: list[str],
        scrape_fn: Callable[[str], Awaitable[None]],
        wait: bool = False,
    ) -> None:
        self._scrape_fn = scrape_fn
        for url in urls:
            domain = urlparse(url).netloc
            if domain not in self.queues:
                async with self._init_lock:
                    if domain not in self.queues:
                        self.queues[domain] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
                        self._workers.add(asyncio.create_task(self._worker(domain)))
            await self.queues[domain].put(url)
        if wait:
            await self.join()

    async def join(self) -> None:
        """Wait for all queues to drain, then cancel workers."""
        await asyncio.gather(*(q.join() for q in self.queues.values()))
        for task in list(self._workers):
            if task is not asyncio.current_task():
                task.cancel()
        self._workers.clear()
        self.queues.clear()

    async def _worker(self, domain: str) -> None:
        queue = self.queues[domain]
        in_flight = False
        try:
            while True:
                url = await queue.get()
                in_flight = True
                try:
                    if self._scrape_fn:
                        await self._scrape_fn(url)
                except Exception as e:
                    log.warning("Error scraping %s: %s", url, e)
                finally:
                    in_flight = False
                    queue.task_done()
                    await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            if in_flight:
                log.warning("Worker cancelled mid-processing for domain %s", domain)
