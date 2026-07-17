"""Tests para F25-B4: FactIndex (R06).

Cubre:
- API: add_fact, remove_fact, lookup, lookup_entity, lookup_predicate,
  lookup_subject_predicate, lookup_evidence
- Edge cases: duplicados, frozen, evidencia vacía, fact vacío
- Construcción por lotes: build(), copy(), freeze()
- Concurrencia: contrato frozen + copy-on-write
- Benchmarks: 10³, 10⁴, 10⁵ facts (build, lookup, memoria)
"""

from __future__ import annotations

import time
import sys

import pytest

from motor.core.fusion.fact_index import FactIndex
from motor.core.fusion.models import KnowledgeFact, make_fact_id


# ── helpers ─────────────────────────────────────────────


def _make_fact(
    fact_id: str,
    subject: str = "Subject",
    predicate: str = "predicate",
    obj: str = "object",
    confidence: float = 0.9,
    evidence_ids: tuple[str, ...] = ("ev1",),
) -> KnowledgeFact:
    return KnowledgeFact(
        id=fact_id,
        subject=subject,
        predicate=predicate,
        object=obj,
        confidence=confidence,
        evidence_ids=evidence_ids,
    )


# ── B4.1: add_fact ──────────────────────────────────────


def test_add_fact() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple")
    idx.add_fact(f)
    assert idx.size == 1


def test_add_fact_duplicate_raises() -> None:
    idx = FactIndex()
    f = _make_fact("f1")
    idx.add_fact(f)
    with pytest.raises(KeyError, match="already indexed"):
        idx.add_fact(f)


def test_add_fact_empty_id_raises() -> None:
    idx = FactIndex()
    f = _make_fact("")
    with pytest.raises(ValueError, match="non-empty id"):
        idx.add_fact(f)


def test_add_fact_frozen_raises() -> None:
    idx = FactIndex()
    idx.freeze()
    f = _make_fact("f1")
    with pytest.raises(RuntimeError, match="Cannot modify frozen"):
        idx.add_fact(f)


# ── B4.2: lookup ────────────────────────────────────────


def test_lookup_found() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple")
    idx.add_fact(f)
    assert idx.lookup("f1") is f


def test_lookup_not_found() -> None:
    idx = FactIndex()
    assert idx.lookup("nonexistent") is None


def test_lookup_empty_string() -> None:
    idx = FactIndex()
    assert idx.lookup("") is None


# ── B4.3: lookup_entity ─────────────────────────────────


def test_lookup_entity_found() -> None:
    idx = FactIndex()
    f1 = _make_fact("f1", subject="Apple")
    f2 = _make_fact("f2", subject="Apple")
    idx.add_fact(f1)
    idx.add_fact(f2)
    results = idx.lookup_entity("apple")
    assert len(results) == 2
    assert f1 in results
    assert f2 in results


def test_lookup_entity_case_insensitive() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple")
    idx.add_fact(f)
    assert len(idx.lookup_entity("APPLE")) == 1
    assert len(idx.lookup_entity("apple")) == 1


def test_lookup_entity_not_found() -> None:
    idx = FactIndex()
    assert idx.lookup_entity("nonexistent") == []


# ── B4.4: lookup_predicate ──────────────────────────────


def test_lookup_predicate_found() -> None:
    idx = FactIndex()
    f1 = _make_fact("f1", predicate="sells")
    f2 = _make_fact("f2", predicate="sells")
    idx.add_fact(f1)
    idx.add_fact(f2)
    assert len(idx.lookup_predicate("sells")) == 2


# ── B4.5: lookup_subject_predicate ──────────────────────


def test_lookup_subject_predicate_found() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple", predicate="sells")
    idx.add_fact(f)
    results = idx.lookup_subject_predicate("Apple", "sells")
    assert len(results) == 1
    assert results[0] is f


def test_lookup_subject_predicate_no_match() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple", predicate="sells")
    idx.add_fact(f)
    assert idx.lookup_subject_predicate("Apple", "buys") == []


# ── B4.6: lookup_evidence ───────────────────────────────


def test_lookup_evidence_found() -> None:
    idx = FactIndex()
    f = _make_fact("f1", evidence_ids=("ev1", "ev2"))
    idx.add_fact(f)
    assert len(idx.lookup_evidence("ev1")) == 1
    assert len(idx.lookup_evidence("ev2")) == 1


