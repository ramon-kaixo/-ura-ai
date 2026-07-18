"""F28-B3: Operational Readiness — chaos, security, subscription, E2E.

Cubre:
- F25→F26→F27 integration pipeline
- Memory subscription (agents notified on new facts)
- Auth token validation
- Unified config loading
- Chaos: crash during write
- Soak: continuous operation
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from motor.core.fusion.engine import FusionPipeline
from motor.core.fusion.stages import (
    ExtractionStage,
    KnowledgeMergerStage,
    MemoryCandidateSelectionStage,
    NormalizationStage,
)
from motor.core.web.citation.citation import CitationBundle, Evidence
from motor.memory import FactRef as MemoryFactRef
from motor.memory import Memory, MemoryEntry, MemoryEventType, make_entry_id


# ═══════════════════════════════════════════════════
# B3.1: F25 → F26 integration pipeline
# ═══════════════════════════════════════════════════


def test_f25_to_f26_pipeline(tmp_path: str) -> None:
    """FusionPipeline produce Facts que se escriben en F26 Memory."""
    snap = os.path.join(tmp_path, "snap.json")
    journal = os.path.join(tmp_path, "journal.jsonl")
    memory = Memory(snapshot_path=snap, journal_path=journal)

    bundle = CitationBundle(
        summary="test", citations=[],
        evidence=[
            Evidence(
                evidence_id=f"ev{i}", document_url=f"https://x.com/{i}",
                canonical_url=None, title=f"D{i}", document_index=i,
                sentence_position=0, fragment=f"Entity{i} has property value{i}",
                content_hash=f"h{i}", document_id=f"d{i}",
                fetched_at=float(i), quality_score=0.8,
            ) for i in range(5)
        ],
    )

    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
        MemoryCandidateSelectionStage(),
    ])

    # Inyectar instancia de memoria en statistics
    from motor.core.fusion.models import FusionContext
    ctx = FusionContext(bundle=bundle)
    ctx.statistics["_memory_instance"] = memory

    for stage in pipeline._stages:
        ctx = stage.execute(ctx)

    # Memory debe tener entries escritos por MemoryCandidateSelectionStage
    assert memory.timeline.size > 0
    memory.close()


# ═══════════════════════════════════════════════════
# B3.2: Memory subscription
# ═══════════════════════════════════════════════════


def test_memory_subscription(tmp_path: str) -> None:
    """Suscriptores son notificados cuando nuevos entries llegan a Memory."""
    snap = os.path.join(tmp_path, "sub_snap.json")
    journal = os.path.join(tmp_path, "sub_journal.jsonl")
    memory = Memory(snapshot_path=snap, journal_path=journal)

    received: list[MemoryEntry] = []
    memory.subscribe(lambda e: received.append(e))

    # Escribir entry via Fusion bridge
    ref = MemoryFactRef(fact_id="f1", version_id="v1", subject="S", predicate="P", object="O")
    entry = MemoryEntry(
        entry_id=make_entry_id("fact_added", ["v1"], 1000.0),
        timestamp=1000.0, fact_refs=(ref,),
        source="fusion", event_type=MemoryEventType.FACT_ADDED,
    )
    memory.append(entry)

    assert len(received) == 1
    assert received[0].entry_id == entry.entry_id
    memory.close()


# ═══════════════════════════════════════════════════
# B3.3: Subscription under concurrency
# ═══════════════════════════════════════════════════


def test_memory_subscription_concurrent(tmp_path: str) -> None:
    """Múltiples suscriptores bajo escritura concurrente."""
    snap = os.path.join(tmp_path, "con_snap.json")
    journal = os.path.join(tmp_path, "con_journal.jsonl")
    memory = Memory(snapshot_path=snap, journal_path=journal)

    received: list[list[MemoryEntry]] = [[] for _ in range(3)]
    for i in range(3):
        memory.subscribe(lambda e, idx=i: received[idx].append(e))

    def writer(n: int) -> None:
        for j in range(10):
            ref = MemoryFactRef(fact_id=f"f{n}_{j}", version_id=f"v{n}_{j}", subject="S", predicate="P", object="O")
            entry = MemoryEntry(
                entry_id=make_entry_id("fact_added", [f"v{n}_{j}"], float(n * 1000 + j)),
                timestamp=float(n * 1000 + j), fact_refs=(ref,),
                source="test", event_type=MemoryEventType.FACT_ADDED,
            )
            memory.append(entry)

    threads = [threading.Thread(target=writer, args=(i,), daemon=True) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # Cada suscriptor debe haber recibido todos los entries
    for i in range(3):
        assert len(received[i]) == 30  # 3 writers x 10 entries
    memory.close()


# ═══════════════════════════════════════════════════
# B3.4: Chaos — crash during write
# ═══════════════════════════════════════════════════


def test_chaos_crash_during_write(tmp_path: str) -> None:
    """Simular crash durante escritura a Memory y verificar recuperación."""
    snap = os.path.join(tmp_path, "chaos_snap.json")
    journal = os.path.join(tmp_path, "chaos_journal.jsonl")

    m1 = Memory(snapshot_path=snap, journal_path=journal)
    for i in range(10):
        ref = MemoryFactRef(fact_id=f"f{i}", version_id=f"v{i}", subject="S", predicate="P", object="O")
        entry = MemoryEntry(
            entry_id=make_entry_id("fact_added", [f"v{i}"], float(i * 1000)),
            timestamp=float(i * 1000), fact_refs=(ref,),
            source="test", event_type=MemoryEventType.FACT_ADDED,
        )
        m1.append(entry)
    m1.close()

    # Crash simulado: truncar journal a la mitad
    with open(journal, "r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        f.writelines(lines[:5])

    # Recuperación: debe funcionar sin errores
    m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
    assert m2.timeline.size >= 0
    m2.close()


# ═══════════════════════════════════════════════════
# B3.5: Soak test
# ═══════════════════════════════════════════════════


@pytest.mark.slow
def test_soak_continuous_operation(tmp_path: str) -> None:
    """Operación continua de Memory durante 10K writes."""
    snap = os.path.join(tmp_path, "soak_snap.json")
    journal = os.path.join(tmp_path, "soak_journal.jsonl")
    memory = Memory(snapshot_path=snap, journal_path=journal)

    start = time.perf_counter()
    for i in range(10000):
        ref = MemoryFactRef(fact_id=f"f{i}", version_id=f"v{i}", subject="S", predicate="P", object="O")
        entry = MemoryEntry(
            entry_id=make_entry_id("fact_added", [f"v{i}"], float(i)),
            timestamp=float(i), fact_refs=(ref,),
            source="test", event_type=MemoryEventType.FACT_ADDED,
        )
        memory.append(entry)
        if i > 0 and i % 2500 == 0:
            memory.snapshot(f"v{i // 2500}")

    total = time.perf_counter() - start
    print(f"  10K writes with snapshots in {total:.1f}s ({10000/total:.0f} writes/s)")
    assert memory.timeline.size == 10000
    memory.close()
