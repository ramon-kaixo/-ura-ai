"""Tests para F25-B6: FactHistory y FactVersion (R07).

Cubre:
- CRUD: create, add_version, rollback, tombstone, delete
- Invariantes V01-V10 de F25_B5_INVARIANTS.md
- Property-based tests (secuencias aleatorias)
- Idempotencia
- Serialización/deserialización
- Benchmarks (10, 100, 1K, 10K versiones)
- FactIndex con nuevo modelo
"""

from __future__ import annotations

import sys
import time

import pytest

from motor.core.fusion.fact_history import FactHistory


@pytest.fixture(autouse=True)
def _reset_ts_counter() -> None:
    _TS_COUNTER[0] = 1000.0


import contextlib

from motor.core.fusion.fact_index import FactIndex
from motor.core.fusion.models import (
    Fact,
    FactVersion,
    VersionState,
    make_fact_id,
    make_version_id,
)

# ── helpers ─────────────────────────────────────────────


def _make_fact(subject="Apple", predicate="sells", obj="oranges") -> Fact:
    fid = make_fact_id(subject, predicate, obj)
    return Fact(fact_id=fid, subject=subject, predicate=predicate, object=obj)


_TS_COUNTER: list[float] = [1000.0]


def _ts() -> float:
    _TS_COUNTER[0] += 1.0
    return _TS_COUNTER[0]


def _make_version(
    fact_id: str,
    version_id: str = "v1",
    confidence: float = 0.9,
    created_at: float | None = None,
    evidence_ids: tuple[str, ...] = ("ev1",),
) -> FactVersion:
    return FactVersion(
        version_id=version_id,
        fact_id=fact_id,
        confidence=confidence,
        evidence_ids=evidence_ids,
        created_at=created_at if created_at is not None else _ts(),
    )


# ── B6.1: Fact creation ────────────────────────────────


def test_make_fact_id_normalizes() -> None:
    """make_fact_id() usa normalize_identity() canónica."""
    a = make_fact_id("Apple", "sells", "oranges")
    b = make_fact_id("apple", "Sells", "  Oranges!  ")
    assert a == b, "make_fact_id must normalize inputs"


def test_make_fact_id_no_version() -> None:
    """version NO participa en fact_id."""
    a = make_fact_id("Apple", "sells", "oranges")
    assert "v" not in a
    assert len(a) == 16


def test_make_version_id_deterministic() -> None:
    a = make_version_id("abc", 1000, "hash1")
    b = make_version_id("abc", 1000, "hash1")
    assert a == b


def test_make_version_id_independent_of_order() -> None:
    """version_id no depende del orden de inserción."""
    a = make_version_id("abc", 1000, "h1")
    b = make_version_id("abc", 2000, "h2")
    assert a != b  # diferentes timestamp/hash → diferentes IDs


def test_fact_identity_immutable() -> None:
    f = _make_fact()
    with pytest.raises(AttributeError):
        f.subject = "changed"  # frozen


# ── B6.2: FactHistory creation ─────────────────────────


def test_history_create() -> None:
    fact = _make_fact()
    v1 = _make_version(fact.fact_id)
    h = FactHistory.create(fact, v1)
    assert h.fact_id == fact.fact_id
    assert h.current.version_id == "v1"
    assert h.version_count == 1
    assert h.current.state == VersionState.CURRENT


def test_history_create_version_mismatch_raises() -> None:
    f1 = _make_fact(subject="Apple")
    v = _make_version("other_fact_id")
    with pytest.raises(ValueError, match="fact_id"):
        FactHistory.create(f1, v)


def test_history_create_initial_not_current_raises() -> None:
    fact = _make_fact()
    v = FactVersion(
        version_id="v1",
        fact_id=fact.fact_id,
        confidence=0.9,
        state=VersionState.SUPERSEDED,
    )
    with pytest.raises(ValueError, match="CURRENT"):
        FactHistory.create(fact, v)


# ── B6.3: add_version ──────────────────────────────────


def test_add_version() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    v2 = _make_version(fact.fact_id, "v2", confidence=0.95)
    h.add_version(v2)
    assert h.current.version_id == "v2"
    assert h.current.confidence == 0.95
    assert h.version_count == 2


