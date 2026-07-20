"""MemoryOrchestrator — consolidación, compresión y olvido automáticos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from motor.intelligence.memory.semantic import SemanticMemoryStore, consolidate_episodes

if TYPE_CHECKING:
    from motor.intelligence.memory.episodic import EpisodeStore

log = logging.getLogger("ura.memory.orchestrator")


class MemoryOrchestrator:
    def __init__(
        self,
        episode_store: EpisodeStore,
        semantic_store: SemanticMemoryStore,
        extractor: Any = None,
        compressor: Any = None,
        forgetting_engine: Any = None,
    ) -> None:
        self._episode_store = episode_store
        self._semantic_store = semantic_store
        self._extractor = extractor
        self._compressor = compressor
        self._forgetting = forgetting_engine
        self._running = False

    def consolidate(self, batch_size: int = 100) -> int:
        if self._extractor is None:
            log.warning("No extractor configured — skipping consolidation")
            return 0
        episodes = self._episode_store.get_recent(k=batch_size)
        if not episodes:
            return 0
        count = consolidate_episodes(episodes, self._semantic_store, self._extractor)
        if count:
            log.info("Consolidated %d facts from %d episodes", count, len(episodes))
        return count

    def compress(self) -> int:
        if self._compressor is None:
            return 0
        result = self._compressor.compress()
        if result.summaries_created:
            log.info("Compressed %d episodes into %d summaries", result.episodes_compressed, result.summaries_created)
        return result.summaries_created

    def forget(self, dry_run: bool = False) -> dict[str, Any]:
        if self._forgetting is None:
            return {"removed": 0, "dry_run": dry_run}
        result = self._forgetting.run(dry_run=dry_run)
        if result.total_removed:
            log.info("Forgetting: removed %d records (dry=%s)", result.total_removed, dry_run)
        return {"removed": result.total_removed, "dry_run": dry_run}

    def run_all(self, dry_run: bool = False) -> dict[str, Any]:
        results: dict[str, Any] = {"consolidated": 0, "compressed": 0, "forgotten": 0}
        results["consolidated"] = self.consolidate()
        results["compressed"] = self.compress()
        results["forgotten"] = self.forget(dry_run=dry_run)["removed"]
        return results
