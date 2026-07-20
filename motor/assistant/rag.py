"""RAG — Retrieval Augmented Generation con el Knowledge Engine."""

from __future__ import annotations


class RAGContext:
    def __init__(self) -> None:
        self._available = False
        self._check_available()

    def _check_available(self) -> None:
        try:
            from knowledge.engine.memory_store import MemoryStore

            self._store = MemoryStore()
            self._available = True
        except Exception:
            self._available = False

    def is_available(self) -> bool:
        return self._available

    async def retrieve(self, query: str, max_results: int = 3) -> str:
        if not self._available or not query:
            return ""

        try:
            from knowledge.engine.memory_store import MemoryStore

            store = MemoryStore()
            results = store.search(query, kind="knowledge", limit=max_results)
            if not results:
                return ""

            parts: list[str] = []
            for r in results:
                content = getattr(r, "content", "") or getattr(r, "text", "") or str(r)
                parts.append(content[:300])
            return "\n---\n".join(parts)
        except Exception:
            return ""