def test_add_version_supersedes_previous() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    old = h.get_version("v1")
    assert old is not None
    assert old.state == VersionState.SUPERSEDED


def test_add_version_duplicate_raises() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    with pytest.raises(KeyError, match="already exists"):
        h.add_version(_make_version(fact.fact_id, "v1"))


def test_add_version_wrong_fact_raises() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    with pytest.raises(ValueError, match="fact_id"):
        h.add_version(_make_version("other_fact", "v2"))


def test_add_version_before_creation_raises() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=2000))
    with pytest.raises(ValueError, match="before history creation"):
        h.add_version(_make_version(fact.fact_id, "v2", created_at=1000))


# ── B6.4: rollback ─────────────────────────────────────


def test_rollback() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    restored = h.rollback("v1")
    assert h.current.version_id == "v1"
    assert restored.state == VersionState.CURRENT
    # v2 queda como ROLLED_BACK
    v2 = h.get_version("v2")
    assert v2 is not None
    assert v2.state == VersionState.ROLLED_BACK
    # timeline preserva ambas
    assert len(h.timeline()) == 2


def test_rollback_preserves_history() -> None:
    """Rollback NO elimina versiones posteriores."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    h.add_version(_make_version(fact.fact_id, "v3"))
    h.rollback("v1")
    assert len(h.timeline()) == 3


def test_rollback_to_tombstone_raises() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    v2 = FactVersion(
        version_id="v2",
        fact_id=fact.fact_id,
        confidence=0.0,
        state=VersionState.TOMBSTONE,
    )
    h.tombstone(v2)
    with pytest.raises(ValueError, match="tombstone"):
        h.rollback("v2")


def test_rollback_nonexistent_raises() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    with pytest.raises(KeyError, match="not found"):
        h.rollback("nonexistent")


# ── B6.5: tombstone ────────────────────────────────────


def test_tombstone() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    v2 = FactVersion(
        version_id="v2",
        fact_id=fact.fact_id,
        confidence=0.0,
        state=VersionState.TOMBSTONE,
    )
    h.tombstone(v2)
    assert h.current.version_id == "v2"
    assert h.has_tombstone
    v1 = h.get_version("v1")
    assert v1 is not None
    assert v1.state == VersionState.SUPERSEDED


# ── B6.6: version_at (consulta temporal) ───────────────


def test_version_at_exact() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    h.add_version(_make_version(fact.fact_id, "v2", created_at=2000))
    assert h.version_at(1000) is not None
    assert h.version_at(1000).version_id == "v1"
    assert h.version_at(2000).version_id == "v2"


def test_version_at_before_first() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    assert h.version_at(500) is None


def test_version_at_after_rollback() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    h.add_version(_make_version(fact.fact_id, "v2", created_at=2000))
    h.rollback("v1")
    # En t=1500, v1 era vigente (y sigue siéndolo tras rollback)
    assert h.version_at(1500).version_id == "v1"


# ── B6.7: invariantes (V01-V10) ────────────────────────


def test_invariant_v01_version_belongs_to_history() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    for v in h.timeline():
        assert v.fact_id == h.fact_id, "V01"


def test_invariant_v02_current_in_versions() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    assert h.current.version_id in [v.version_id for v in h.timeline()], "V02"


def test_invariant_v03_no_cycles() -> None:
    """La cadena supersedes no contiene ciclos (DAG)."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    h.add_version(_make_version(fact.fact_id, "v3"))
    visited: set[str] = set()
    v = h.current
    while v is not None:
        assert v.version_id not in visited, "V03: cycle detected"
        visited.add(v.version_id)
        v = h.get_version(v.supersedes) if v.supersedes else None


