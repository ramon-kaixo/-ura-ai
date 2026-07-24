"""Tests for SemanticMemory (scripts/pro/tuneladora/memory/semantic.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pro.tuneladora.memory.semantic import Concept, Relation, SemanticMemory


@pytest.fixture
def sem_mem(tmp_path: Path) -> SemanticMemory:
    return SemanticMemory(tmp_path / "test_semantic.db")


class TestConcept:
    def test_learn_and_get(self, sem_mem: SemanticMemory) -> None:
        c = Concept(name="ruff", context="linting tool", weight=1.0, tags=("lint",))
        sem_mem.learn_concept(c)
        results = sem_mem.get_concept("ruff")
        assert len(results) == 1
        assert results[0].weight == 1.0
        assert "lint" in results[0].tags

    def test_learn_accumulates_weight(self, sem_mem: SemanticMemory) -> None:
        c1 = Concept(name="bolt", context="database", weight=1.0)
        c2 = Concept(name="bolt", context="database", weight=2.0)
        sem_mem.learn_concept(c1)
        sem_mem.learn_concept(c2)
        results = sem_mem.get_concept("bolt")
        assert results[0].weight == 3.0
        assert results[0].occurrences == 2

    def test_get_missing(self, sem_mem: SemanticMemory) -> None:
        assert sem_mem.get_concept("nonexistent") == []


class TestRelation:
    def test_learn_and_get_related(self, sem_mem: SemanticMemory) -> None:
        r = Relation(source="ruff", target="linting", relation_type="tool_for")
        sem_mem.learn_relation(r)
        related = sem_mem.get_related("ruff")
        assert len(related) == 1
        assert related[0].target == "linting"

    def test_get_related_by_type(self, sem_mem: SemanticMemory) -> None:
        sem_mem.learn_relation(Relation(source="a", target="b", relation_type="depends"))
        sem_mem.learn_relation(Relation(source="a", target="c", relation_type="extends"))
        related = sem_mem.get_related("a", relation_type="depends")
        assert len(related) == 1
        assert related[0].target == "b"

    def test_relation_inverse(self, sem_mem: SemanticMemory) -> None:
        sem_mem.learn_relation(Relation(source="x", target="y", relation_type="connects"))
        from_y = sem_mem.get_related("y")
        assert len(from_y) == 1

    def test_update_relation(self, sem_mem: SemanticMemory) -> None:
        r1 = Relation(source="a", target="b", relation_type="link", weight=1.0)
        r2 = Relation(source="a", target="b", relation_type="link", weight=5.0)
        sem_mem.learn_relation(r1)
        sem_mem.learn_relation(r2)
        related = sem_mem.get_related("a")
        assert related[0].weight == 5.0


class TestSearch:
    def test_search_concepts(self, sem_mem: SemanticMemory) -> None:
        sem_mem.learn_concept(Concept(name="python", context="language"))
        sem_mem.learn_concept(Concept(name="pyramid", context="structure"))
        results = sem_mem.search_concepts("python")
        assert len(results) >= 1
        assert any(c.name == "python" for c in results)

    def test_search_by_context(self, sem_mem: SemanticMemory) -> None:
        sem_mem.learn_concept(Concept(name="x", context="database engine"))
        results = sem_mem.search_concepts("database")
        assert len(results) >= 1

    def test_search_limit(self, sem_mem: SemanticMemory) -> None:
        for i in range(10):
            sem_mem.learn_concept(Concept(name=f"concept{i}", context="test"))
        assert len(sem_mem.search_concepts("concept", limit=3)) == 3
