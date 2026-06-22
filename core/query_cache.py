import asyncio
import hashlib
import json
import time
from collections import OrderedDict


class AsyncQueryCache:
    def __init__(self, max_size: int = 128, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
        self.lock = asyncio.Lock()

    def compute_key(
        self,
        query_text: str,
        use_reranker: bool = False,
        use_hybrid: bool = False,
        top_k: int = 5,
    ) -> str:
        payload = {
            "q": query_text.strip().lower(),
            "r": use_reranker,
            "h": use_hybrid,
            "k": top_k,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def get(self, key: str) -> list[dict] | None:
        async with self.lock:
            if key in self.cache:
                ts, results = self.cache[key]
                if time.monotonic() - ts < self.ttl:
                    self.cache.move_to_end(key)
                    return results
                del self.cache[key]
            return None

    async def set(self, key: str, results: list[dict]) -> None:
        async with self.lock:
            self.cache[key] = (time.monotonic(), results)
            self.cache.move_to_end(key)
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    async def clear(self) -> None:
        async with self.lock:
            self.cache.clear()
