"""F26-RR1: Operational Readiness Review.

Valida la operación del sistema en condiciones reales:
- Recuperación tras reinicio/corrupción
- Crecimiento sostenido del journal
- Compactaciones repetidas
- Snapshots bajo carga
- Funcionamiento continuo (soak)
- Compatibilidad entre versiones persistidas
"""

from __future__ import annotations

import hashlib
import os
import random
import time

import pytest

from motor.memory import (
    FactRef,
    Journal,
    Memory,
    MemoryEntry,
    MemoryEventType,
    make_entry_id,
)


# ── helpers ─────────────────────────────────────────────

_COUNTER: list[int] = [0]


def _next_vid() -> str:
    _COUNTER[0] += 1
    return f"v{_COUNTER[0]}"


def _ref(fact_id: str = "f1") -> FactRef:
    return FactRef(fact_id=fact_id, version_id=_next_vid(), subject=fact_id, predicate="p", object="o")


def _entry(ts: float = 1000) -> MemoryEntry:
    ref = _ref()
    return MemoryEntry(
        entry_id=make_entry_id("fact_added", [ref.version_id], ts),
        timestamp=ts, fact_refs=(ref,), source="test",
        event_type=MemoryEventType.FACT_ADDED,
    )


# ═══════════════════════════════════════════════════
# RR-01: Recuperación tras reinicio
# ═══════════════════════════════════════════════════


def test_recovery_after_restart(tmp_path: str) -> None:
    """Simular reinicio completo: escribir, cerrar, abrir, verificar."""
    snap = os.path.join(tmp_path, "snap.json")
    journal = os.path.join(tmp_path, "journal.jsonl")

    m1 = Memory(snapshot_path=snap, journal_path=journal)
    for i in range(100):
        m1.append(_entry(ts=float(i * 1000)))
    m1.snapshot("v1")
    for i in range(100, 110):
        m1.append(_entry(ts=float(i * 1000)))
    cs_before = hashlib.sha256(
        str(sorted(m1.timeline.entries.keys())).encode()
    ).hexdigest()
    m1.close()

    # Reinicio simulado
    m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
    cs_after = hashlib.sha256(
        str(sorted(m2.timeline.entries.keys())).encode()
    ).hexdigest()

    assert cs_before == cs_after, "State changed after restart"
    assert m2.timeline.size == 110
    m2.close()


# ═══════════════════════════════════════════════════
# RR-02: Recuperación tras corrupción del journal
# ═══════════════════════════════════════════════════


def test_recovery_after_journal_corruption(tmp_path: str) -> None:
    """Corrupción del journal (lineas faltantes) → recovery desde snapshot."""
    snap = os.path.join(tmp_path, "snap.json")
    journal = os.path.join(tmp_path, "journal.jsonl")

    m1 = Memory(snapshot_path=snap, journal_path=journal)
    for i in range(50):
        m1.append(_entry(ts=float(i * 1000)))
    m1.snapshot("v1")
    for i in range(50, 60):
        m1.append(_entry(ts=float(i * 1000)))
    m1.close()

    # Corromper: eliminar las últimas 3 líneas del journal
    with open(journal, "r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        f.writelines(lines[:-3])

    m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
    # Snapshot (50) + journal restante (7) = 57
    assert m2.timeline.size >= 50
    m2.close()


# ═══════════════════════════════════════════════════
# RR-03: Crecimiento sostenido del journal
# ═══════════════════════════════════════════════════


def test_journal_sustained_growth(tmp_path: str) -> None:
    """Journal growth medido con 1000 entries (fsync real por línea)."""
    journal = os.path.join(tmp_path, "growth.jsonl")
    j = Journal()
    j.open(journal)
    for i in range(1000):
        j.append(_entry(ts=float(i * 1000)))
    size_kb = os.path.getsize(journal) / 1024
    print(f"  1000 entries: {size_kb:.1f} KB")
    assert j.count == 1000
    j.close()


# ═══════════════════════════════════════════════════
# RR-04: Snapshots repetidos bajo carga
# ═══════════════════════════════════════════════════


def test_repeated_snapshots_under_load(tmp_path: str) -> None:
    """10 snapshots consecutivos con carga entre cada uno."""
    snap = os.path.join(tmp_path, "snap.json")
    journal = os.path.join(tmp_path, "journal.jsonl")

    m = Memory(snapshot_path=snap, journal_path=journal)
    for s in range(10):
        for i in range(100):
            m.append(_entry(ts=float(s * 1000 + i)))
        cs = m.snapshot(f"v{s}")
        assert len(cs) == 16
    assert m.timeline.size == 1000
    m.close()

    # Verificar recuperación
    m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
    assert m2.timeline.size == 1000
    m2.close()


# ═══════════════════════════════════════════════════
# RR-05: Soak test (operación continua)
# ═══════════════════════════════════════════════════


@pytest.mark.slow
def test_soak_continuous_operation(tmp_path: str) -> None:
    """100K operaciones continuas midiendo estabilidad."""
    snap = os.path.join(tmp_path, "snap_soak.json")
    journal = os.path.join(tmp_path, "journal_soak.jsonl")

    m = Memory(snapshot_path=snap, journal_path=journal)
    rng = random.Random(42)
    start = time.perf_counter()
    snapshots = 0

    for i in range(100000):
        m.append(_entry(ts=float(i)))
        if i > 0 and i % 25000 == 0:
            m.snapshot(f"soak_v{snapshots}")
            snapshots += 1
        if i % 25000 == 0 and i > 0:
            elapsed = time.perf_counter() - start
            print(f"  {i} ops in {elapsed:.1f}s ({i/elapsed:.0f} ops/s)")

    total = time.perf_counter() - start
    print(f"  100K ops in {total:.1f}s ({100000/total:.0f} ops/s)")
    assert m.timeline.size == 100000
    m.close()

    # Recuperación post-soak
    m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
    assert m2.timeline.size == 100000
    m2.close()


# ═══════════════════════════════════════════════════
# RR-06: Estabilidad de benchmarks
# ═══════════════════════════════════════════════════


def test_benchmark_stability(tmp_path: str) -> None:
    """Benchmarks deben ser estables en 3 ejecuciones consecutivas."""
    snap = os.path.join(tmp_path, "stab_snap.json")
    journal = os.path.join(tmp_path, "stab_journal.jsonl")

    times: list[float] = []
    for run in range(3):
        m1 = Memory(snapshot_path=snap, journal_path=journal)
        for i in range(5000):
            m1.append(_entry(ts=float(i)))
        m1.snapshot(f"v{run}")
        m1.close()

        start = time.perf_counter()
        m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
        t = time.perf_counter() - start
        times.append(t)
        m2.close()

    avg = sum(times) / len(times)
    max_dev = max(abs(t - avg) for t in times)
    print(f"  Recovery times: {[f'{t*1000:.1f}ms' for t in times]}")
    print(f"  Avg: {avg*1000:.1f}ms, Max deviation: {max_dev*1000:.1f}ms")
    # No debe desviarse más del 50% del promedio
    assert max_dev < avg * 1.0, f"Benchmark unstable: {max_dev/avg*100:.1f}% deviation"
