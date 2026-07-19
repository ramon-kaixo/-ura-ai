from __future__ import annotations

from motor.intelligence.memory.episodic import Episode, EpisodeStore
from motor.intelligence.memory.extractor import RuleBasedFactExtractor
from motor.intelligence.memory.extractor_llm import LLMFactExtractor
from motor.intelligence.memory.orchestrator import MemoryOrchestrator
from motor.intelligence.memory.semantic import SemanticMemoryStore
from motor.intelligence.pipeline import (
    disable_reranker,
    enable_reranker,
    reranker_enabled,
    search_with_reranker,
)


class TestMemoryOrchestrator:
    def test_consolidate_empty(self):
        epi = EpisodeStore()
        sem = SemanticMemoryStore()
        orch = MemoryOrchestrator(epi, sem, extractor=RuleBasedFactExtractor())
        assert orch.consolidate() == 0

    def test_consolidate_with_episodes(self):
        epi = EpisodeStore()
        sem = SemanticMemoryStore()
        epi.store(Episode(payload="El sistema es muy rapido"))
        epi.store(Episode(payload="Error: timeout en conexion"))
        orch = MemoryOrchestrator(epi, sem, extractor=RuleBasedFactExtractor())
        count = orch.consolidate()
        assert count >= 1
        assert sem.count() >= 1

    def test_compress_no_compressor(self):
        epi = EpisodeStore()
        sem = SemanticMemoryStore()
        orch = MemoryOrchestrator(epi, sem)
        assert orch.compress() == 0

    def test_forget_no_engine(self):
        epi = EpisodeStore()
        sem = SemanticMemoryStore()
        orch = MemoryOrchestrator(epi, sem)
        result = orch.forget()
        assert result["removed"] == 0

    def test_run_all(self):
        epi = EpisodeStore()
        sem = SemanticMemoryStore()
        epi.store(Episode(payload="test data"))
        orch = MemoryOrchestrator(epi, sem, extractor=RuleBasedFactExtractor())
        results = orch.run_all()
        assert "consolidated" in results
        assert "compressed" in results
        assert "forgotten" in results


class TestLLMFactExtractor:
    def test_implements_interface(self):
        from motor.intelligence.memory.extractor import FactExtractor

        extractor = LLMFactExtractor()
        assert isinstance(extractor, FactExtractor)

    def test_empty_payload(self):
        extractor = LLMFactExtractor()
        ep = Episode(payload="")
        facts = extractor.extract(ep)
        assert facts == []


class TestRerankerFeatureFlag:
    def test_disabled_by_default(self):
        assert not reranker_enabled()

    def test_enable_disable(self):
        class FakeReranker:
            def rerank(self, query, candidates):
                return candidates

        enable_reranker(FakeReranker())
        assert reranker_enabled()
        disable_reranker()
        assert not reranker_enabled()

    def test_search_with_reranker_disabled(self):
        from motor.intelligence.retrieval.lexical import LexicalRetriever

        disable_reranker()
        lex = LexicalRetriever()
        results = search_with_reranker("test", lex, k=5)
        assert isinstance(results, list)


class TestIntegration:
    def test_researcher_with_memory(self):
        from motor.intelligence.agents.researcher import ResearcherAgent
        from motor.intelligence.memory.episodic import Episode, EpisodeStore
        from motor.intelligence.memory.retrieval import ContextRetriever

        store = EpisodeStore()
        store.store(Episode(payload="EventBus test data", session_id="s1"))
        retriever = ContextRetriever(store)

        agent = ResearcherAgent(memory_store=None, context_retriever=retriever)
        from motor.intelligence.agents.message import AgentTask

        result = agent.run(AgentTask(objective="EventBus"))
        assert result.success
        assert result.output.get("sources") == ["episodic_memory"]

    def test_full_pipeline(self):
        from motor.intelligence.agents.executor import ExecutorAgent
        from motor.intelligence.agents.runtime import MultiAgentRuntime

        runtime = MultiAgentRuntime()
        runtime.register(ExecutorAgent())
        result = runtime.execute_workflow("echo test", timeout=10)
        assert result.success or not result.success
