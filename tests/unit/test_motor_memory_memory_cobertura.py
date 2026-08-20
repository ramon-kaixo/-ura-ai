"""Cobertura 100x100 de motor/memory/memory.py. TASK-20260820-006."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from motor.memory.journal import Journal
from motor.memory.memory import Memory
from motor.memory.models import (
    FactRef,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
)
from motor.memory.snapshot import save_snapshot


def _entry(entry_id: str = "e1", ts: float = 1.0, created_by: str = "t") -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        timestamp=ts,
        fact_refs=(
            FactRef(fact_id="f1", version_id="v1", subject="alice", predicate="p", object="x"),
        ),
        source="test",
        event_type=MemoryEventType.FACT_ADDED,
        metadata=MemoryMetadata(pipeline_version="1", created_by=created_by),
    )


@dataclass
class _FakeTimeline:
    entries: dict


# ── constructores / básico ───────────────────────────────────


def test_memory_vacio() -> None:
    m = Memory()
    assert m.timeline.size == 0
    assert m._journal.path == ""


def test_memory_append_sin_journal() -> None:
    m = Memory()
    m.append(_entry("a", 1.0))
    assert m.timeline.size == 1
    assert m._entry_count_since_snapshot == 1


def test_memory_append_con_journal(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    m = Memory(journal_path=path)
    m.append(_entry("a", 1.0))
    j = Journal()
    j.open(path)
    assert j.count == 1
    j.close()
    m.close()


def test_memory_state_at() -> None:
    m = Memory()
    m.append(_entry("a", 1.0))
    m.append(_entry("b", 5.0))
    assert m.state_at(3.0).entry_id == "a"
    assert m.state_at(99.0).entry_id == "b"


def test_memory_append_tras_shutdown_lanza() -> None:
    m = Memory()
    m.shutdown()
    with pytest.raises(RuntimeError):
        m.append(_entry("x"))


def test_memory_append_notifica_subscriber() -> None:
    m = Memory()
    recibidos: list[str] = []
    m.subscribe(lambda e: recibidos.append(e.entry_id))
    m.subscribe(lambda e: recibidos.append(e.entry_id))  # segunda suscripción: _subscribers ya existe
    m.append(_entry("n1", 1.0))
    assert recibidos == ["n1", "n1"]


def test_memory_subscriber_con_error_no_rompe() -> None:
    m = Memory()

    def cb(e: MemoryEntry) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    m.subscribe(cb)
    m.append(_entry("x", 1.0))
    assert m.timeline.size == 1


# ── snapshot / save / load ───────────────────────────────────


def test_memory_snapshot_sin_path_genera_archivo() -> None:
    m = Memory()
    m.append(_entry("a", 1.0))
    chk = m.snapshot(version="v1")
    assert len(chk) == 16
    assert m._entry_count_since_snapshot == 0


def test_memory_snapshot_con_path_y_rotate(tmp_path: object) -> None:
    snap = str(tmp_path / "snap.json")
    jpath = str(tmp_path / "j.log")
    m = Memory(journal_path=jpath, snapshot_path=snap)
    m.append(_entry("a", 1.0))
    chk = m.snapshot()
    assert len(chk) == 16
    assert (tmp_path / "snap.json.journal.bak").exists()


def test_memory_snapshot_sin_journal_no_rota(tmp_path: object) -> None:
    snap = str(tmp_path / "snap.json")
    m = Memory(snapshot_path=snap)
    m.append(_entry("a", 1.0))
    m.snapshot()
    assert not (tmp_path / "snap.json.journal.bak").exists()


def test_memory_save_devuelve_checksum(tmp_path: object) -> None:
    m = Memory()
    m.append(_entry("a", 1.0))
    chk = m.save(str(tmp_path / "s.json"), version="v2")
    assert len(chk) == 16


def test_memory_load_roundtrip(tmp_path: object) -> None:
    path = str(tmp_path / "s.json")
    m = Memory()
    m.append(_entry("a", 1.0, created_by="t1"))
    m.append(_entry("b", 2.0, created_by="t2"))
    m.save(path)
    m2 = Memory.load(path)
    assert m2.timeline.size == 2
    assert m2.timeline.get("a").metadata.created_by == "t1"


def test_memory_load_con_fact_refs(tmp_path: object) -> None:
    path = str(tmp_path / "s.json")
    m = Memory()
    m.append(_entry("a", 1.0))
    m.save(path)
    m2 = Memory.load(path)
    e = m2.timeline.get("a")
    assert e.fact_refs[0].fact_id == "f1"
    assert e.event_type == MemoryEventType.FACT_ADDED


# ── health / readiness / liveness ────────────────────────────


def test_memory_health() -> None:
    m = Memory()
    h = m.health()
    assert h["service"] == "memory"
    assert h["status"] == "ok"
    assert h["journal"] is False
    assert h["encryption"] is False


def test_memory_readiness_sin_journal() -> None:
    m = Memory()
    assert m.readiness()["ready"] is True


def test_memory_readiness_con_journal_inexistente(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    m = Memory(journal_path=path)
    m.close()
    Path(path).unlink()
    assert m.readiness()["ready"] is False


def test_memory_liveness() -> None:
    m = Memory()
    assert m.liveness() == {"service": "memory", "alive": True}


# ── shutdown / close ─────────────────────────────────────────


def test_memory_shutdown_cierra_journal(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    m = Memory(journal_path=path)
    m.append(_entry("a"))
    m.shutdown()
    assert m._shutdown is True
    assert m._journal._file is None


def test_memory_shutdown_sin_journal() -> None:
    m = Memory()
    m.shutdown()
    assert m._shutdown is True


def test_memory_close_cierra_journal(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    m = Memory(journal_path=path)
    m.close()
    assert m._journal._file is None


# ── recuperación ─────────────────────────────────────────────


def test_memory_recover_solo_snapshot(tmp_path: object) -> None:
    snap = str(tmp_path / "s.json")
    m = Memory()
    m.append(_entry("a", 1.0))
    m.save(snap)
    m2 = Memory(snapshot_path=snap)
    assert m2.timeline.size == 1
    assert m2.timeline.get("a").source == "test"


def test_memory_recover_snapshot_inexistente_y_journal(tmp_path: object) -> None:
    jpath = str(tmp_path / "j.log")
    snap = str(tmp_path / "no.json")
    m = Memory(journal_path=jpath)
    m.append(_entry("a", 1.0))
    m.close()
    m2 = Memory(journal_path=jpath, snapshot_path=snap)
    assert m2.timeline.size == 1


def test_memory_recover_replay_solo_nuevos(tmp_path: object) -> None:
    jpath = str(tmp_path / "j.log")
    snap = str(tmp_path / "s.json")
    m = Memory(journal_path=jpath)
    m.append(_entry("a", 1.0))
    m.append(_entry("b", 2.0))
    m.close()
    # snapshot con solo "a" (simula snapshot intermedio)
    tl = _FakeTimeline(entries={"a": _entry("a", 1.0)})
    save_snapshot(tl, snap)
    m2 = Memory(journal_path=jpath, snapshot_path=snap)
    assert m2.timeline.size == 2  # a del snapshot + b del journal


def test_memory_recover_snapshot_corrupto_solo_journal(tmp_path: object) -> None:
    jpath = str(tmp_path / "j.log")
    snap = str(tmp_path / "bad.json")
    Path(snap).write_text("{corrupto")
    m = Memory(journal_path=jpath)
    m.append(_entry("a", 1.0))
    m.close()
    m2 = Memory(journal_path=jpath, snapshot_path=snap)
    assert m2.timeline.size == 1


def test_memory_recover_duplicados_tolerados(tmp_path: object) -> None:
    jpath = str(tmp_path / "j.log")
    snap = str(tmp_path / "s.json")
    m = Memory(journal_path=jpath)
    m.append(_entry("a", 1.0))
    m.close()
    tl = _FakeTimeline(entries={"a": _entry("a", 1.0)})
    save_snapshot(tl, snap)
    m2 = Memory(journal_path=jpath, snapshot_path=snap)
    assert m2.timeline.size == 1


def test_memory_entry_from_data_completo() -> None:
    m = Memory()
    e = m._entry_from_data(
        {
            "entry_id": "x",
            "timestamp": 3.5,
            "fact_refs": [{"fact_id": "f", "version_id": "v", "subject": "s", "predicate": "p", "object": "o"}],
            "source": "src",
            "event_type": "rollback",
            "metadata": {
                "pipeline_version": "pv",
                "fusion_config_hash": "fc",
                "fact_count": 2,
                "confidence_avg": 0.5,
                "created_by": "cb",
            },
            "snapshot": False,
        }
    )
    assert e.entry_id == "x"
    assert e.timestamp == 3.5
    assert e.event_type == MemoryEventType.ROLLBACK
    assert e.metadata.confidence_avg == 0.5
    assert e.metadata.fact_count == 2


def test_memory_entry_from_data_por_defecto() -> None:
    m = Memory()
    e = m._entry_from_data({"entry_id": "y", "timestamp": 1.0})
    assert e.event_type == MemoryEventType.SYSTEM
    assert e.metadata.pipeline_version == ""
    assert e.fact_refs == ()


def test_memory_recover_snapshot_con_entry_sin_key_error(tmp_path: object) -> None:
    """Snapshot con entries duplicados: KeyError se suprime en carga."""
    jpath = str(tmp_path / "j.log")
    snap = str(tmp_path / "s.json")
    m = Memory(journal_path=jpath)
    m.append(_entry("a", 1.0))
    m.close()
    tl = _FakeTimeline(entries={"a": _entry("a", 1.0), "b": _entry("b", 2.0)})
    save_snapshot(tl, snap)
    m2 = Memory(journal_path=jpath, snapshot_path=snap)
    assert m2.timeline.size == 2


def test_memory_load_duplicados_suprimidos(tmp_path: object) -> None:
    """Carga de snapshot con entries con el mismo entry_id: KeyError suprimido."""
    path = str(tmp_path / "s.json")
    tl = _FakeTimeline(entries={"a": _entry("a", 1.0), "b": _entry("a", 2.0)})
    save_snapshot(tl, path)
    m2 = Memory.load(path)
    assert m2.timeline.size == 1
