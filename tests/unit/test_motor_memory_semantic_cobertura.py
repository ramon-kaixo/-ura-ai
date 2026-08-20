"""Cobertura 100x100 de motor/intelligence/memory (parte 1). TASK-20260820-008."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from motor.intelligence.memory.base import MemoryStore
from motor.intelligence.memory.episodic import Episode
from motor.intelligence.memory.extractor import FactExtractor, RuleBasedFactExtractor
from motor.intelligence.memory.extractor_llm import LLMFactExtractor
from motor.intelligence.memory.orchestrator import MemoryOrchestrator
from motor.intelligence.memory.record import MemoryRecord, MemoryType
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore, consolidate_episodes

# ── record ───────────────────────────────────────────────────


def test_memory_type_valores() -> None:
    assert MemoryType.WORKING.value == "working"
    assert MemoryType.EPISODIC.value == "episodic"
    assert MemoryType.SEMANTIC.value == "semantic"


def test_record_defaults() -> None:
    r = MemoryRecord()
    assert r.id != ""
    assert r.timestamp != ""
    assert r.type == MemoryType.WORKING
    assert r.metadata["access_count"] == 0
    assert r.metadata["created_at"] == r.timestamp


def test_record_con_ids() -> None:
    r = MemoryRecord(id="r1", timestamp="t1", ttl=None)
    assert r.id == "r1"
    assert r.timestamp == "t1"
    assert r.metadata == {}


def test_record_ttl_negativo_sin_metadata() -> None:
    r = MemoryRecord(ttl=-1)
    assert r.metadata == {}


def test_record_no_expired() -> None:
    r = MemoryRecord()
    assert r.is_expired is False
    assert r.age_seconds >= 0


def test_record_expired_con_ttl_corto() -> None:
    viejo = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    r = MemoryRecord(ttl=3600)
    r.metadata["created_at"] = viejo
    assert r.is_expired is True


def test_record_ttl_none_no_expira() -> None:
    r = MemoryRecord(ttl=None)
    assert r.is_expired is False


# ── base (MemoryStore ABC) ───────────────────────────────────


def test_memory_store_abstracto() -> None:
    with pytest.raises(TypeError):
        MemoryStore()


class _ConSuperStore(MemoryStore):
    def __init__(self) -> None:
        self.llamadas: list[str] = []

    def store(self, record: MemoryRecord) -> str:
        r = super().store(record)
        if r is None:
            self.llamadas.append("store")
            return ""
        return r

    def get(self, record_id: str) -> MemoryRecord | None:
        r = super().get(record_id)
        return r

    def search(self, query: str, k: int = 10, memory_type: MemoryType | None = None) -> list[MemoryRecord]:
        r = super().search(query, k, memory_type)
        if r is None:
            return []
        return r

    def delete(self, record_id: str) -> bool:
        r = super().delete(record_id)
        if r is None:
            return False
        return r

    def count(self, memory_type: MemoryType | None = None) -> int:
        r = super().count(memory_type)
        if r is None:
            return 0
        return r


def test_memory_store_elipsis_via_super() -> None:
    s = _ConSuperStore()
    s.store(MemoryRecord())
    assert s.get("x") is None
    assert s.search("q") == []
    assert s.delete("x") is False
    assert s.count() == 0


# ── orchestrator ─────────────────────────────────────────────


class _ExtractorStub:
    def __init__(self, count: int = 3) -> None:
        self.count = count

    def extract(self, episode: Episode) -> list:
        return [SemanticFact(subject="s", predicate="p", object_value="o")] * self.count


class _EpisodeStoreStub:
    def __init__(self, n: int = 5) -> None:
        self._episodes = {f"e{i}": Episode(id=f"e{i}", payload=f"texto {i}") for i in range(n)}

    def get_recent(self, k: int = 100) -> list:
        return list(self._episodes.values())[:k]


class _CompressorStub:
    def __init__(self, creados: int = 2) -> None:
        self.creados = creados

    def compress(self):
        class _R:
            summaries_created: int
            episodes_compressed: int

        r = _R()
        r.summaries_created = self.creados
        r.episodes_compressed = 4
        return r


class _ForgettingStub:
    def __init__(self, removed: int = 1) -> None:
        self.removed = removed

    def run(self, dry_run: bool = False):
        class _R:
            total_removed: int

        r = _R()
        r.total_removed = self.removed
        return r


def test_orchestrator_consolidate_sin_extractor() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(), semantic_store=SemanticMemoryStore())
    assert o.consolidate() == 0


def test_orchestrator_consolidate_sin_episodios() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(0), semantic_store=SemanticMemoryStore(), extractor=_ExtractorStub())
    assert o.consolidate() == 0


def test_orchestrator_consolidate_extractor_sin_facts() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(3), semantic_store=SemanticMemoryStore(), extractor=_ExtractorStub(0))
    assert o.consolidate() == 0


def test_orchestrator_consolidate_ok() -> None:
    store = SemanticMemoryStore()
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(3), semantic_store=store, extractor=_ExtractorStub())
    assert o.consolidate(batch_size=10) == 9


def test_orchestrator_compress_sin_compressor() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(), semantic_store=SemanticMemoryStore())
    assert o.compress() == 0


def test_orchestrator_compress_ok() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(), semantic_store=SemanticMemoryStore(), compressor=_CompressorStub())
    assert o.compress() == 2


def test_orchestrator_forget_sin_engine() -> None:
    o = MemoryOrchestrator(episode_store=_EpisodeStoreStub(), semantic_store=SemanticMemoryStore())
    assert o.forget(dry_run=True) == {"removed": 0, "dry_run": True}


def test_orchestrator_forget_ok() -> None:
    o = MemoryOrchestrator(
        episode_store=_EpisodeStoreStub(),
        semantic_store=SemanticMemoryStore(),
        forgetting_engine=_ForgettingStub(3),
    )
    assert o.forget(dry_run=False) == {"removed": 3, "dry_run": False}


def test_orchestrator_run_all() -> None:
    o = MemoryOrchestrator(
        episode_store=_EpisodeStoreStub(2),
        semantic_store=SemanticMemoryStore(),
        extractor=_ExtractorStub(1),
        compressor=_CompressorStub(2),
        forgetting_engine=_ForgettingStub(1),
    )
    r = o.run_all(dry_run=True)
    assert r == {"consolidated": 2, "compressed": 2, "forgotten": 1}


def test_orchestrator_compress_cero() -> None:
    o = MemoryOrchestrator(
        episode_store=_EpisodeStoreStub(),
        semantic_store=SemanticMemoryStore(),
        compressor=_CompressorStub(0),
    )
    assert o.compress() == 0


def test_orchestrator_forget_cero() -> None:
    o = MemoryOrchestrator(
        episode_store=_EpisodeStoreStub(),
        semantic_store=SemanticMemoryStore(),
        forgetting_engine=_ForgettingStub(0),
    )
    assert o.forget() == {"removed": 0, "dry_run": False}


# ── extractor (rule-based) ───────────────────────────────────


def _ep(payload: str, tags: list[str] | None = None) -> Episode:
    return Episode(payload=payload, tags=tags or [], confidence=0.8, importance=0.6, session_id="s1")


def test_extractor_sin_payload() -> None:
    assert RuleBasedFactExtractor().extract(_ep("")) == []


def test_extractor_patron_attribute() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("El sistema es rápido y fiable"))
    assert any(f.fact_type == "attribute" for f in facts)


def test_extractor_patron_relation() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("El servidor contiene la base de datos"))
    assert any(f.fact_type == "relation" for f in facts)


def test_extractor_patron_event() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("El servicio se ha reiniciado correctamente"))
    assert any(f.fact_type == "event" for f in facts)


def test_extractor_patron_statement() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("El sistema indica que todo funciona"))
    assert any(f.fact_type == "statement" for f in facts)


def test_extractor_patron_error() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("Error: conexión rechazada"))
    assert any(f.fact_type == "error" and f.subject == "sistema" for f in facts)


def test_extractor_patron_config() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("Configuración timeout = 30"))
    assert any(f.fact_type == "attribute" for f in facts)


def test_extractor_patron_igual() -> None:
    facts = RuleBasedFactExtractor().extract(_ep("puerto = 8080"))
    assert any(f.fact_type == "attribute" for f in facts)


def test_extractor_fact_metadata() -> None:
    e = _ep("El sistema es rápido y fiable")
    facts = RuleBasedFactExtractor().extract(e)
    f = facts[0]
    assert f.confidence == pytest.approx(0.8 * 0.9)
    assert f.importance == 0.6
    assert f.metadata["session_id"] == "s1"
    assert f.source_episode_ids == [e.id]
    assert f.tags == []


def test_extractor_abstracto() -> None:
    with pytest.raises(TypeError):
        FactExtractor()


class _ConSuperExtractor(FactExtractor):
    def extract(self, episode: Episode) -> list:
        r = super().extract(episode)
        if r is None:
            return []
        return r


def test_extractor_elipsis_via_super() -> None:
    assert _ConSuperExtractor().extract(_ep("x")) == []


class _ExtractorConFactFalso(RuleBasedFactExtractor):
    def _make_fact(self, episode, subject, predicate, object_value, fact_type):
        return None


def test_extractor_fact_falsy_se_ignora() -> None:
    e = _ep("El sistema es rápido y fiable")
    assert _ExtractorConFactFalso().extract(e) == []


# ── extractor_llm ────────────────────────────────────────────


def test_llm_extractor_sin_payload() -> None:
    assert LLMFactExtractor().extract(_ep("")) == []


def test_llm_extractor_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps([{"subject": "a", "predicate": "b", "object": "c", "type": "relation"}])
    monkeypatch.setattr("motor.intelligence.memory.extractor_llm.generate", lambda *a, **k: raw)
    facts = LLMFactExtractor().extract(_ep("texto"))
    assert len(facts) == 1
    assert facts[0].subject == "a"
    assert facts[0].confidence == pytest.approx(0.8 * 0.8)


def test_llm_extractor_error_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("motor.intelligence.memory.extractor_llm.generate", lambda *a, **k: "Error: ollama caído")
    assert LLMFactExtractor().extract(_ep("texto")) == []


def test_llm_extractor_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a, **k):
        msg = "timeout"
        raise TimeoutError(msg)

    monkeypatch.setattr("motor.intelligence.memory.extractor_llm.generate", _boom)
    assert LLMFactExtractor().extract(_ep("texto")) == []


def test_llm_parse_response_fenced() -> None:
    e = _ep("texto")
    raw = "```json\n" + json.dumps([{"subject": "s", "predicate": "p", "object": "o"}]) + "\n```"
    facts = LLMFactExtractor()._parse_response(raw, e)
    assert len(facts) == 1


def test_llm_parse_response_no_lista() -> None:
    e = _ep("texto")
    assert LLMFactExtractor()._parse_response('{"no": "lista"}', e) == []


def test_llm_parse_response_item_no_dict() -> None:
    e = _ep("texto")
    facts = LLMFactExtractor()._parse_response('[1, 2]', e)
    assert facts == []


def test_llm_parse_response_sin_object() -> None:
    e = _ep("texto")
    facts = LLMFactExtractor()._parse_response('[{"subject": "s", "predicate": "p", "object": ""}]', e)
    assert facts == []


def test_llm_parse_response_fallback() -> None:
    e = _ep("texto")
    facts = LLMFactExtractor()._parse_response('{"subject": "solo-subject"', e)
    assert facts == []


def test_llm_fallback_parse_encuentra_subjects() -> None:
    raw = '{"subject": "a"} texto {"subject": "b"}'
    items = LLMFactExtractor()._fallback_parse(raw)
    assert items == [{"subject": "a"}, {"subject": "b"}]


def test_llm_fallback_parse_sin_matches() -> None:
    assert LLMFactExtractor()._fallback_parse("nada") == []


# ── semantic ─────────────────────────────────────────────────


def test_semantic_fact_defaults() -> None:
    f = SemanticFact(subject="s", predicate="p", object_value="o")
    assert f.id != ""
    assert f.created_at != ""
    assert f.version == 1


def test_semantic_fact_key() -> None:
    f = SemanticFact(subject="a", predicate="b", object_value="c")
    assert f.key == "a|b|c"


def test_semantic_fact_merge() -> None:
    f1 = SemanticFact(subject="a", predicate="b", object_value="c", confidence=0.5, importance=0.3, source_episode_ids=["e1"], tags=["x"])
    f2 = SemanticFact(subject="a", predicate="b", object_value="c", confidence=0.9, importance=0.8, source_episode_ids=["e2", "e1"], tags=["y"], metadata={"k": "v"})
    f1.merge(f2)
    assert f1.confidence == 0.9
    assert f1.importance == 0.8
    assert f1.version == 2
    assert f1.source_episode_ids == ["e1", "e2"]
    assert f1.tags == ["x", "y"]
    assert f1.metadata == {"k": "v"}


def test_semantic_fact_merge_con_ids_duplicados() -> None:
    f1 = SemanticFact(subject="a", predicate="b", object_value="c", source_episode_ids=["e1"], tags=["x"])
    f2 = SemanticFact(subject="a", predicate="b", object_value="c", source_episode_ids=["e1"], tags=["x"])
    f1.merge(f2)
    assert f1.source_episode_ids == ["e1"]
    assert f1.tags == ["x"]


def test_semantic_fact_to_dict() -> None:
    f = SemanticFact(subject="a", predicate="b", object_value="c", source_episode_ids=["e1"])
    d = f.to_dict()
    assert d["subject"] == "a"
    assert d["object"] == "c"
    assert d["source_episodes"] == 1
    assert d["version"] == 1


def test_semantic_store_store_y_get() -> None:
    s = SemanticMemoryStore()
    fid = s.store(SemanticFact(subject="a", predicate="b", object_value="c"))
    assert s.get(fid).subject == "a"
    assert s.count() == 1


def test_semantic_store_merge_por_key() -> None:
    s = SemanticMemoryStore()
    fid1 = s.store(SemanticFact(subject="a", predicate="b", object_value="c", confidence=0.5))
    fid2 = s.store(SemanticFact(subject="a", predicate="b", object_value="c", confidence=0.9))
    assert fid1 == fid2
    assert s.get(fid1).confidence == 0.9
    assert s.count() == 1


def test_semantic_store_get_by_key() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="a", predicate="b", object_value="c"))
    assert s.get_by_key("a", "b", "c") is not None
    assert s.get_by_key("x", "y", "z") is None


def test_semantic_store_search_por_texto() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="alice", predicate="tiene", object_value="gato"))
    s.store(SemanticFact(subject="bob", predicate="tiene", object_value="perro"))
    res = s.search(text="gato")
    assert len(res) == 1
    assert res[0].subject == "alice"


def test_semantic_store_search_por_tags() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="a", predicate="p", object_value="o", tags=["urgente"]))
    s.store(SemanticFact(subject="b", predicate="p", object_value="o", tags=["normal"]))
    assert len(s.search(tags=["urgente"])) == 1


def test_semantic_store_search_por_tipo() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="a", predicate="p", object_value="o", fact_type="relation"))
    s.store(SemanticFact(subject="b", predicate="p", object_value="o", fact_type="error"))
    assert len(s.search(fact_type="error")) == 1


def test_semantic_store_search_por_entidad() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="alice", predicate="p", object_value="x"))
    s.store(SemanticFact(subject="bob", predicate="p", object_value="alice"))
    assert len(s.search(entity="alice")) == 2


def test_semantic_store_search_orden_y_k() -> None:
    s = SemanticMemoryStore()
    for i in range(5):
        s.store(SemanticFact(subject=f"e{i}", predicate="p", object_value="o", importance=i / 10))
    res = s.search(text="", k=2)
    assert len(res) == 2
    assert res[0].subject == "e4"


def test_semantic_store_delete() -> None:
    s = SemanticMemoryStore()
    fid = s.store(SemanticFact(subject="a", predicate="b", object_value="c"))
    assert s.delete(fid) is True
    assert s.delete(fid) is False
    assert s.count() == 0


def test_semantic_store_clear_all() -> None:
    s = SemanticMemoryStore()
    s.store(SemanticFact(subject="a", predicate="b", object_value="c"))
    assert s.clear_all() == 1
    assert s.count() == 0


def test_semantic_store_persistencia(tmp_path: object) -> None:
    path = str(tmp_path / "sem.db")
    s = SemanticMemoryStore(persist_path=path)
    s.store(SemanticFact(subject="persistido", predicate="p", object_value="o"))
    s.close()
    s2 = SemanticMemoryStore(persist_path=path)
    assert s2.count() == 1
    assert s2.get_by_key("persistido", "p", "o") is not None
    s2.close()


def test_semantic_store_clear_con_db(tmp_path: object) -> None:
    path = str(tmp_path / "sem.db")
    s = SemanticMemoryStore(persist_path=path)
    s.store(SemanticFact(subject="a", predicate="b", object_value="c"))
    assert s.clear_all() == 1
    s.close()


def test_consolidate_episodes() -> None:
    store = SemanticMemoryStore()
    n = consolidate_episodes([_ep("El sistema es rápido y fiable")], store, RuleBasedFactExtractor())
    assert n >= 1
    assert store.count() == n


def test_semantic_persist_error_se_degrada() -> None:
    s = SemanticMemoryStore()
    f = SemanticFact(subject="a", predicate="b", object_value="c")
    s._facts[f.id] = f
    s._by_key[f.key] = f.id

    class _ConnRoto:
        def execute(self, *a, **k):
            msg = "db rota"
            raise __import__("sqlite3").OperationalError(msg)

        def close(self):
            pass

    s._conn = _ConnRoto()  # type: ignore[assignment]
    s._persist(f)
    s._persist_delete(f.id)  # no debe lanzar
    s.close()


def test_semantic_persist_delete_conn_cerrado(tmp_path: object) -> None:
    import sqlite3

    s = SemanticMemoryStore()
    s._conn = sqlite3.connect(str(tmp_path / "c.db"))
    s._conn.close()  # conn cerrado: execute lanza ProgrammingError
    s._persist_delete("cualquier-id")  # except → log.warning
    s._persist(SemanticFact(subject="a", predicate="b", object_value="c"))


def test_semantic_persist_delete_commit_roto() -> None:

    class _ConnCommitRoto:
        def execute(self, sql: str, params=()):
            return __import__("sqlite3").Cursor.__new__(__import__("sqlite3").Cursor)

        def commit(self):
            msg = "commit roto"
            raise __import__("sqlite3").OperationalError(msg)

    s = SemanticMemoryStore()
    s._conn = _ConnCommitRoto()  # type: ignore[assignment]
    s._persist_delete("x")  # execute OK, commit falla → except


def test_semantic_load_from_db_sin_conn() -> None:
    s = SemanticMemoryStore()
    s._conn = None
    s._load_from_db()  # return temprano, no lanza


def test_semantic_close_sin_conn() -> None:
    s = SemanticMemoryStore()
    s.close()  # sin conn, no lanza


def test_semantic_db_fila_corrupta_se_omite(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    path = str(tmp_path / "sem.db")
    s = SemanticMemoryStore(persist_path=path)
    s.store(SemanticFact(subject="ok", predicate="p", object_value="o"))
    s.close()
    # inyectamos fila corrupta directamente
    import sqlite3

    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO semantic_facts (id, subject) VALUES ('bad', 'malo')"  # obj NULL rompe json/float
    )
    conn.commit()
    conn.close()
    s2 = SemanticMemoryStore(persist_path=path)
    assert s2.count() >= 1  # la fila buena se carga, la mala se omite
    s2.close()
