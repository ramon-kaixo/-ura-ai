"""Tests para F26-B2: Memoria Histórica (infraestructura mínima).

Cubre:
- MemoryEntry, FactRef, make_entry_id
- MemoryTimeline (append, state_at, by_entity, by_time, by_event, diff)
- Journal (append, read, rotate)
- Snapshot (save, load, checksum, corrupción)
- Memory (wrapper, recover, load/save cycle)
- state_at O(log n) tie-breaking
- Determinismo, concurrencia, consistencia
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

import pytest

from motor.memory import (
    FactRef,
    Journal,
    Memory,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
    MemoryTimeline,
    load_snapshot,
    make_entry_id,
    save_snapshot,
)
from motor.memory.models import SnapshotHeader


# ── helpers ─────────────────────────────────────────────


def _make_ref(fact_id: str = "f1", version_id: str = "v1", subject: str = "Apple") -> FactRef:
    return FactRef(
        fact_id=fact_id, version_id=version_id,
        subject=subject, predicate="sells", object="oranges",
    )


def _make_entry(
    entry_id: str = "",
    timestamp: float = 1000,
    fact_refs: tuple[FactRef, ...] = (_make_ref(),),
    source: str = "test",
    event_type: MemoryEventType = MemoryEventType.FACT_ADDED,
) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id or make_entry_id(
            event_type.value, [r.version_id for r in fact_refs], timestamp,
        ),
        timestamp=timestamp,
        fact_refs=fact_refs,
        source=source,
        event_type=event_type,
    )


def _make_timeline() -> MemoryTimeline:
    tl = MemoryTimeline()
    tl.append(_make_entry(timestamp=1000))
    tl.append(_make_entry(timestamp=2000, fact_refs=(_make_ref("f2"),)))
    tl.append(_make_entry(timestamp=3000, fact_refs=(_make_ref("f3"),)))
    return tl


# ═══════════════════════════════════════════════════
# B2.1: Models
# ═══════════════════════════════════════════════════


def test_make_entry_id_deterministic() -> None:
    a = make_entry_id("fact_added", ["v1", "v2"], 1000)
    b = make_entry_id("fact_added", ["v1", "v2"], 1000)
    assert a == b


def test_make_entry_id_based_on_content() -> None:
    """IDs diferentes para contenido diferente."""
    a = make_entry_id("fact_added", ["v1"], 1000)
    b = make_entry_id("fact_added", ["v2"], 1000)
    assert a != b


def test_make_entry_id_independent_of_order() -> None:
    a = make_entry_id("fact_added", ["v1", "v2"], 1000)
    b = make_entry_id("fact_added", ["v2", "v1"], 1000)
    assert a == b  # sorted internamente


def test_fact_ref_immutable() -> None:
    ref = _make_ref()
    with pytest.raises(AttributeError):
        ref.subject = "changed"  # frozen


def test_fact_ref_fields() -> None:
    ref = FactRef(fact_id="f1", version_id="v3", subject="S", predicate="P", object="O")
    assert ref.fact_id == "f1"
    assert ref.version_id == "v3"


def test_memory_entry_frozen() -> None:
    entry = _make_entry()
    with pytest.raises(AttributeError):
        entry.timestamp = 999


# ═══════════════════════════════════════════════════
# B2.2: MemoryTimeline
# ═══════════════════════════════════════════════════


def test_timeline_append() -> None:
    tl = MemoryTimeline()
    tl.append(_make_entry())
    assert tl.size == 1


def test_timeline_append_duplicate_raises() -> None:
    tl = MemoryTimeline()
    entry = _make_entry()
    tl.append(entry)
    with pytest.raises(KeyError, match="already exists"):
        tl.append(entry)


def test_state_at_exact() -> None:
    tl = _make_timeline()
    assert tl.state_at(1000) is not None
    assert tl.state_at(1000).timestamp == 1000


def test_state_at_between() -> None:
    tl = _make_timeline()
    entry = tl.state_at(1500)
    assert entry is not None
    assert entry.timestamp == 1000  # el entry en t=1000 es el vigente en t=1500


def test_state_at_before_first() -> None:
    tl = _make_timeline()
    assert tl.state_at(500) is None


def test_state_at_after_last() -> None:
    tl = _make_timeline()
    entry = tl.state_at(5000)
    assert entry is not None
    assert entry.timestamp == 3000


def test_state_at_tie_breaking() -> None:
    """Mismo timestamp → prevalece el de mayor entry_id."""
    tl = MemoryTimeline()
    e1 = _make_entry(entry_id="a", timestamp=1000, fact_refs=(_make_ref("f1", "v1"),))
    e2 = _make_entry(entry_id="b", timestamp=1000, fact_refs=(_make_ref("f2", "v2"),))
    tl.append(e1)
    tl.append(e2)
    result = tl.state_at(1000)
    assert result is not None
    # Debe ser el de mayor entry_id (e2 > e1 lexicográficamente)
    assert result.entry_id == max(e1.entry_id, e2.entry_id)


def test_by_entity() -> None:
    tl = _make_timeline()
    results = tl.by_entity("apple")
    assert len(results) >= 1


def test_by_entity_case_insensitive() -> None:
    tl = _make_timeline()
    assert len(tl.by_entity("APPLE")) >= 1


def test_by_time_range() -> None:
    tl = _make_timeline()
    results = tl.by_time(1500, 2500)
    assert len(results) == 1


def test_by_event() -> None:
    tl = MemoryTimeline()
    tl.append(_make_entry(event_type=MemoryEventType.FACT_ADDED))
    results = tl.by_event("fact_added")
    assert len(results) == 1


def test_get_entry() -> None:
    tl = _make_timeline()
    entry = _make_entry(timestamp=5000)
    tl.append(entry)
    assert tl.get(entry.entry_id) is entry


def test_diff() -> None:
    tl = MemoryTimeline()
    e1 = _make_entry(timestamp=1000, fact_refs=(_make_ref("f1"),))
    e2 = _make_entry(timestamp=2000, fact_refs=(_make_ref("f1"), _make_ref("f2")))
    tl.append(e1)
    tl.append(e2)
    d = tl.diff(e1.entry_id, e2.entry_id)
    assert "f2" in d["added"]
    assert "f1" in d["common"]
    assert len(d["removed"]) == 0


# ═══════════════════════════════════════════════════
# B2.3: Journal
# ═══════════════════════════════════════════════════


def test_journal_append_and_read(tmp_path: str) -> None:
    path = os.path.join(tmp_path, "journal.jsonl")
    j = Journal()
    j.open(path)
    j.append(_make_entry())
    j.append(_make_entry(timestamp=2000))
    j.close()
    entries = j.read_all()
    assert len(entries) == 2


def test_journal_rotate(tmp_path: str) -> None:
    path = os.path.join(tmp_path, "journal.jsonl")
    backup = os.path.join(tmp_path, "journal.bak")
    j = Journal()
    j.open(path)
    j.append(_make_entry())
    j.rotate(backup)
    assert j.count == 0
    assert os.path.exists(backup)


def test_journal_count(tmp_path: str) -> None:
    path = os.path.join(tmp_path, "journal.jsonl")
    j = Journal()
    j.open(path)
    j.append(_make_entry())
    j.append(_make_entry(timestamp=2000))
    assert j.count == 2


# ═══════════════════════════════════════════════════
# B2.4: Snapshot
# ═══════════════════════════════════════════════════


def test_snapshot_save_and_load(tmp_path: str) -> None:
    tl = _make_timeline()
    path = os.path.join(tmp_path, "snapshot.json")
    cs = save_snapshot(tl, path)
    assert len(cs) == 16
    header, entries = load_snapshot(path)
    assert header["entry_count"] == 3
    assert len(entries) == 3


def test_snapshot_checksum_validation(tmp_path: str) -> None:
    tl = _make_timeline()
    path = os.path.join(tmp_path, "snapshot.json")
    save_snapshot(tl, path)
    # Corromper el archivo
    with open(path, "r") as f:
        data = json.load(f)
    data["entries"]["corrupted"] = {"entry_id": "bad"}
    with open(path, "w") as f:
        json.dump(data, f)
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_snapshot(path)


# ═══════════════════════════════════════════════════
# B2.5: Memory (wrapper + recovery)
# ═══════════════════════════════════════════════════


def test_memory_append() -> None:
    m = Memory()
    m.append(_make_entry())
    assert m.timeline.size == 1


def test_memory_state_at() -> None:
    m = Memory()
    m.append(_make_entry(timestamp=1000))
    m.append(_make_entry(timestamp=2000))
    assert m.state_at(1500).timestamp == 1000
    assert m.state_at(2000).timestamp == 2000


def test_memory_load_cycle(tmp_path: str) -> None:
    """Memory → snapshot → load → mismo estado."""
    m1 = Memory()
    m1.append(_make_entry(timestamp=1000))
    m1.append(_make_entry(timestamp=2000))
    path = os.path.join(tmp_path, "cycle.json")
    m1.save(path)
    m2 = Memory.load(path)
    assert m2.timeline.size == 2
    assert m2.state_at(1000).timestamp == 1000
    assert m2.state_at(2000).timestamp == 2000


def test_memory_recover_from_snapshot_and_journal(tmp_path: str) -> None:
    """Recuperación desde snapshot + journal."""
    snap_path = os.path.join(tmp_path, "snap.json")
    journal_path = os.path.join(tmp_path, "journal.jsonl")

    m1 = Memory(snapshot_path=snap_path, journal_path=journal_path)
    m1.append(_make_entry(timestamp=1000))
    m1.snapshot(version="v1")
    m1.append(_make_entry(timestamp=2000))
    m1.close()

    # Nueva instancia: debe recuperar snapshot + journal
    m2 = Memory(snapshot_path=snap_path, journal_path=journal_path, auto_recover=True)
    assert m2.timeline.size == 2
    assert m2.state_at(500) is None
    assert m2.state_at(1000).timestamp == 1000
    assert m2.state_at(2000).timestamp == 2000
    m2.close()


# ═══════════════════════════════════════════════════
# B2.6: Concurrencia
# ═══════════════════════════════════════════════════


def test_concurrent_readers_during_append() -> None:
    tl = MemoryTimeline()
    for i in range(10):
        tl.append(_make_entry(timestamp=float(i * 1000), fact_refs=(_make_ref(f"f{i}"),)))

    errors: list[Exception] = []
    lock = threading.Lock()

    def writer() -> None:
        for i in range(10, 20):
            with lock:
                try:
                    tl.append(_make_entry(timestamp=float(i * 1000), fact_refs=(_make_ref(f"f{i}"),)))
                except Exception as e:
                    errors.append(e)

    def reader() -> None:
        for _ in range(20):
            with lock:
                try:
                    _ = tl.state_at(5000)
                    _ = tl.by_entity("apple")
                    _ = tl.size
                except Exception as e:
                    errors.append(e)

    threads = [threading.Thread(target=writer, daemon=True)]
    threads += [threading.Thread(target=reader, daemon=True) for _ in range(5)]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Concurrent errors: {errors}"
    assert tl.size >= 10


# ═══════════════════════════════════════════════════
# B2.7: Determinismo
# ═══════════════════════════════════════════════════


def test_deterministic_entry_id() -> None:
    """Mismos datos → mismo entry_id."""
    refs = [_make_ref("f1"), _make_ref("f2")]
    ts = 1000.0
    e1 = _make_entry(timestamp=ts, fact_refs=tuple(refs))
    e2 = _make_entry(timestamp=ts, fact_refs=tuple(refs))
    assert e1.entry_id == e2.entry_id


def test_deterministic_state_at() -> None:
    """Misma timeline → mismo resultado en state_at."""
    def build() -> MemoryTimeline:
        tl = MemoryTimeline()
        tl.append(_make_entry(timestamp=1000))
        tl.append(_make_entry(timestamp=2000))
        return tl

    r1 = build().state_at(1500)
    r2 = build().state_at(1500)
    assert r1 is not None and r2 is not None
    assert r1.entry_id == r2.entry_id


# ═══════════════════════════════════════════════════
# B2.8: Benchmarks
# ═══════════════════════════════════════════════════


def test_benchmark_append_1000() -> None:
    tl = MemoryTimeline()
    start = time.perf_counter()
    for i in range(1000):
        tl.append(_make_entry(timestamp=float(i * 1000), fact_refs=(_make_ref(f"f{i}"),)))
    t = time.perf_counter() - start
    assert tl.size == 1000
    assert t < 0.5, f"1000 appends took {t*1000:.1f}ms"


def test_benchmark_state_at_1000() -> None:
    tl = MemoryTimeline()
    for i in range(1000):
        tl.append(_make_entry(timestamp=float(i * 1000), fact_refs=(_make_ref(f"f{i}"),)))
    start = time.perf_counter()
    for ts in range(0, 1000 * 1000, 1000):
        tl.state_at(float(ts))
    t = time.perf_counter() - start
    assert t < 0.5, f"1000 state_at queries took {t*1000:.1f}ms"


def test_benchmark_peak_memory_10k() -> None:
    """RAM estimada para 10K entries."""
    tl = MemoryTimeline()
    for i in range(10000):
        tl.append(_make_entry(
            timestamp=float(i * 1000),
            fact_refs=tuple(_make_ref(f"f{j}") for j in range(3)),
        ))
    # Tamaño aproximado (solo entries)
    size = sys.getsizeof(tl) + sum(
        sys.getsizeof(e) for e in tl.entries.values()
    )
    print(f"\n  10K entries: ~{size / 1024:.1f} KB")
    assert tl.size == 10000