def test_lookup_evidence_empty_ids() -> None:
    idx = FactIndex()
    f = _make_fact("f1", evidence_ids=())
    idx.add_fact(f)
    assert idx.lookup_evidence("ev1") == []


# ── B4.7: remove_fact ───────────────────────────────────


def test_remove_fact() -> None:
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple", evidence_ids=("ev1",))
    idx.add_fact(f)
    removed = idx.remove_fact("f1")
    assert removed is f
    assert idx.size == 0
    assert idx.lookup("f1") is None
    assert idx.lookup_entity("apple") == []
    assert idx.lookup_evidence("ev1") == []


def test_remove_fact_not_found_raises() -> None:
    idx = FactIndex()
    with pytest.raises(KeyError, match="not found"):
        idx.remove_fact("nonexistent")


def test_remove_fact_frozen_raises() -> None:
    idx = FactIndex()
    idx.freeze()
    with pytest.raises(RuntimeError, match="Cannot modify frozen"):
        idx.remove_fact("f1")


# ── B4.8: build (batch construction) ────────────────────


def test_build_empty() -> None:
    idx = FactIndex.build([])
    assert idx.size == 0
    assert idx.frozen is True


def test_build_with_facts() -> None:
    facts = [
        _make_fact("f1", subject="Apple"),
        _make_fact("f2", subject="Tesla"),
    ]
    idx = FactIndex.build(facts)
    assert idx.size == 2
    assert idx.frozen is True
    assert len(idx.lookup_entity("apple")) == 1
    assert len(idx.lookup_entity("tesla")) == 1


def test_build_skips_duplicates() -> None:
    facts = [
        _make_fact("f1", subject="Apple"),
        _make_fact("f1", subject="Tesla"),  # duplicate id
    ]
    idx = FactIndex.build(facts)
    assert idx.size == 1
    # First fact prevails
    assert len(idx.lookup_entity("apple")) == 1
    assert len(idx.lookup_entity("tesla")) == 0


def test_build_result_is_frozen() -> None:
    idx = FactIndex.build([_make_fact("f1")])
    with pytest.raises(RuntimeError):
        idx.add_fact(_make_fact("f2"))


# ── B4.9: freeze + copy-on-write ────────────────────────


def test_freeze_prevents_writes() -> None:
    idx = FactIndex()
    idx.freeze()
    with pytest.raises(RuntimeError):
        idx.add_fact(_make_fact("f1"))


def test_copy_produces_mutable_index() -> None:
    idx = FactIndex.build([_make_fact("f1", subject="Apple")])
    mutable = idx.copy()
    assert mutable.frozen is False
    mutable.add_fact(_make_fact("f2", subject="Tesla"))
    assert mutable.size == 2


def test_copy_shares_facts() -> None:
    f = _make_fact("f1")
    idx = FactIndex.build([f])
    mutable = idx.copy()
    assert mutable.lookup("f1") is f  # same reference


def test_copy_independent_lists() -> None:
    idx = FactIndex.build([
        _make_fact("f1", subject="Apple"),
        _make_fact("f2", subject="Apple"),
    ])
    mutable = idx.copy()
    # Remove from mutable should not affect original
    mutable.remove_fact("f1")
    assert len(idx.lookup_entity("apple")) == 2
    assert len(mutable.lookup_entity("apple")) == 1


# ── B4.10: edge cases ──────────────────────────────────


def test_index_with_no_evidence() -> None:
    idx = FactIndex()
    f = _make_fact("f1", evidence_ids=())
    idx.add_fact(f)
    assert idx.size == 1
    assert idx.lookup("f1") is f


def test_index_empty_subject_predicate() -> None:
    idx = FactIndex()
    f = KnowledgeFact(
        id="f1", subject="", predicate="", object="raw text",
        confidence=0.5,
    )
    idx.add_fact(f)
    assert idx.lookup("f1") is f
    assert idx.lookup_entity("") == [f]


def test_multiple_evidence_same_fact() -> None:
    idx = FactIndex()
    f = _make_fact("f1", evidence_ids=("ev1", "ev2", "ev3"))
    idx.add_fact(f)
    assert len(idx.lookup_evidence("ev1")) == 1
    assert len(idx.lookup_evidence("ev2")) == 1
    assert len(idx.lookup_evidence("ev3")) == 1


