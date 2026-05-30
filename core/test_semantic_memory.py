"""Tests for core/semantic_memory.py — semantic memory system."""

import logging


logging.disable(logging.CRITICAL)


class TestSemanticMemoryManager:
    """semantic_memory_manager — create and manage memories."""

    def test_imports_without_error(self):
        from core.semantic_memory import SemanticMemory, SemanticMemoryManager

        assert SemanticMemory is not None
        assert SemanticMemoryManager is not None

    def test_create_memory_returns_instance(self):
        from core.semantic_memory import SemanticMemoryManager

        smm = SemanticMemoryManager()
        memory = smm.create_memory("test_memory", dimension=64)
        assert memory is not None

    def test_add_memory_accepts_text(self):
        from core.semantic_memory import SemanticMemoryManager

        smm = SemanticMemoryManager()
        memory = smm.create_memory("test", dimension=64)
        memory.add_memory("test fact", {"type": "test"}, importance=0.8)

    def test_recall_returns_list(self):
        from core.semantic_memory import SemanticMemoryManager

        smm = SemanticMemoryManager()
        memory = smm.create_memory("test", dimension=64)
        results = memory.recall("test", top_k=5)
        assert isinstance(results, list)

    def test_empty_memory_recall_returns_empty(self):
        from core.semantic_memory import SemanticMemoryManager

        smm = SemanticMemoryManager()
        memory = smm.create_memory("empty", dimension=64)
        results = memory.recall("nothing")
        assert results == []

    def test_add_multiple_memories(self):
        from core.semantic_memory import SemanticMemoryManager

        smm = SemanticMemoryManager()
        memory = smm.create_memory("multi", dimension=64)
        for i in range(5):
            memory.add_memory(f"fact {i}", {"type": "test"}, importance=0.5)
        results = memory.recall("fact", top_k=3)
        assert len(results) <= 3
