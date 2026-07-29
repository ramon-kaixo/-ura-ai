from __future__ import annotations

import pytest

from motor.intelligence.memory.episodic import Episode
from motor.intelligence.memory.extractor import FactExtractor, RuleBasedFactExtractor
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore, consolidate_episodes

# ── Test FactExtractor ────────────────────────────────────────────────────


class TestFactExtractorInterface:
    def test_interface_cannot_instantiate(self):
        with pytest.raises(TypeError):
            FactExtractor()


class TestRuleBasedFactExtractor:
    def test_empty_payload(self):
        extractor = RuleBasedFactExtractor()
        facts = extractor.extract(Episode(payload=""))
        assert facts == []

    def test_attribute_pattern(self):
        extractor = RuleBasedFactExtractor()
        ep = Episode(payload="La temperatura es 42 grados")
        facts = extractor.extract(ep)
        assert len(facts) >= 1
        assert facts[0].predicate == "temperatura"
        assert "42" in facts[0].object_value

    def test_relation_pattern(self):
        extractor = RuleBasedFactExtractor()
        ep = Episode(payload="El servidor contiene 64GB de RAM")
        facts = extractor.extract(ep)
        assert any("servidor" in f.subject and "64GB" in f.object_value for f in facts)

    def test_error_pattern(self):
        extractor = RuleBasedFactExtractor()
        ep = Episode(payload="Error: conexion rechazada")
        facts = extractor.extract(ep)
        assert any(f.predicate == "error" for f in facts)

    def test_importance_and_confidence_from_episode(self):
        extractor = RuleBasedFactExtractor()
        ep = Episode(payload="El sistema es muy rapido", importance=0.9, confidence=0.8)
        facts = extractor.extract(ep)
        assert all(f.importance == 0.9 for f in facts)
        assert all(f.confidence == 0.8 * 0.9 for f in facts)

    def test_source_episode_id(self):
        extractor = RuleBasedFactExtractor()
        ep = Episode(id="ep001", payload="El modulo usa Python")
        facts = extractor.extract(ep)
        assert all("ep001" in f.source_episode_ids for f in facts)


# ── Test SemanticFact ──────────────────────────────────────────────────────


class TestSemanticFact:
    def test_auto_id(self):
        f = SemanticFact(subject="s", predicate="p", object_value="o")
        assert f.id != ""

    def test_auto_timestamps(self):
        f = SemanticFact(subject="s", predicate="p", object_value="o")
        assert f.created_at != ""
        assert f.updated_at != ""

    def test_key(self):
        f = SemanticFact(subject="sistema", predicate="tiene", object_value="memoria")
        assert f.key == "sistema|tiene|memoria"

    def test_merge_increases_version(self):
        f1 = SemanticFact(subject="s", predicate="p", object_value="o", source_episode_ids=["e1"])
        f2 = SemanticFact(subject="s", predicate="p", object_value="o", source_episode_ids=["e2"], confidence=0.9)
        f1.merge(f2)
        assert f1.version == 2
        assert f1.confidence == 0.9
        assert "e2" in f1.source_episode_ids

    def test_merge_preserves_highest(self):
        f1 = SemanticFact(subject="s", predicate="p", object_value="o", importance=0.8, confidence=0.6)
        f2 = SemanticFact(subject="s", predicate="p", object_value="o", importance=0.5, confidence=0.9)
        f1.merge(f2)
        assert f1.importance == 0.8
        assert f1.confidence == 0.9

    def test_merge_tags(self):
        f1 = SemanticFact(subject="s", predicate="p", object_value="o", tags=["a"])
        f2 = SemanticFact(subject="s", predicate="p", object_value="o", tags=["b"])
        f1.merge(f2)
        assert "a" in f1.tags
        assert "b" in f1.tags

    def test_to_dict(self):
        f = SemanticFact(subject="s", predicate="p", object_value="o", importance=0.9, source_episode_ids=["e1"])
        d = f.to_dict()
        assert d["subject"] == "s"
        assert d["importance"] == 0.9
        assert d["source_episodes"] == 1


# ── Test SemanticMemoryStore ──────────────────────────────────────────────