def test_1000_facts_then_lookup() -> None:
    idx = FactIndex()
    facts = [_make_fact(f"f{i}", subject=f"Entity{i % 50}") for i in range(1000)]
    for f in facts:
        idx.add_fact(f)
    assert idx.size == 1000
    assert len(idx.lookup_entity("entity0")) == 1000 // 50  # ~20


# ── B4.11: determinism ──────────────────────────────────


def test_build_deterministic() -> None:
    facts = [
        _make_fact("f1", subject="Apple"),
        _make_fact("f2", subject="Tesla"),
    ]
    a = FactIndex.build(list(facts))
    b = FactIndex.build(list(facts))
    assert a.lookup("f1") is not None
    assert b.lookup("f1") is not None
    assert len(a.lookup_entity("apple")) == len(b.lookup_entity("apple"))


def test_lookup_order_deterministic() -> None:
    """Mismos datos de entrada → mismo orden de resultados."""
    f1 = _make_fact("f1", subject="Apple")
    f2 = _make_fact("f2", subject="Apple")
    idx = FactIndex.build([f1, f2])
    r1 = idx.lookup_entity("apple")
    r2 = idx.lookup_entity("apple")
    assert [f.id for f in r1] == [f.id for f in r2]


# ── B4.12: benchmarks ──────────────────────────────────


def test_benchmark_build_1000() -> None:
    facts = [_make_fact(f"f{i}") for i in range(1000)]
    start = time.perf_counter()
    FactIndex.build(facts)
    t = time.perf_counter() - start
    # Should be well under 100ms
    assert t < 0.1, f"Build 1K facts took {t*1000:.1f}ms"


def test_benchmark_build_10000() -> None:
    facts = [_make_fact(f"f{i}") for i in range(10000)]
    start = time.perf_counter()
    FactIndex.build(facts)
    t = time.perf_counter() - start
    # Should be under 500ms
    assert t < 0.5, f"Build 10K facts took {t*1000:.1f}ms"


def test_benchmark_lookup_10000() -> None:
    facts = [_make_fact(f"f{i}") for i in range(10000)]
    idx = FactIndex.build(facts)
    start = time.perf_counter()
    for i in range(10000):
        idx.lookup(f"f{i}")
    t = time.perf_counter() - start
    # Should be under 10ms for 10K lookups
    assert t < 0.01, f"10K lookups took {t*1000:.1f}ms"


def test_benchmark_incremental_add() -> None:
    """Incremental update cost O(Δ): adding 100 facts to existing 10K."""
    core = [_make_fact(f"f{i}") for i in range(10000)]
    idx = FactIndex.build(core)
    new_facts = [_make_fact(f"new{i}") for i in range(100)]
    start = time.perf_counter()
    # Copy-on-write: copy + add
    mutable = idx.copy()
    for f in new_facts:
        mutable.add_fact(f)
    t = time.perf_counter() - start
    # Should be well under 50ms
    assert t < 0.05, f"Incremental add 100 took {t*1000:.1f}ms"


def test_benchmark_memory_estimate() -> None:
    """Estimar footprint de 10K facts en el índice."""
    facts = [_make_fact(f"f{i}", evidence_ids=("ev1", "ev2")) for i in range(10000)]
    # Use sys.getsizeof for rough estimate
    idx = FactIndex.build(facts)
    # Rough memory check: each fact + indexes
    # Just verify it doesn't blow up (practical check)
    assert idx.size == 10000
    # Print memory for visibility (not an assertion)
    fact_size = sum(sys.getsizeof(f) for f in facts)
    print(f"\n  10K facts total size: {fact_size / 1024:.1f} KB")


# ── B4.13: consistency across indexes ──────────────────


def _all_secondary_fact_ids(idx: FactIndex) -> set[str]:
    """Retorna todos los fact_ids referenciados en índices secundarios."""
    ids: set[str] = set()
    for inner in idx._by_entity.values():
        ids.update(inner)
    for inner in idx._by_predicate.values():
        ids.update(inner)
    for inner in idx._by_sp.values():
        ids.update(inner)
    for inner in idx._by_evidence.values():
        ids.update(inner)
    return ids


