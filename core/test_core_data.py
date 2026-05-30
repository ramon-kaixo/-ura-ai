"""Tests for core: vector_database, semantic_search, memory_persistence, scheduler_buscadores, repetition_detector, config_assistant, email_reader."""

import logging


logging.disable(logging.CRITICAL)


class TestVectorDatabase:
    def test_imports(self):
        from core.vector_database import VectorDatabase

        assert VectorDatabase is not None

    def test_instantiates(self):
        from core.vector_database import VectorDatabase

        db = VectorDatabase()
        assert hasattr(db, "collections")


class TestSemanticSearch:
    def test_imports(self):
        from core.semantic_search import get_semantic_search_engine

        assert get_semantic_search_engine is not None


class TestMemoryPersistence:
    def test_imports(self):
        from core.memory_persistence import MemoryPersistence

        assert MemoryPersistence is not None


class TestConfigAssistant:
    def test_imports(self):
        from core.config_assistant import ConfigAssistant

        assert ConfigAssistant is not None


class TestEmailReader:
    def test_imports(self):
        from core.email_reader import EmailReader

        assert EmailReader is not None
