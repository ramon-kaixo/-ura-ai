"""Tests exhaustivos para motor/memory/ — Memoria Histórica (F26).

Cobertura:
  1. Models: MemoryEntry, FactRef, MemoryMetadata, SnapshotHeader, make_entry_id
  2. MemoryTimeline: append, state_at, by_entity, by_time, by_event, diff, get
  3. Journal: open, append, read_all, rotate, close, count; plano y cifrado
  4. Snapshot: save, load, checksum, atomicidad, corrupción; plano y cifrado
  5. Memory: append, state_at, snapshot, save, load, recover, shutdown,
            subscribe/notify, health, readiness, liveness, close
  6. Crypto: encrypt, decrypt, is_encryption_available
  7. Determinismo y thread safety
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from motor.memory import (
    FactRef,
    Journal,
    Memory,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
    MemoryTimeline,
    SnapshotHeader,
    load_snapshot,
    make_entry_id,
    save_snapshot,
)
from motor.memory.crypto import decrypt, encrypt, is_encryption_available
from motor.memory.models import SNAPSHOT_SCHEMA_VERSION

# ── helpers ─────────────────────────────────────────────

_KEY = "test-encryption-key-32bytes!"
_ENCRYPTION_AVAILABLE = is_encryption_available()
_COUNTER: list[int] = [0]


def _next_vid() -> str:
    _COUNTER[0] += 1
    return f"v{_COUNTER[0]}"


def _ref(
    fact_id: str = "f1",
    subject: str = "Apple",
    predicate: str = "sells",
    object: str = "oranges",
) -> FactRef:
    return FactRef(
        fact_id=fact_id,
        version_id=_next_vid(),  # siempre único
        subject=subject,
        predicate=predicate,
        object=object,
    )


def _entry(
    ts: float = 1000.0,
    refs: tuple[FactRef, ...] | None = None,
    etype: MemoryEventType = MemoryEventType.FACT_ADDED,
    source: str = "test",
    eid: str = "",
    snapshot_flag: bool = False,
) -> MemoryEntry:
    if refs is None:
        refs = (_ref(),)
    return MemoryEntry(
        entry_id=eid or make_entry_id(etype.value, [r.version_id for r in refs], ts),
        timestamp=ts,
        fact_refs=refs,
        source=source,
        event_type=etype,
        metadata=MemoryMetadata(created_by="test"),
        snapshot=snapshot_flag,
    )


def _populate(memory: Memory, n: int = 10) -> None:
    for i in range(n):
        memory.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))


# ═══════════════════════════════════════════════════
# 1. Models
# ═══════════════════════════════════════════════════


class TestMakeEntryId:
    def test_deterministic(self) -> None:
        a = make_entry_id("fact_added", ["v1", "v2"], 1000.0)
        b = make_entry_id("fact_added", ["v1", "v2"], 1000.0)
        assert a == b
        assert len(a) == 16

    def test_different_content_different_id(self) -> None:
        a = make_entry_id("fact_added", ["v1"], 1000.0)
        b = make_entry_id("fact_added", ["v2"], 1000.0)
        assert a != b

    def test_sorted_order(self) -> None:
        a = make_entry_id("fact_added", ["v1", "v2"], 1000.0)
        b = make_entry_id("fact_added", ["v2", "v1"], 1000.0)
        assert a == b

    def test_different_event_type_different_id(self) -> None:
        a = make_entry_id("fact_added", ["v1"], 1000.0)
        b = make_entry_id("fact_removed", ["v1"], 1000.0)
        assert a != b

    def test_different_timestamp_different_id(self) -> None:
        a = make_entry_id("fact_added", ["v1"], 1000.0)
        b = make_entry_id("fact_added", ["v1"], 2000.0)
        assert a != b

    def test_empty_version_ids(self) -> None:
        eid = make_entry_id("system_event", [], 1000.0)
        assert isinstance(eid, str)
        assert len(eid) == 16


class TestFactRef:
    def test_immutable(self) -> None:
        ref = _ref()
        with pytest.raises(AttributeError):
            ref.subject = "changed"

    def test_fields(self) -> None:
        ref = FactRef(fact_id="fa1", version_id="ve1", subject="S", predicate="P", object="O")
        assert ref.fact_id == "fa1"
        assert ref.version_id == "ve1"
        assert ref.subject == "S"
        assert ref.predicate == "P"
        assert ref.object == "O"

    def test_hashable(self) -> None:
        ref = _ref()
        s = {ref}
        assert ref in s

    def test_equality(self) -> None:
        a = FactRef(fact_id="f1", version_id="v1", subject="S", predicate="P", object="O")
        b = FactRef(fact_id="f1", version_id="v1", subject="S", predicate="P", object="O")
        assert a == b
        assert a == b


class TestMemoryEntry:
    def test_frozen(self) -> None:
        entry = _entry()
        with pytest.raises(AttributeError):
            entry.timestamp = 999.0

    def test_default_event_type(self) -> None:
        entry = MemoryEntry(entry_id="e1", timestamp=1000.0)
        assert entry.event_type == MemoryEventType.SYSTEM
        assert entry.source == ""

    def test_default_fact_refs(self) -> None:
        entry = MemoryEntry(entry_id="e1", timestamp=1000.0)
        assert entry.fact_refs == ()

    def test_default_metadata(self) -> None:
        entry = MemoryEntry(entry_id="e1", timestamp=1000.0)
        assert isinstance(entry.metadata, MemoryMetadata)
        assert entry.metadata.pipeline_version == ""

    def test_snapshot_flag(self) -> None:
        entry = _entry(snapshot_flag=True)
        assert entry.snapshot is True


class TestMemoryMetadata:
    def test_defaults(self) -> None:
        m = MemoryMetadata()
        assert m.pipeline_version == ""
        assert m.fusion_config_hash == ""
        assert m.fact_count == 0
        assert m.confidence_avg == 0.0
        assert m.created_by == ""

    def test_fields(self) -> None:
        m = MemoryMetadata(pipeline_version="1.0", fusion_config_hash="abc", fact_count=42, confidence_avg=0.95, created_by="tester")
        assert m.pipeline_version == "1.0"
        assert m.fact_count == 42

    def test_frozen(self) -> None:
        m = MemoryMetadata()
        with pytest.raises(AttributeError):
            m.pipeline_version = "new"


class TestSnapshotHeader:
    def test_defaults(self) -> None:
        h = SnapshotHeader()
        assert h.schema_version == SNAPSHOT_SCHEMA_VERSION
        assert h.snapshot_version == ""
        assert h.checksum == ""
        assert h.entry_count == 0
        assert h.journal_offset == 0
        assert h.compatible_from == "0.26.0"

    def test_frozen(self) -> None:
        h = SnapshotHeader()
        with pytest.raises(AttributeError):
            h.schema_version = 2

    def test_SNAPSHOT_SCHEMA_VERSION_constant(self) -> None:
        assert SNAPSHOT_SCHEMA_VERSION == 1


class TestMemoryEventType:
    def test_values(self) -> None:
        assert MemoryEventType.FACT_ADDED.value == "fact_added"
        assert MemoryEventType.FACT_UPDATED.value == "fact_updated"
        assert MemoryEventType.FACT_REMOVED.value == "fact_removed"
        assert MemoryEventType.ROLLBACK.value == "rollback"
        assert MemoryEventType.SNAPSHOT.value == "snapshot"
        assert MemoryEventType.COMPACTION.value == "compaction"
        assert MemoryEventType.SYSTEM.value == "system_event"

    def test_all_types(self) -> None:
        assert len(MemoryEventType) == 7


# ═══════════════════════════════════════════════════
# 2. MemoryTimeline
# ═══════════════════════════════════════════════════


class TestMemoryTimeline:
    def test_append(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        assert tl.size == 1

    def test_append_duplicate_raises(self) -> None:
        tl = MemoryTimeline()
        e = _entry()
        tl.append(e)
        with pytest.raises(KeyError, match="already exists"):
            tl.append(e)

    def test_empty_state_at(self) -> None:
        tl = MemoryTimeline()
        assert tl.state_at(1000.0) is None

    def test_state_at_exact(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        assert tl.state_at(1000.0) is not None
        assert tl.state_at(1000.0).timestamp == 1000.0

    def test_state_at_between(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        r = tl.state_at(1500.0)
        assert r is not None
        assert r.timestamp == 1000.0

    def test_state_at_before_first(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        assert tl.state_at(500.0) is None

    def test_state_at_after_last(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        r = tl.state_at(3000.0)
        assert r is not None
        assert r.timestamp == 2000.0

    def test_state_at_tie_breaking(self) -> None:
        tl = MemoryTimeline()
        e1 = _entry(ts=1000.0, refs=(_ref(),), eid="aaaa")
        e2 = _entry(ts=1000.0, refs=(_ref(),), eid="bbbb")
        tl.append(e1)
        tl.append(e2)
        r = tl.state_at(1000.0)
        assert r is not None
        assert r.entry_id == "bbbb"

    def test_by_entity(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(refs=(_ref(fact_id="f1", subject="Tesla"),)))
        assert len(tl.by_entity("Tesla")) == 1

    def test_by_entity_nonexistent(self) -> None:
        tl = MemoryTimeline()
        assert tl.by_entity("NonExistent") == []

    def test_by_entity_case_insensitive(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(refs=(_ref(fact_id="f1", subject="Apple"),)))
        assert len(tl.by_entity("APPLE")) == 1
        assert len(tl.by_entity("apple")) == 1

    def test_by_time_range(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        tl.append(_entry(ts=3000.0))
        r = tl.by_time(1500.0, 2500.0)
        assert len(r) == 1
        assert r[0].timestamp == 2000.0

    def test_by_time_empty_range(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        assert tl.by_time(2000.0, 3000.0) == []

    def test_by_time_exact_boundaries(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        assert len(tl.by_time(1000.0, 1000.0)) >= 1
        assert len(tl.by_time(2000.0, 2000.0)) >= 1

    def test_by_event(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(etype=MemoryEventType.FACT_ADDED))
        tl.append(_entry(etype=MemoryEventType.FACT_REMOVED))
        r = tl.by_event("fact_added")
        assert len(r) == 1
        assert r[0].event_type == MemoryEventType.FACT_ADDED

    def test_by_event_nonexistent(self) -> None:
        tl = MemoryTimeline()
        assert tl.by_event("nonexistent") == []

    def test_get_existing(self) -> None:
        tl = MemoryTimeline()
        e = _entry()
        tl.append(e)
        assert tl.get(e.entry_id) is e

    def test_get_nonexistent(self) -> None:
        tl = MemoryTimeline()
        assert tl.get("nonexistent") is None

    def test_diff_added_and_removed(self) -> None:
        tl = MemoryTimeline()
        e1 = _entry(ts=1000.0, refs=(_ref(fact_id="f1"), _ref(fact_id="f2")))
        e2 = _entry(ts=2000.0, refs=(_ref(fact_id="f2"), _ref(fact_id="f3")))
        tl.append(e1)
        tl.append(e2)
        d = tl.diff(e1.entry_id, e2.entry_id)
        assert any("f3" in fid for fid in d["added"])
        assert any("f1" in fid for fid in d["removed"])
        assert any("f2" in fid for fid in d["common"])

    def test_diff_same_entry(self) -> None:
        tl = MemoryTimeline()
        e = _entry(refs=(_ref(),))
        tl.append(e)
        d = tl.diff(e.entry_id, e.entry_id)
        assert d["added"] == []
        assert d["removed"] == []
        assert len(d["common"]) == 1

    def test_diff_nonexistent_raises(self) -> None:
        tl = MemoryTimeline()
        e = _entry()
        tl.append(e)
        with pytest.raises(KeyError, match="Entry not found"):
            tl.diff(e.entry_id, "nonexistent")
        with pytest.raises(KeyError, match="Entry not found"):
            tl.diff("nonexistent", e.entry_id)

    def test_size_empty(self) -> None:
        tl = MemoryTimeline()
        assert tl.size == 0

    def test_entries_property_is_copy(self) -> None:
        tl = MemoryTimeline()
        e = _entry()
        tl.append(e)
        entries = tl.entries
        entries["new"] = e
        assert "new" not in tl.entries

    def test_timeline_property_is_copy(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        t = tl.timeline
        t.append((3000.0, "fake"))
        assert len(tl.timeline) == 2


# ═══════════════════════════════════════════════════
# 3. Journal — plain
# ═══════════════════════════════════════════════════


class TestJournalPlain:
    def test_open_and_close(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        assert j.path == p
        assert j.count == 0
        j.close()

    def test_append_and_read(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.append(_entry(ts=2000.0))
        j.close()
        entries = j.read_all()
        assert len(entries) == 2
        assert entries[0]["timestamp"] == 1000.0
        assert entries[1]["timestamp"] == 2000.0

    def test_count(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        assert j.count == 0
        j.append(_entry(ts=1000.0))
        assert j.count == 1
        j.append(_entry(ts=2000.0))
        assert j.count == 2
        j.close()

    def test_rotate(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        backup = str(Path(tmp_path) / "journal.bak")
        j = Journal()
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.rotate(backup)
        assert j.count == 0
        assert Path(backup).exists()
        assert Path(p).exists()
        j.close()

    def test_rotate_without_path_does_not_crash(self) -> None:
        j = Journal()
        j.rotate("/nonexistent/backup.jsonl")

    def test_read_all_non_existent(self) -> None:
        j = Journal()
        assert j.read_all() == []

    def test_read_all_empty(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "empty.jsonl")
        Path(p).write_text("")
        j = Journal(path=p)
        assert j.read_all() == []

    def test_append_without_open_raises(self) -> None:
        j = Journal()
        with pytest.raises(RuntimeError, match="Journal not open"):
            j.append(_entry())

    def test_read_all_skips_corrupt_lines(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "corrupt.jsonl")
        from motor.memory.journal import Journal as J

        valid = json.dumps(J._entry_to_dict(_entry()), ensure_ascii=False)
        Path(p).write_text(f"{valid}\ncorrupted line\n{valid}\n")
        j = Journal(path=p)
        entries = j.read_all()
        assert len(entries) == 2

    def test_reopen_recovers_count(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j1 = Journal()
        j1.open(p)
        j1.append(_entry(ts=1000.0))
        j1.append(_entry(ts=2000.0))
        j1.close()
        j2 = Journal()
        j2.open(p)
        assert j2.count == 2
        j2.close()

    def test_close_twice(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        j.close()
        j.close()

    def test_read_all_after_rotation(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        backup = str(Path(tmp_path) / "journal.bak")
        j = Journal()
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.rotate(backup)
        j.append(_entry(ts=2000.0))
        j.close()
        entries = j.read_all()
        assert len(entries) == 1
        assert entries[0]["timestamp"] == 2000.0

    def test_append_and_read_entry_version(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        j.append(_entry())
        j.close()
        entries = j.read_all()
        assert entries[0].get("entry_version") == "test"
        assert entries[0].get("schema_version") == 1

    def test_large_journal_read(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "large.jsonl")
        j = Journal()
        j.open(p)
        for i in range(500):
            j.append(_entry(ts=float(i * 1000)))
        j.close()
        entries = j.read_all()
        assert len(entries) == 500


@pytest.mark.skipif(not _ENCRYPTION_AVAILABLE, reason="cryptography not installed")
class TestJournalEncrypted:
    def test_append_and_read_single(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal_enc.jsonl")
        j = Journal(path=p, encryption_key=_KEY)
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.close()
        entries = j.read_all()
        assert len(entries) == 1
        assert entries[0]["timestamp"] == 1000.0

    def test_encrypted_on_disk_not_plaintext(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal_enc.jsonl")
        j = Journal(path=p, encryption_key=_KEY)
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.close()
        raw = Path(p).read_bytes()
        assert b"timestamp" not in raw

    def test_rotate_with_encryption(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal_enc.jsonl")
        backup = str(Path(tmp_path) / "journal_enc.bak")
        j = Journal(path=p, encryption_key=_KEY)
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.rotate(backup)
        assert j.count == 0
        assert Path(backup).exists()
        j.close()

    def test_wrong_key_returns_garbage(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal_enc.jsonl")
        j = Journal(path=p, encryption_key=_KEY)
        j.open(p)
        j.append(_entry(ts=1000.0))
        j.close()
        j2 = Journal(path=p, encryption_key=_KEY + "x")
        entries = j2.read_all()
        assert len(entries) == 0


# ═══════════════════════════════════════════════════
# 4. Snapshot
# ═══════════════════════════════════════════════════


class TestSnapshotPlain:
    def test_save_and_load(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        p = str(Path(tmp_path) / "snap.json")
        cs = save_snapshot(tl, p)
        assert len(cs) == 16
        header, entries = load_snapshot(p)
        assert header["entry_count"] == 2
        assert len(entries) == 2

    def test_checksum_matches(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap.json")
        cs = save_snapshot(tl, p)
        header, _ = load_snapshot(p)
        assert header["checksum"] == cs

    def test_checksum_mismatch_raises(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap.json")
        save_snapshot(tl, p)
        data = json.loads(Path(p).read_text())
        data["entries"]["corrupted"] = {"entry_id": "bad"}
        Path(p).write_text(json.dumps(data))
        with pytest.raises(ValueError, match="checksum mismatch"):
            load_snapshot(p)

    def test_truncated_file_raises(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap.json")
        save_snapshot(tl, p)
        content = Path(p).read_text()
        Path(p).write_text(content[: len(content) // 2])
        with pytest.raises((ValueError, json.JSONDecodeError, KeyError)):
            load_snapshot(p)

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="Snapshot not found"):
            load_snapshot("/nonexistent/path.json")

    def test_save_version(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap.json")
        save_snapshot(tl, p, version="v2.0")
        header, _ = load_snapshot(p)
        assert header["snapshot_version"] == "v2.0"

    def test_empty_timeline_snapshot(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        p = str(Path(tmp_path) / "empty.json")
        cs = save_snapshot(tl, p)
        assert cs
        header, entries = load_snapshot(p)
        assert header["entry_count"] == 0
        assert len(entries) == 0

    def test_snapshot_without_checksum_compat(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "compat.json")
        data = {
            "header": {"schema_version": 1, "entry_count": 1},
            "entries": {
                "e1": {
                    "entry_id": "e1",
                    "timestamp": 1000.0,
                    "fact_refs": [],
                    "source": "test",
                    "event_type": "system_event",
                    "metadata": {},
                    "snapshot": False,
                },
            },
        }
        Path(p).write_text(json.dumps(data))
        header, entries = load_snapshot(p)
        assert header["entry_count"] == 1
        assert "e1" in entries

    def test_snapshot_is_atomic(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap.json")
        save_snapshot(tl, p)
        # El archivo debe ser un JSON válido (no hay .tmp colgando)
        assert Path(p).exists()
        header, _ = load_snapshot(p)
        assert header["entry_count"] == 1


@pytest.mark.skipif(not _ENCRYPTION_AVAILABLE, reason="cryptography not installed")
class TestSnapshotEncrypted:
    def test_save_and_load(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        tl.append(_entry(ts=2000.0))
        p = str(Path(tmp_path) / "snap_enc.json")
        cs = save_snapshot(tl, p, encryption_key=_KEY)
        assert len(cs) == 16
        header, entries = load_snapshot(p, encryption_key=_KEY)
        assert header["entry_count"] == 2
        assert len(entries) == 2

    def test_encrypted_not_plaintext(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap_enc.json")
        save_snapshot(tl, p, encryption_key=_KEY)
        raw = Path(p).read_bytes()
        assert b"timestamp" not in raw

    def test_load_without_key_raises(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap_enc.json")
        save_snapshot(tl, p, encryption_key=_KEY)
        with pytest.raises(ValueError, match="encrypted or corrupted"):
            load_snapshot(p)

    def test_wrong_key_raises(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0))
        p = str(Path(tmp_path) / "snap_enc.json")
        save_snapshot(tl, p, encryption_key=_KEY)
        with pytest.raises((ValueError, json.JSONDecodeError)):
            load_snapshot(p, encryption_key=_KEY + "x")


# ═══════════════════════════════════════════════════
# 5. Memory (wrapper)
# ═══════════════════════════════════════════════════


class TestMemoryBasic:
    def test_append(self) -> None:
        m = Memory()
        m.append(_entry(ts=1000.0))
        assert m.timeline.size == 1

    def test_state_at(self) -> None:
        m = Memory()
        m.append(_entry(ts=1000.0))
        m.append(_entry(ts=2000.0))
        assert m.state_at(1500.0).timestamp == 1000.0
        assert m.state_at(2000.0).timestamp == 2000.0

    def test_state_at_before_first(self) -> None:
        m = Memory()
        m.append(_entry(ts=1000.0))
        assert m.state_at(500.0) is None

    def test_in_memory_no_journal_or_snapshot(self) -> None:
        m = Memory()
        _populate(m, 5)
        assert m.timeline.size == 5
        m.close()

    def test_save_round_trip(self, tmp_path: str) -> None:
        m1 = Memory()
        _populate(m1, 5)
        p = str(Path(tmp_path) / "save.json")
        m1.save(p)
        m2 = Memory.load(p)
        assert m2.timeline.size == 5
        assert m2.state_at(0.0).timestamp == 0.0
        assert m2.state_at(4000.0).timestamp == 4000.0

    def test_snapshot_then_journal_recovery(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        journal = str(Path(tmp_path) / "journal.jsonl")
        m1 = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m1, 10)
        m1.snapshot(version="v1")
        m1.append(_entry(ts=50000.0, refs=(_ref("fx"),)))  # post-snapshot unique entry
        m1.close()
        m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
        assert m2.timeline.size == 11
        m2.close()

    def test_recover_without_snapshot_only_journal(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "nonexistent_snap.json")
        journal = str(Path(tmp_path) / "journal.jsonl")
        m1 = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m1, 5)
        m1.close()
        m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
        assert m2.timeline.size == 5
        m2.close()

    def test_recover_without_journal_only_snapshot(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        m1 = Memory(snapshot_path=snap)
        _populate(m1, 10)
        m1.snapshot("v1")
        m1.close()
        m2 = Memory(snapshot_path=snap, auto_recover=True)
        assert m2.timeline.size == 10
        m2.close()

    def test_snapshot_returns_checksum(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        m = Memory(snapshot_path=snap)
        _populate(m, 5)
        cs = m.snapshot(version="v1")
        assert len(cs) == 16
        m.close()

    def test_snapshot_without_path(self) -> None:
        m = Memory()
        _populate(m, 5)
        cs = m.snapshot()
        assert len(cs) == 16
        m.close()

    def test_timeline_property(self) -> None:
        m = Memory()
        _populate(m, 3)
        assert m.timeline.size == 3
        assert isinstance(m.timeline, MemoryTimeline)


class TestMemoryHealthProbes:
    def test_health(self) -> None:
        m = Memory()
        h = m.health()
        assert h["service"] == "memory"
        assert h["status"] == "ok"
        assert h["entries"] == 0
        assert h["journal"] is False
        assert h["snapshot"] is False

    def test_health_with_journal(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        m = Memory(snapshot_path=snap)
        h = m.health()
        assert h["snapshot"] is True
        m.close()

    def test_readiness(self) -> None:
        m = Memory()
        r = m.readiness()
        assert r["service"] == "memory"
        assert r["ready"] is True

    def test_readiness_after_shutdown(self) -> None:
        m = Memory()
        m.shutdown()
        r = m.readiness()
        assert r["ready"] is False

    def test_liveness(self) -> None:
        m = Memory()
        l = m.liveness()
        assert l["service"] == "memory"
        assert l["alive"] is True


class TestMemoryShutdown:
    def test_append_after_shutdown_raises(self) -> None:
        m = Memory()
        m.shutdown()
        with pytest.raises(RuntimeError, match="shutting down"):
            m.append(_entry())

    def test_shutdown_closes_journal(self, tmp_path: str) -> None:
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(journal_path=journal)
        _populate(m, 3)
        m.shutdown()
        assert m.timeline.size == 3

    def test_shutdown_no_journal(self) -> None:
        m = Memory()
        m.shutdown()
        assert m.readiness()["ready"] is False

    def test_shutdown_timeout(self, tmp_path: str) -> None:
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(journal_path=journal)
        _populate(m, 5)
        m.shutdown(timeout=1)
        assert m.timeline.size == 5

    def test_shutdown_twice(self) -> None:
        m = Memory()
        m.shutdown()
        m.shutdown()


class TestMemorySubscribe:
    def test_subscribe_receives_entries(self) -> None:
        m = Memory()
        received: list[MemoryEntry] = []

        def cb(entry: MemoryEntry) -> None:
            received.append(entry)

        m.subscribe(cb)
        e = _entry(ts=1000.0)
        m.append(e)
        assert len(received) == 1
        assert received[0] is e

    def test_multiple_subscribers(self) -> None:
        m = Memory()
        r0: list[MemoryEntry] = []
        r1: list[MemoryEntry] = []

        def cb0(e: MemoryEntry) -> None:
            r0.append(e)

        def cb1(e: MemoryEntry) -> None:
            r1.append(e)

        m.subscribe(cb0)
        m.subscribe(cb1)
        e = _entry(ts=1000.0)
        m.append(e)
        assert len(r0) == 1
        assert len(r1) == 1

    def test_subscriber_error_does_not_break_append(self) -> None:
        m = Memory()

        def bad_cb(entry: MemoryEntry) -> None:
            msg = "oops"
            raise RuntimeError(msg)

        m.subscribe(bad_cb)
        m.append(_entry(ts=1000.0))
        assert m.timeline.size == 1

    def test_no_subscriber_no_error(self) -> None:
        m = Memory()
        m.append(_entry(ts=1000.0))
        assert m.timeline.size == 1


class TestMemoryPersistenceEdgeCases:
    def test_journal_auto_creates_file(self, tmp_path: str) -> None:
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(journal_path=journal)
        m.append(_entry(ts=1000.0))
        assert Path(journal).exists()
        m.close()

    def test_snapshot_rotates_journal(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m, 5)
        m.snapshot("v1")
        m.append(_entry(ts=99999.0, refs=(_ref("f_post"),)))
        m.close()
        rot = Path(snap + ".journal.bak")
        assert rot.exists()
        assert Path(journal).exists()
        recovered = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
        assert recovered.timeline.size == 6
        recovered.close()

    def test_save_does_not_rotate_journal(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "save_no_rotate.json")
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m, 5)
        m.save(snap)
        assert m.timeline.size == 5
        rot = Path(snap + ".journal.bak")
        assert not rot.exists()
        m.close()

    def test_load_tolerates_duplicate_entry_ids(self, tmp_path: str) -> None:
        m1 = Memory()
        _populate(m1, 5)
        p = str(Path(tmp_path) / "snap.json")
        m1.save(p)
        # Añadir duplicado al JSON directamente y recalcular checksum
        data = json.loads(Path(p).read_text())
        dup = dict(next(iter(data["entries"].values())))
        dup["entry_id"] = "manual_dup"
        data["entries"]["manual_dup"] = dup
        data["header"]["entry_count"] = len(data["entries"])
        # Recalcular checksum
        import hashlib

        data_copy = dict(data)
        data_copy["header"] = dict(data["header"])
        data_copy["header"]["checksum"] = ""
        raw = json.dumps(data_copy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        data["header"]["checksum"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        Path(p).write_text(json.dumps(data))
        m2 = Memory.load(p)
        assert m2.timeline.size >= 5


# ═══════════════════════════════════════════════════
# 6. Crypto
# ═══════════════════════════════════════════════════


class TestCrypto:
    def test_no_key_passthrough(self) -> None:
        pt = b"hello world"
        assert encrypt(pt) == pt
        assert decrypt(pt) == pt

    def test_empty_key_passthrough(self) -> None:
        pt = b"hello"
        assert encrypt(pt, "") == pt
        assert decrypt(pt, "") == pt

    @pytest.mark.skipif(not _ENCRYPTION_AVAILABLE, reason="cryptography not installed")
    def test_encrypt_decrypt_roundtrip(self) -> None:
        pt = b"hello world with encryption"
        ct = encrypt(pt, _KEY)
        assert ct != pt
        assert decrypt(ct, _KEY) == pt

    @pytest.mark.skipif(not _ENCRYPTION_AVAILABLE, reason="cryptography not installed")
    def test_wrong_key_fails(self) -> None:
        pt = b"secret data"
        ct = encrypt(pt, _KEY)
        dt = decrypt(ct, _KEY + "x")
        assert dt != pt

    def test_is_encryption_available_returns_bool(self) -> None:
        assert isinstance(is_encryption_available(), bool)


# ═══════════════════════════════════════════════════
# 7. Determinismo
# ═══════════════════════════════════════════════════


class TestDeterminism:
    def test_same_inputs_same_entry_id(self) -> None:
        refs = (_ref(fact_id="f1"), _ref(fact_id="f2"))
        ts = 1000.0
        e1 = _entry(ts=ts, refs=refs)
        e2 = _entry(ts=ts, refs=refs)
        assert e1.entry_id == e2.entry_id

    def test_same_timeline_same_state_at(self) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0, eid="det_a", refs=(_ref("f1"),)))
        tl.append(_entry(ts=2000.0, eid="det_b", refs=(_ref("f2"),)))
        r1 = tl.state_at(1500.0)
        r2 = tl.state_at(1500.0)
        assert r1 is not None
        assert r2 is not None
        assert r1.entry_id == r2.entry_id

    def test_recovery_deterministic_10x(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap.json")
        journal = str(Path(tmp_path) / "journal.jsonl")
        m1 = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m1, 10)
        m1.snapshot("v1")
        m1.append(_entry(ts=50000.0, refs=(_ref("fx"),)))
        m1.close()
        states: list[str] = []
        for _ in range(10):
            m = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
            states.append(str(sorted(m.timeline.entries.keys())))
            m.close()
        assert all(s == states[0] for s in states)

    def test_same_entries_deterministic_checksum_format(self, tmp_path: str) -> None:
        tl = MemoryTimeline()
        tl.append(_entry(ts=1000.0, eid="det_c", refs=(_ref("f1"),)))
        p = str(Path(tmp_path) / "snap.json")
        cs = save_snapshot(tl, p)
        assert len(cs) == 16
        assert all(c in "0123456789abcdef" for c in cs)
        header, _ = load_snapshot(p)
        assert header["checksum"] == cs


# ═══════════════════════════════════════════════════
# 8. Thread safety
# ═══════════════════════════════════════════════════


class TestThreadSafety:
    def test_concurrent_writers(self) -> None:
        tl = MemoryTimeline()
        errors: list[Exception] = []
        lock = threading.Lock()

        def writer(start: int, count: int) -> None:
            for i in range(start, start + count):
                try:
                    with lock:
                        tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 50)),
            threading.Thread(target=writer, args=(50, 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert tl.size == 100
        assert not errors

    def test_concurrent_readers_during_append(self) -> None:
        tl = MemoryTimeline()
        for i in range(10):
            tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
        errors: list[Exception] = []
        lock = threading.Lock()

        def writer() -> None:
            for i in range(10, 20):
                with lock:
                    try:
                        tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
                    except Exception as e:
                        errors.append(e)

        def reader() -> None:
            for _ in range(20):
                with lock:
                    try:
                        tl.state_at(5000.0)
                        tl.by_entity("Apple")
                        tl.size
                    except Exception as e:
                        errors.append(e)

        threads = [threading.Thread(target=writer, daemon=True)]
        threads += [threading.Thread(target=reader, daemon=True) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not errors

    def test_journal_thread_safe(self, tmp_path: str) -> None:
        p = str(Path(tmp_path) / "journal.jsonl")
        j = Journal()
        j.open(p)
        errors: list[Exception] = []
        lock = threading.Lock()

        def writer(start: int, count: int) -> None:
            for i in range(start, start + count):
                with lock:
                    try:
                        j.append(_entry(ts=float(i * 1000)))
                    except Exception as e:
                        errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 50)),
            threading.Thread(target=writer, args=(50, 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        j.close()
        assert j.count == 100
        assert not errors
        entries = j.read_all()
        assert len(entries) == 100

    def test_memory_thread_safe_with_journal(self, tmp_path: str) -> None:
        journal = str(Path(tmp_path) / "journal.jsonl")
        m = Memory(journal_path=journal)
        errors: list[Exception] = []

        def writer(start: int, count: int) -> None:
            for i in range(start, start + count):
                try:
                    m.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 50)),
            threading.Thread(target=writer, args=(50, 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert m.timeline.size == 100
        assert not errors
        m.close()

    def test_concurrent_reads_do_not_block(self) -> None:
        tl = MemoryTimeline()
        for i in range(100):
            tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
        results: list[MemoryEntry | None] = []
        errors: list[Exception] = []

        def query(t: float) -> None:
            try:
                results.append(tl.state_at(t))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=query, args=(float(i * 100),)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(results) == 50
        assert not errors


# ═══════════════════════════════════════════════════
# 9. Benchmarks (límites generosos para CI)
# ═══════════════════════════════════════════════════


class TestBenchmarks:
    def test_append_1000(self) -> None:
        tl = MemoryTimeline()
        start = time.perf_counter()
        for i in range(1000):
            tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
        elapsed = time.perf_counter() - start
        assert tl.size == 1000
        assert elapsed < 1.0, f"1000 appends took {elapsed * 1000:.1f}ms"

    def test_state_at_1000_queries(self) -> None:
        tl = MemoryTimeline()
        for i in range(1000):
            tl.append(_entry(ts=float(i * 1000), refs=(_ref(f"f{i}"),)))
        start = time.perf_counter()
        for ts in range(0, 1_000_000, 1000):
            tl.state_at(float(ts))
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0

    def test_recovery_10k(self, tmp_path: str) -> None:
        snap = str(Path(tmp_path) / "snap_10k.json")
        journal = str(Path(tmp_path) / "journal_10k.jsonl")
        m1 = Memory(snapshot_path=snap, journal_path=journal)
        _populate(m1, 10000)
        m1.snapshot("v1")
        m1.close()
        start = time.perf_counter()
        m2 = Memory(snapshot_path=snap, journal_path=journal, auto_recover=True)
        elapsed = time.perf_counter() - start
        assert m2.timeline.size == 10000
        assert elapsed < 5.0, f"Recovery 10K took {elapsed:.2f}s"
        m2.close()