def test_consistency_after_add() -> None:
    """Todo fact en índices secundarios existe en el primario."""
    idx = FactIndex()
    f1 = _make_fact("f1", subject="Apple", predicate="sells", evidence_ids=("ev1",))
    f2 = _make_fact("f2", subject="Tesla", predicate="makes", evidence_ids=("ev2",))
    idx.add_fact(f1)
    idx.add_fact(f2)
    secondary_ids = _all_secondary_fact_ids(idx)
    for fid in secondary_ids:
        assert idx.lookup(fid) is not None, f"Secondary index references {fid} not in primary"


def test_consistency_after_remove() -> None:
    """Ningún fact eliminado permanece en índices secundarios."""
    idx = FactIndex()
    f = _make_fact("f1", subject="Apple", predicate="sells", evidence_ids=("ev1",))
    idx.add_fact(f)
    idx.remove_fact("f1")
    secondary_ids = _all_secondary_fact_ids(idx)
    assert "f1" not in secondary_ids, "Removed fact still in secondary index"


def test_consistency_after_remove_all() -> None:
    """Eliminar todos los facts → índices secundarios vacíos."""
    idx = FactIndex()
    for i in range(10):
        idx.add_fact(_make_fact(f"f{i}", subject=f"E{i}", evidence_ids=(f"ev{i}",)))
    for i in range(10):
        idx.remove_fact(f"f{i}")
    assert idx.size == 0
    assert _all_secondary_fact_ids(idx) == set()


def test_consistency_build_equals_sequential_add() -> None:
    """build(list) produce el mismo estado que add_fact() secuencial."""
    facts = [
        _make_fact("f1", subject="Apple", predicate="sells", evidence_ids=("ev1",)),
        _make_fact("f2", subject="Tesla", predicate="makes", evidence_ids=("ev2",)),
        _make_fact("f3", subject="Apple", predicate="sells", evidence_ids=("ev3",)),
    ]
    idx_build = FactIndex.build(facts)
    idx_seq = FactIndex()
    for f in facts:
        idx_seq.add_fact(f)
    idx_seq.freeze()

    # Same primary
    assert idx_build.size == idx_seq.size
    for f in facts:
        assert (idx_build.lookup(f.id) is not None) == (idx_seq.lookup(f.id) is not None)

    # Same secondary indexes
    assert len(idx_build.lookup_entity("apple")) == len(idx_seq.lookup_entity("apple"))
    assert len(idx_build.lookup_predicate("sells")) == len(idx_seq.lookup_predicate("sells"))
    assert (
        len(idx_build.lookup_subject_predicate("Apple", "sells"))
        == len(idx_seq.lookup_subject_predicate("Apple", "sells"))
    )


def test_consistency_copy_preserves_integrity() -> None:
    """copy() preserva la consistencia entre índices."""
    facts = [_make_fact(f"f{i}", subject=f"E{i % 5}") for i in range(20)]
    idx = FactIndex.build(facts)
    mutable = idx.copy()
    # Añadir nuevo fact al mutable
    new_f = _make_fact("f99", subject="E99", evidence_ids=("ev99",))
    mutable.add_fact(new_f)
    secondary_ids = _all_secondary_fact_ids(mutable)
    for fid in secondary_ids:
        assert mutable.lookup(fid) is not None


# ── B4.14: skewed distribution benchmark ────────────────


def test_benchmark_skewed_distribution() -> None:
    """100 facts para una entidad + 9900 para otras."""
    facts = [_make_fact(f"f{i}", subject="HotEntity") for i in range(100)]
    facts += [_make_fact(f"g{j}", subject=f"Other{j}") for j in range(9900)]
    start = time.perf_counter()
    idx = FactIndex.build(facts)
    build_t = time.perf_counter() - start
    assert idx.size == 10000
    # Lookup on the hot entity
    start = time.perf_counter()
    hot = idx.lookup_entity("hotentity")
    lookup_t = time.perf_counter() - start
    assert len(hot) == 100
    assert build_t < 0.5, f"Skewed build took {build_t*1000:.1f}ms"
    assert lookup_t < 0.001, f"Hot entity lookup took {lookup_t*1000:.1f}ms"
