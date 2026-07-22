"""RAG — Retrieval Augmented Generation con el Knowledge Engine."""

from __future__ import annotations

from pathlib import Path


class RAGContext:
    def __init__(self) -> None:
        self._available = False
        self._check_available()

    @staticmethod
    def _get_ke_db_path() -> Path | None:
        db = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"
        if db.exists():
            return db
        return None

    def _check_available(self) -> None:
        try:
            from knowledge.engine.memory_store import SQLiteMemoryStore

            db_path = self._get_ke_db_path()
            if db_path is None:
                return
            self._store = SQLiteMemoryStore(db_path)
            self._available = True
        except Exception:
            self._available = False

    def is_available(self) -> bool:
        return self._available

    async def retrieve(self, query: str, max_results: int = 3) -> str:
        if not self._available or not query:
            return ""
        try:
            return self.retrieve_sync(query, max_results)
        except Exception:
            return ""

    def retrieve_sync(self, query: str, max_results: int = 3) -> str:
        if not self._available or not query:
            return ""
        try:
            results = self._store.search(query, kind="knowledge", limit=max_results)
            if not results:
                return ""
            parts: list[str] = []
            for r in results:
                content = getattr(r, "content", "") or getattr(r, "text", "") or str(r)
                parts.append(content[:300])
            return "\n---\n".join(parts)
        except Exception:
            return ""