class TestSemanticMemoryStore:
    def test_store_and_get(self):
        store = SemanticMemoryStore()
        f = SemanticFact(subject="s", predicate="p", object_value="o")
        fid = store.store(f)
        assert store.get(fid) is not None

    def test_dedup_by_key(self):
        store = SemanticMemoryStore()
        f1 = SemanticFact(subject="s", predicate="p", object_value="o", tags=["a"])
        f2 = SemanticFact(subject="s", predicate="p", object_value="o", tags=["b"])
        store.store(f1)
        store.store(f2)
        assert store.count() == 1  # deduplicated
        merged = store.get_by_key("s", "p", "o")
        assert merged is not None
        assert "a" in merged.tags
        assert "b" in merged.tags

    def test_search_by_text(self):
        store = SemanticMemoryStore()
        store.store(SemanticFact(subject="sistema", predicate="tiene", object_value="memoria"))
        store.store(SemanticFact(subject="usuario", predicate="pregunta", object_value="ayuda"))
        results = store.search(text="memoria")
        assert len(results) == 1

    def test_search_by_tags(self):
        store = SemanticMemoryStore()
        store.store(SemanticFact(subject="a", predicate="es", object_value="1", tags=["urgente"]))
        store.store(SemanticFact(subject="b", predicate="es", object_value="2", tags=["normal"]))
        results = store.search(tags=["urgente"])
        assert len(results) == 1

    def test_search_by_type(self):
        store = SemanticMemoryStore()
        store.store(SemanticFact(subject="a", predicate="es", object_value="1", fact_type="attribute"))
        store.store(SemanticFact(subject="b", predicate="error", object_value="fallo", fact_type="error"))
        results = store.search(fact_type="error")
        assert len(results) == 1

    def test_search_by_entity(self):
        store = SemanticMemoryStore()
        store.store(SemanticFact(subject="sistema", predicate="tiene", object_value="RAM"))
        store.store(SemanticFact(subject="usuario", predicate="dice", object_value="hola"))
        results = store.search(entity="sistema")
        assert len(results) == 1

    def test_get_nonexistent(self):
        store = SemanticMemoryStore()
        assert store.get("nope") is None

    def test_get_by_key_nonexistent(self):
        store = SemanticMemoryStore()
        assert store.get_by_key("x", "y", "z") is None

    def test_delete(self):
        store = SemanticMemoryStore()
        fid = store.store(SemanticFact(subject="s", predicate="p", object_value="o"))
        assert store.delete(fid) is True
        assert store.get(fid) is None

    def test_delete_nonexistent(self):
        store = SemanticMemoryStore()
        assert store.delete("nope") is False

    def test_count(self):
        store = SemanticMemoryStore()
        assert store.count() == 0
        store.store(SemanticFact(subject="a", predicate="b", object_value="c"))
        assert store.count() == 1

    def test_clear_all(self):
        store = SemanticMemoryStore()
        store.store(SemanticFact(subject="a", predicate="b", object_value="c"))
        assert store.clear_all() == 1
        assert store.count() == 0

    def test_search_limit(self):
        store = SemanticMemoryStore()
        for i in range(20):
            store.store(SemanticFact(subject="s", predicate="p", object_value=f"v{i}"))
        results = store.search(text="v", k=5)
        assert len(results) == 5

    def test_search_empty(self):
        store = SemanticMemoryStore()
        assert store.search(text="nothing") == []


# ── Test Consolidation ────────────────────────────────────────────────────


class TestConsolidation:
    def test_consolidate_episodes(self):
        store = SemanticMemoryStore()
        extractor = RuleBasedFactExtractor()
        episodes = [
            Episode(payload="El sistema es muy rapido"),
            Episode(payload="Error: timeout en conexion"),
        ]
        count = consolidate_episodes(episodes, store, extractor)
        assert count >= 2
        assert store.count() >= 1

    def test_consolidate_dedup(self):
        store = SemanticMemoryStore()
        extractor = RuleBasedFactExtractor()
        episodes = [
            Episode(payload="La temperatura es 42 grados"),
            Episode(payload="La temperatura es 42 grados"),
        ]
        count = consolidate_episodes(episodes, store, extractor)
        assert store.count() < count  # deduplicated

    def test_consolidate_empty_episodes(self):
        store = SemanticMemoryStore()
        extractor = RuleBasedFactExtractor()
        count = consolidate_episodes([], store, extractor)
        assert count == 0


# ── Test Persistence ──────────────────────────────────────────────────────


class TestPersistence:
    def test_sqlite_roundtrip(self, tmp_path):
        db_path = str(tmp_path / "semantic.db")
        store = SemanticMemoryStore(persist_path=db_path)
        store.store(SemanticFact(subject="sistema", predicate="tiene", object_value="memoria"))
        assert store.count() == 1
        store2 = SemanticMemoryStore(persist_path=db_path)
        assert store2.count() == 1
        assert store2.get_by_key("sistema", "tiene", "memoria") is not None


# ── Test Thread Safety ────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_store(self):
        import concurrent.futures

        store = SemanticMemoryStore()
        n = 100
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [
                exe.submit(store.store, SemanticFact(subject=f"s{i}", predicate="p", object_value="o"))
                for i in range(n)
            ]
            concurrent.futures.wait(futures)
        assert store.count() == n  # all unique subjects

    def test_concurrent_search(self):
        import concurrent.futures

        store = SemanticMemoryStore()
        for i in range(50):
            store.store(SemanticFact(subject=f"s{i}", predicate="p", object_value="o"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(store.search, text="s") for _ in range(20)]
            concurrent.futures.wait(futures)
        for f in futures:
            assert len(f.result()) <= 50