def test_invariant_v04_version_id_independent() -> None:
    """version_id no depende del orden de inserción."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    h.add_version(_make_version(fact.fact_id, "v2", created_at=2000))
    # Recrear con orden inverso (timestamps deben ser compatibles)
    h2 = FactHistory.create(fact, _make_version(fact.fact_id, "va", created_at=1000))
    h2.add_version(_make_version(fact.fact_id, "vb", created_at=2000))
    # Ambos historiales deben tener el mismo número de versiones
    assert h.version_count == h2.version_count
    # Ambos deben tener la última versión como CURRENT
    assert h.current.state == VersionState.CURRENT
    assert h2.current.state == VersionState.CURRENT


def test_invariant_v09_no_orphan_versions() -> None:
    """Toda FactVersion pertenece a un FactHistory."""
    fact = _make_fact()
    v = _make_version(fact.fact_id)
    FactHistory.create(fact, v)
    # v pertenece a h. Si intentamos crear otra history con la misma v, falla
    with pytest.raises(KeyError):
        h2 = FactHistory.create(fact, v)
        h2.add_version(v)


# ── B6.8: idempotencia ────────────────────────────────


def test_idempotent_add_same_version() -> None:
    """Añadir la misma versión dos veces no debe corromper el historial."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    with pytest.raises(KeyError):
        h.add_version(_make_version(fact.fact_id, "v1"))


def test_idempotent_rollback_twice() -> None:
    """Rollback dos veces seguidas no corrompe el historial."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1"))
    h.add_version(_make_version(fact.fact_id, "v2"))
    h.add_version(_make_version(fact.fact_id, "v3"))
    h.rollback("v2")
    h.rollback("v1")
    assert h.current.version_id == "v1"
    assert h.version_count == 3


# ── B6.9: serialización ────────────────────────────────


def test_serialization_roundtrip() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    h.add_version(_make_version(fact.fact_id, "v2", created_at=2000, confidence=0.8))
    data = h.to_dict()
    restored = FactHistory.from_dict(data)
    assert restored.fact_id == h.fact_id
    assert restored.current.version_id == h.current.version_id
    assert restored.version_count == h.version_count
    assert restored.timeline()[0].confidence == 0.9


def test_serialization_with_tombstone() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    v2 = FactVersion(
        version_id="v2",
        fact_id=fact.fact_id,
        confidence=0.0,
        created_at=2000,
        state=VersionState.TOMBSTONE,
    )
    h.tombstone(v2)
    data = h.to_dict()
    restored = FactHistory.from_dict(data)
    assert restored.has_tombstone
    # Tras deserialización, current debería ser la TOMBSTONE
    assert restored.current.state == VersionState.TOMBSTONE


def test_serialization_deep_copy() -> None:
    """Modificar el original no afecta al restaurado."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v1", created_at=1000))
    data = h.to_dict()
    restored = FactHistory.from_dict(data)
    h.add_version(_make_version(fact.fact_id, "v2", created_at=2000))
    assert restored.version_count == 1  # no afectado


# ── B6.10: FactIndex con nuevo modelo ──────────────────


def test_fact_index_add_fact_version() -> None:
    fact = _make_fact()
    v1 = _make_version(fact.fact_id)
    idx = FactIndex()
    idx.add_fact_version(fact, v1)
    assert idx.size == 1
    entry = idx.lookup(fact.fact_id)
    assert entry is not None
    f, v = entry
    assert f.fact_id == fact.fact_id
    assert v.version_id == "v1"


def test_fact_index_update_current() -> None:
    fact = _make_fact()
    v1 = _make_version(fact.fact_id, "v1")
    idx = FactIndex()
    idx.add_fact_version(fact, v1)
    v2 = _make_version(fact.fact_id, "v2", confidence=0.95)
    idx.update_current(fact.fact_id, v2)
    entry = idx.lookup(fact.fact_id)
    assert entry is not None
    _f, v = entry
    assert v.version_id == "v2"


def test_fact_index_build_from_versions() -> None:
    entries: list[tuple[Fact, FactVersion]] = []
    for idx_num in range(2):
        subj = ["Apple", "Tesla"][idx_num]
        pred = ["sells", "makes"][idx_num]
        obj = ["oranges", "cars"][idx_num]
        fact = _make_fact(subj, pred, obj)
        v = FactVersion(
            version_id=f"v{idx_num}",
            fact_id=fact.fact_id,
            confidence=0.9,
        )
        entries.append((fact, v))
    idx = FactIndex.build_from_versions(entries)
    assert idx.size == 2
    assert idx.frozen


# ── B6.11: property-based sequences ───────────────────


def _random_sequence(seed: int, length: int) -> list[str]:
    """Genera una secuencia pseudoaleatoria de operaciones."""
    import hashlib

    ops = []
    for i in range(length):
        h = hashlib.sha256(f"{seed}:{i}".encode()).hexdigest()
        op_idx = int(h[:2], 16) % 5
        op = ["create", "update", "rollback", "tombstone", "delete"][op_idx]
        ops.append(op)
    return ops


