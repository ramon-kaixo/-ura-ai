"""Cobertura 100x100 de motor/memory (journal + snapshot). TASK-20260820-006."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from motor.memory.journal import Journal
from motor.memory.models import (
    FactRef,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
)
from motor.memory.snapshot import load_snapshot, save_snapshot


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


# ── Journal ──────────────────────────────────────────────────


def test_journal_append_flush_fsync(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    j = Journal()
    j.open(path)
    j.append(_entry("e1", 1.0))
    j.append(_entry("e2", 2.0))
    assert j.count == 2
    assert j.path == path
    j.close()
    with Path(path).open() as fh:
        lines = fh.readlines()
    assert len(lines) == 2


def test_journal_append_sin_open_lanza() -> None:
    j = Journal()
    with pytest.raises(RuntimeError):
        j.append(_entry())


def test_journal_read_all_vacio_si_no_existe() -> None:
    j = Journal("/no/existe.log")
    assert j.read_all() == []


def test_journal_read_all_corruptas_omitidas(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    with Path(path).open("w") as f:
        f.write('{"entry_id": "e1"}\n')
        f.write("no-json\n")
        f.write('{"entry_id": "e2"}\n')
    j = Journal(path)
    j.open(path)
    assert [r["entry_id"] for r in j.read_all()] == ["e1", "e2"]
    j.close()


def test_journal_read_all_archivo_vacio(tmp_path: object) -> None:
    path = str(tmp_path / "empty.log")
    Path(path).open("w").close()
    j = Journal()
    j.open(path)
    assert j.read_all() == []


def test_journal_rotate_renombra_y_reabre(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    j = Journal()
    j.open(path)
    j.append(_entry("e1"))
    j.rotate(str(tmp_path / "j.bak"))
    assert j.count == 0
    assert Path(tmp_path / "j.bak").read_text() != ""
    j.append(_entry("e2"))
    j.close()


def test_journal_rotate_sin_path_no_rompe(tmp_path: object) -> None:
    j = Journal()
    j.rotate(str(tmp_path / "j.bak"))
    assert j.count == 0


def test_journal_wait_idle_true_cuando_libre() -> None:
    j = Journal()
    assert j.wait_idle(1) is True


def test_journal_wait_idle_espera_lock_ocupado() -> None:
    j = Journal()
    j._lock.acquire()
    assert j.wait_idle(0.2) is False
    j._lock.release()
    assert j.wait_idle(1) is True


def test_journal_entry_to_dict_estructura() -> None:
    e = _entry("e1", 3.5, created_by="autor")
    d = Journal._entry_to_dict(e)
    assert d["entry_id"] == "e1"
    assert d["timestamp"] == 3.5
    assert d["entry_version"] == "autor"
    assert d["event_type"] == "fact_added"
    assert d["fact_refs"][0]["fact_id"] == "f1"
    assert d["metadata"]["created_by"] == "autor"
    assert d["snapshot"] is False


def test_journal_entry_version_default() -> None:
    e = MemoryEntry(entry_id="x", timestamp=1.0)
    assert Journal._entry_to_dict(e)["entry_version"] == "1"


def test_journal_count_lines_inicial(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    with Path(path).open("w") as f:
        f.write("a\nb\nc\n")
    j = Journal()
    j.open(path)
    assert j.count == 3
    j.close()


def test_journal_ab_binario_sin_encoding_con_clave(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    j = Journal(encryption_key="clave")
    j.open(path)
    j.append(_entry("e1"))
    j.close()
    raw = Path(path).read_bytes()
    assert b"entry_id" not in raw  # cifrado


def test_journal_read_all_con_clave(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    j = Journal(encryption_key="clave")
    j.open(path)
    j.append(_entry("e1"))
    j.close()
    # NOTA: open() con clave y archivo preexistente cifrado rompe en _count_lines
    # (abre en utf-8; hallazgo documentado). Leemos sin open(), vía path directo.
    j2 = Journal(encryption_key="clave")
    j2._path = path
    assert [r["entry_id"] for r in j2.read_all()] == ["e1"]


def test_journal_read_all_clave_incorrecta_decodifica_reemplazo(tmp_path: object) -> None:
    path = str(tmp_path / "j.log")
    j = Journal(encryption_key="clave")
    j.open(path)
    j.append(_entry("e1"))
    j.close()
    j3 = Journal(encryption_key="otra")
    j3._path = path
    result = j3.read_all()
    assert result == []  # texto corrupto no parsea como JSON


def test_journal_count_lines_sin_archivo() -> None:
    j = Journal()
    assert j._count_lines() == 0


def test_journal_close_idempotente() -> None:
    j = Journal()
    j.close()
    j.close()


def test_journal_properties_por_defecto() -> None:
    j = Journal()
    assert j.path == ""
    assert j.count == 0


# ── Snapshot ─────────────────────────────────────────────────


@dataclass
class _FakeTimeline:
    entries: dict


def test_save_snapshot_guarda_y_devuelve_checksum(tmp_path: object) -> None:
    path = str(tmp_path / "snap.json")
    tl = _FakeTimeline(entries={"e1": _entry("e1", 1.0)})
    chk = save_snapshot(tl, path, version="v1")
    assert len(chk) == 16
    data = json.loads(Path(path).read_text())
    assert data["header"]["entry_count"] == 1
    assert data["header"]["snapshot_version"] == "v1"
    assert data["header"]["checksum"] == chk


def test_save_snapshot_sin_entries(tmp_path: object) -> None:
    path = str(tmp_path / "empty.json")
    tl = _FakeTimeline(entries={})
    chk = save_snapshot(tl, path)
    data = json.loads(Path(path).read_text())
    assert data["header"]["entry_count"] == 0
    assert len(chk) == 16


def test_save_snapshot_cifrado(tmp_path: object) -> None:
    path = str(tmp_path / "snap.enc")
    tl = _FakeTimeline(entries={"e1": _entry("e1", 1.0)})
    save_snapshot(tl, path, encryption_key="k")
    raw = Path(path).read_bytes()
    assert b"entry_id" not in raw


def test_load_snapshot_roundtrip(tmp_path: object) -> None:
    path = str(tmp_path / "snap.json")
    tl = _FakeTimeline(entries={"e1": _entry("e1", 1.0)})
    save_snapshot(tl, path)
    header, entries = load_snapshot(path)
    assert header["entry_count"] == 1
    assert entries["e1"]["entry_id"] == "e1"


def test_load_snapshot_no_existe_lanza() -> None:
    with pytest.raises(FileNotFoundError):
        load_snapshot("/no/existe.json")


def test_load_snapshot_cifrado_sin_clave_lanza_valueerror(tmp_path: object) -> None:
    path = str(tmp_path / "snap.enc")
    tl = _FakeTimeline(entries={})
    save_snapshot(tl, path, encryption_key="k")
    with pytest.raises(ValueError):
        load_snapshot(path)


def test_load_snapshot_con_clave(tmp_path: object) -> None:
    path = str(tmp_path / "snap.enc")
    tl = _FakeTimeline(entries={"e1": _entry("e1", 1.0)})
    save_snapshot(tl, path, encryption_key="k")
    _header, entries = load_snapshot(path, encryption_key="k")
    assert entries["e1"]["entry_id"] == "e1"


def test_load_snapshot_checksum_mismatch_lanza(tmp_path: object) -> None:
    path = str(tmp_path / "snap.json")
    tl = _FakeTimeline(entries={"e1": _entry("e1", 1.0)})
    save_snapshot(tl, path)
    data = json.loads(Path(path).read_text())
    data["header"]["checksum"] = "0" * 16
    Path(path).write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_snapshot(path)


def test_load_snapshot_sin_checksum_acepta(tmp_path: object) -> None:
    path = str(tmp_path / "snap.json")
    data = {"header": {"schema_version": 1, "checksum": ""}, "entries": {"a": {}}}
    Path(path).write_text(json.dumps(data))
    header, entries = load_snapshot(path)
    assert header["checksum"] == ""
    assert "a" in entries


def test_entry_to_dict_completo() -> None:
    e = _entry("e1", 2.5)
    d = __import__("motor.memory.snapshot", fromlist=["_entry_to_dict"])._entry_to_dict(e)
    assert d["entry_id"] == "e1"
    assert d["event_type"] == "fact_added"
    assert d["metadata"]["created_by"] == "t"
    assert d["fact_refs"][0]["subject"] == "alice"
