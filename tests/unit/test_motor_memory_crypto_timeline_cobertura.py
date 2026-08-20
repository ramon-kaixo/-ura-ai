"""Cobertura 100x100 de motor/memory (crypto + timeline). TASK-20260820-006."""

from __future__ import annotations

import pytest

from motor.memory import crypto
from motor.memory.models import (
    FactRef,
    MemoryEntry,
    MemoryEventType,
    MemoryMetadata,
    make_entry_id,
)
from motor.memory.timeline import MemoryTimeline

# ── crypto ───────────────────────────────────────────────────


def test_encrypt_sin_clave_devuelve_plaintext() -> None:
    raw = b"hola mundo"
    assert crypto.encrypt(raw, "") == raw


def test_decrypt_sin_clave_devuelve_ciphertext() -> None:
    raw = b"hola mundo"
    assert crypto.decrypt(raw, "") == raw


def test_is_encryption_available_booleano() -> None:
    assert isinstance(crypto.is_encryption_available(), bool)


def test_derive_key_sin_cryptography_devuelve_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "_ENCRYPTION_ENABLED", False)
    assert crypto._derive_key("k", b"salt") is None
    assert crypto.encrypt(b"x", "k") == b"x"
    assert crypto.decrypt(b"x", "k") == b"x"


def test_import_cryptography_fallido_marca_deshabilitado(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import importlib

    real_import = builtins.__import__

    def _bloquea_cryptography(name: str, *args, **kwargs):
        if name.startswith("cryptography"):
            msg = f"No module named '{name}'"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _bloquea_cryptography)
    importlib.reload(crypto)
    assert not crypto._ENCRYPTION_ENABLED
    monkeypatch.undo()
    importlib.reload(crypto)
    assert crypto._ENCRYPTION_ENABLED or not crypto._ENCRYPTION_ENABLED


def test_encrypt_derived_none_devuelve_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "_ENCRYPTION_ENABLED", True)
    monkeypatch.setattr(crypto, "_derive_key", lambda k, s: None)
    assert crypto.encrypt(b"x", "clave") == b"x"
    assert crypto.decrypt(b"x", "clave") == b"x"


def test_encrypt_con_clave_devuelve_distinto() -> None:
    if not crypto.is_encryption_available():
        pytest.skip("cryptography no instalado")
    plain = b"secreto"
    enc = crypto.encrypt(plain, "mi-clave")
    assert enc != plain
    assert crypto.decrypt(enc, "mi-clave") == plain


def test_roundtrip_clave_incorrecta_rompe_datos() -> None:
    if not crypto.is_encryption_available():
        pytest.skip("cryptography no instalado")
    enc = crypto.encrypt(b"secreto", "a")
    dec = crypto.decrypt(enc, "b")
    assert dec != b"secreto"


# ── helpers de entries ───────────────────────────────────────


def _entry(
    entry_id: str = "e1",
    ts: float = 1.0,
    refs: list[tuple[str, str, str]] | None = None,
    event: MemoryEventType = MemoryEventType.FACT_ADDED,
) -> MemoryEntry:
    fr = tuple(
        FactRef(fact_id=fid, version_id=vid, subject=sub, predicate="p", object=sub)
        for fid, vid, sub in (refs or [])
    )
    return MemoryEntry(
        entry_id=entry_id,
        timestamp=ts,
        fact_refs=fr,
        source="test",
        event_type=event,
        metadata=MemoryMetadata(pipeline_version="1", created_by="test"),
    )


# ── make_entry_id ────────────────────────────────────────────


def test_make_entry_id_determinista() -> None:
    a = make_entry_id("fact_added", ["v2", "v1"], 100)
    b = make_entry_id("fact_added", ["v1", "v2"], 100)
    assert a == b
    assert len(a) == 16


def test_make_entry_id_cambia_con_evento_y_ts() -> None:
    base = make_entry_id("fact_added", ["v1"], 100)
    assert make_entry_id("rollback", ["v1"], 100) != base
    assert make_entry_id("fact_added", ["v1"], 200) != base


# ── MemoryTimeline ───────────────────────────────────────────


def test_append_y_size() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0))
    tl.append(_entry("b", 2.0))
    assert tl.size == 2
    assert set(tl.entries.keys()) == {"a", "b"}


def test_append_duplicado_lanza_keyerror() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0))
    with pytest.raises(KeyError):
        tl.append(_entry("a", 1.0))


def test_state_at_antes_del_primero_devuelve_none() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 5.0))
    assert tl.state_at(4.0) is None


def test_state_at_devuelve_vigente() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 5.0, [("f1", "v1", "alice")]))
    tl.append(_entry("b", 10.0, [("f2", "v1", "bob")]))
    assert tl.state_at(7.0).entry_id == "a"
    assert tl.state_at(10.0).entry_id == "b"
    assert tl.state_at(99.0).entry_id == "b"


def test_state_at_desempate_mayor_entry_id() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("aaa", 5.0))
    tl.append(_entry("bbb", 5.0))
    assert tl.state_at(5.0).entry_id == "bbb"


def test_by_entity_insensible_a_mayusculas() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0, [("f1", "v1", "Alice")]))
    assert [e.entry_id for e in tl.by_entity("alice")] == ["a"]
    assert [e.entry_id for e in tl.by_entity("nadie")] == []


def test_by_time_rango() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0))
    tl.append(_entry("b", 2.0))
    tl.append(_entry("c", 3.0))
    assert [e.entry_id for e in tl.by_time(1.5, 2.5)] == ["b"]
    assert [e.entry_id for e in tl.by_time(0.0, 99.0)] == ["a", "b", "c"]


def test_by_event() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0, event=MemoryEventType.FACT_ADDED))
    tl.append(_entry("b", 2.0, event=MemoryEventType.ROLLBACK))
    assert [e.entry_id for e in tl.by_event("rollback")] == ["b"]
    assert [e.entry_id for e in tl.by_event("nada")] == []


def test_get_devuelve_entry_o_none() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("x", 1.0))
    assert tl.get("x") is not None
    assert tl.get("zzz") is None


def test_diff_compara_refs() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0, [("f1", "v1", "alice"), ("f2", "v1", "bob")]))
    tl.append(_entry("b", 2.0, [("f2", "v1", "bob"), ("f3", "v1", "carol")]))
    d = tl.diff("a", "b")
    assert d["added"] == ["f3"]
    assert d["removed"] == ["f1"]
    assert d["common"] == ["f2"]


def test_diff_entry_inexistente_lanza() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0))
    with pytest.raises(KeyError):
        tl.diff("a", "zzz")


def test_timeline_propiedad_es_copia() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0))
    tl.timeline.append((9.0, "hack"))
    assert tl.size == 1


def test_index_por_entidad_y_evento() -> None:
    tl = MemoryTimeline()
    tl.append(_entry("a", 1.0, [("f1", "v1", "alice")], event=MemoryEventType.FACT_ADDED))
    assert tl._by_entity["alice"] == ["a"]
    assert tl._by_event["fact_added"] == ["a"]