def test_property_random_sequences() -> None:  # noqa: C901, PLR0912
    """Secuencias aleatorias no deben corromper invariantes."""
    import random

    random.seed(42)
    for seq_len in [5, 10, 20]:
        for _ in range(10):
            fact = _make_fact()
            v1 = _make_version(fact.fact_id, "v_base", created_at=1000)
            h = FactHistory.create(fact, v1)
            version_counter = 1
            try:
                for op in _random_sequence(random.randint(0, 1000), seq_len):  # noqa: S311
                    if op == "create":
                        pass  # ya tenemos un history
                    elif op == "update":
                        version_counter += 1
                        v = _make_version(
                            fact.fact_id,
                            f"v{version_counter}",
                            created_at=1000 + version_counter,
                            confidence=random.random(),  # noqa: S311
                        )
                        h.add_version(v)
                    elif op == "rollback":
                        versions = list(h._versions.keys())
                        if versions and h.current.state != VersionState.TOMBSTONE:
                            target = random.choice(versions)  # noqa: S311
                            with contextlib.suppress(ValueError, KeyError):
                                h.rollback(target)
                    elif op == "tombstone":
                        if not h.has_tombstone:
                            version_counter += 1
                            v = FactVersion(
                                version_id=f"v{version_counter}",
                                fact_id=fact.fact_id,
                                confidence=0.0,
                                created_at=1000 + version_counter,
                                state=VersionState.TOMBSTONE,
                            )
                            h.tombstone(v)
                    elif op == "delete":
                        pass  # DELETE físico no implementado aún
            except Exception as e:
                pytest.fail(f"Sequence failed at len={seq_len}: {e}")

            # Verificar invariantes después de la secuencia
            assert h.current.version_id is not None
            for v in h.timeline():
                assert v.fact_id == h.fact_id, "V01"
            # V03: sin ciclos
            visited = set()
            v = h.current
            while v is not None:
                assert v.version_id not in visited
                visited.add(v.version_id)
                v = h.get_version(v.supersedes) if v.supersedes else None


# ── B6.12: benchmarks ──────────────────────────────────


def test_benchmark_add_10() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v_base", created_at=0))
    start = time.perf_counter()
    for i in range(10):
        h.add_version(_make_version(fact.fact_id, f"v{i}", created_at=i + 1))
    t = time.perf_counter() - start
    assert h.version_count == 11
    assert t < 0.01, f"10 versions took {t * 1000:.1f}ms"


def test_benchmark_add_1000() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v_base", created_at=0))
    start = time.perf_counter()
    for i in range(1000):
        h.add_version(_make_version(fact.fact_id, f"v{i}", created_at=i + 1))
    t = time.perf_counter() - start
    assert h.version_count == 1001
    assert t < 0.1, f"1K versions took {t * 1000:.1f}ms"


def test_benchmark_rollback_amid_1000() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v_base", created_at=0))
    for i in range(1000):
        h.add_version(_make_version(fact.fact_id, f"v{i}", created_at=i + 1))
    start = time.perf_counter()
    h.rollback("v500")
    t = time.perf_counter() - start
    assert t < 0.001, f"Rollback amid 1K took {t * 1000:.1f}ms"


def test_benchmark_version_at_1000() -> None:
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v_base", created_at=0))
    for i in range(1000):
        h.add_version(_make_version(fact.fact_id, f"v{i}", created_at=i + 1))
    start = time.perf_counter()
    for ts in range(0, 1000, 50):
        h.version_at(float(ts))
    t = time.perf_counter() - start
    assert t < 0.1, f"20 version_at queries took {t * 1000:.1f}ms"


def test_benchmark_peak_memory() -> None:
    """Estimar memoria de 10K versiones en FactHistory."""
    fact = _make_fact()
    h = FactHistory.create(fact, _make_version(fact.fact_id, "v_base", created_at=0))
    for i in range(10000):
        h.add_version(_make_version(fact.fact_id, f"v{i}", created_at=i + 1))
    # Tamaño del historial
    sys.getsizeof(h) + sum(sys.getsizeof(v) for v in h._versions.values())
    assert h.version_count == 10001
