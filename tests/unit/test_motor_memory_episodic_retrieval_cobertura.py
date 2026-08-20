"""Cobertura 100x100 de motor/intelligence/memory (episodic + retrieval). TASK-20260820-008."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig, SessionMemory
from motor.intelligence.memory.record import MemoryRecord, MemoryType
from motor.intelligence.memory.retrieval import ContextQuery, ContextResult, ContextResultList, ContextRetriever


def _ep(oid: str = "e1", ts: str | None = None, session: str = "s1", **kw) -> Episode:
    if ts is None:
        ts = datetime.now(UTC).isoformat()
    return Episode(id=oid, timestamp=ts, session_id=session, **kw)


# ── Episode ──────────────────────────────────────────────────


def test_episode_defaults() -> None:
    e = Episode()
    assert e.id != ""
    assert e.timestamp != ""
    assert e.ttl == 604800


def test_episode_ttl_negativo_resetea() -> None:
    e = Episode(ttl=-5)
    assert e.ttl == 604800


def test_episode_to_record() -> None:
    e = _ep("e1", payload="texto", tags=["a"], references=["r1"], importance=0.7, confidence=0.8, ttl=100)
    r = e.to_record()
    assert r.id == "e1"
    assert r.type == MemoryType.EPISODIC
    assert r.payload == "texto"
    assert r.tags == ["a"]
    assert r.metadata["session_id"] == "s1"


def test_episode_from_record() -> None:
    r = MemoryRecord(id="r1", type=MemoryType.EPISODIC, payload="p", tags=["t"], metadata={"session_id": "ss"})
    e = Episode.from_record(r)
    assert e.id == "r1"
    assert e.session_id == "ss"
    assert e.payload == "p"


def test_episode_from_record_sin_session() -> None:
    r = MemoryRecord(id="r1", payload="p")
    e = Episode.from_record(r)
    assert e.session_id == ""


def test_episode_expired() -> None:
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    e = _ep("e1", ts=viejo, ttl=3600)
    assert e.is_expired is True


def test_episode_no_expired() -> None:
    e = _ep("e1", ttl=3600)
    assert e.is_expired is False
    assert e.age_seconds >= 0


# ── EpisodeStore ─────────────────────────────────────────────


def test_store_y_get() -> None:
    s = EpisodeStore()
    eid = s.store(_ep("e1", payload="x"))
    assert eid == "e1"
    assert s.get("e1").payload == "x"
    assert s.count() == 1


def test_store_id_auto() -> None:
    s = EpisodeStore()
    e = Episode(payload="x")
    eid = s.store(e)
    assert eid == e.id
    assert s.count() == 1


def test_get_inexistente_none() -> None:
    s = EpisodeStore()
    assert s.get("zzz") is None


def test_get_expirado_borra() -> None:
    s = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    s.store(_ep("e1", ts=viejo, ttl=3600))
    assert s.get("e1") is None
    assert s.count() == 0


def test_get_by_session() -> None:
    s = EpisodeStore()
    s.store(_ep("a", ts="2026-08-19T00:00:00+00:00", session="s1"))
    s.store(_ep("b", ts="2026-08-19T01:00:00+00:00", session="s1"))
    s.store(_ep("c", ts="2026-08-19T02:00:00+00:00", session="s2"))
    res = s.get_by_session("s1")
    assert [e.id for e in res] == ["b", "a"]
    assert s.get_by_session("zzz") == []


def test_get_by_session_limit_offset() -> None:
    s = EpisodeStore()
    for i in range(5):
        s.store(_ep(f"e{i}", ts=f"2026-08-19T{i+1:02d}:00:00+00:00", session="s1"))
    res = s.get_by_session("s1", limit=2, offset=1)
    assert len(res) == 2


def test_get_by_time_range() -> None:
    s = EpisodeStore()
    s.store(_ep("a", ts="2026-08-19T00:00:00+00:00"))
    s.store(_ep("b", ts="2026-08-19T03:00:00+00:00"))
    s.store(_ep("c", ts="2026-08-18T00:00:00+00:00"))
    res = s.get_by_time_range("2026-08-19", "2026-08-20")
    assert [e.id for e in res] == ["b", "a"]


def test_get_recent() -> None:
    s = EpisodeStore()
    for i in range(3):
        s.store(_ep(f"e{i}", ts=f"2026-08-19T0{i+1}:00:00+00:00"))
    res = s.get_recent(k=2)
    assert [e.id for e in res] == ["e2", "e1"]


def test_count_por_sesion() -> None:
    s = EpisodeStore()
    s.store(_ep("a", session="s1"))
    s.store(_ep("b", session="s1"))
    s.store(_ep("c", session="s2"))
    assert s.count() == 3
    assert s.count("s1") == 2


def test_delete() -> None:
    s = EpisodeStore()
    s.store(_ep("a"))
    assert s.delete("a") is True
    assert s.delete("a") is False
    assert s.count() == 0


def test_delete_expired() -> None:
    s = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    s.store(_ep("a", ts=viejo, ttl=3600))
    s.store(_ep("b"))
    assert s.delete_expired() == 1
    assert s.count() == 1


def test_clear_session() -> None:
    s = EpisodeStore()
    s.store(_ep("a", session="s1"))
    s.store(_ep("b", session="s1"))
    s.store(_ep("c", session="s2"))
    assert s.clear_session("s1") == 2
    assert s.count() == 1


def test_clear_all() -> None:
    s = EpisodeStore()
    s.store(_ep("a"))
    s.store(_ep("b"))
    assert s.clear_all() == 2
    assert s.count() == 0


def test_trim_por_max_episodes() -> None:
    s = EpisodeStore(config=EpisodeStoreConfig(max_episodes=2))
    s.store(_ep("a", ts="2026-08-19T00:00:00+00:00"))
    s.store(_ep("b", ts="2026-08-19T01:00:00+00:00"))
    s.store(_ep("c", ts="2026-08-19T02:00:00+00:00"))
    assert s.count() == 2
    assert s.get("a") is None


def test_persistencia_sqlite(tmp_path: object) -> None:
    path = str(tmp_path / "ep.db")
    s = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    s.store(_ep("a", payload="texto-a", tags=["t1"], references=["r1"]))
    s.store(_ep("b", payload="texto-b", session="s2"))
    s.close()
    s2 = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    assert s2.count() == 2
    assert s2.get("a").tags == ["t1"]
    assert s2.get("b").session_id == "s2"
    s2.close()


def test_persistencia_sqlite_delete(tmp_path: object) -> None:
    path = str(tmp_path / "ep.db")
    s = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    s.store(_ep("a"))
    s.delete("a")
    s.close()
    s2 = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    assert s2.count() == 0
    s2.close()


def test_db_corrupta_se_recrea(tmp_path: object) -> None:
    path = str(tmp_path / "ep.db")
    Path(path).write_bytes(b"no-sqlite")
    s = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    assert s.count() == 0
    s.store(_ep("a"))
    assert s.count() == 1
    s.close()


def test_persist_error_se_degrada() -> None:
    s = EpisodeStore()
    e = _ep("a")
    s._episodes[e.id] = e
    s._by_session.setdefault(e.session_id, set()).add(e.id)

    class _ConnRoto:
        def execute(self, *a, **k):
            msg = "roto"
            raise sqlite3.OperationalError(msg)

        def close(self):
            pass

    s._conn = _ConnRoto()  # type: ignore[assignment]
    s._persist(e)
    s._persist_delete("a")
    s.close()


def test_load_db_fila_corrupta_se_omite(tmp_path: object) -> None:
    path = str(tmp_path / "ep.db")
    s = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    s.store(_ep("ok", payload="bien"))
    s.close()
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO episodes (id, payload) VALUES ('bad', NULL)")
    conn.commit()
    conn.close()
    s2 = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    assert s2.get("ok") is not None
    s2.close()


def test_session_memory() -> None:
    sm = SessionMemory()
    sid = sm.create_session("ses1", metadata={"usuario": "ramon"})
    assert sid == "ses1"
    ep = sm.add_episode("ses1", "hola", source="chat", importance=0.9)
    assert ep.session_id == "ses1"
    assert sm.session_count() == 1
    assert len(sm.get_history("ses1")) == 1
    assert len(sm.get_recent()) == 1
    assert sm.close_session("ses1") is True
    assert sm.close_session("ses1") is False
    assert sm.session_count() == 0


def test_session_memory_id_auto() -> None:
    sm = SessionMemory()
    sid = sm.create_session()
    assert sid != ""


def test_session_memory_store_compartido() -> None:
    store = EpisodeStore()
    sm = SessionMemory(store=store)
    assert sm.store is store


# ── retrieval ────────────────────────────────────────────────


def test_context_result_explanation() -> None:
    r = ContextResult(episode=_ep("a"), score=0.5, recency_score=0.4, importance_score=0.3, confidence_score=0.2)
    assert "score=0.500" in r.explanation
    assert "rec=" in r.explanation
    assert "sem=" not in r.explanation


def test_context_result_explanation_con_sem() -> None:
    r = ContextResult(episode=_ep("a"), semantic_score=0.9, recency_score=0.4, importance_score=0.3, confidence_score=0.2)
    assert "sem=0.90" in r.explanation


def test_context_result_list_indexado() -> None:
    rl = ContextResultList(results=[ContextResult(episode=_ep("a"))])
    assert len(rl) == 1
    assert rl[0].episode.id == "a"


def test_context_result_list_to_dict() -> None:
    rl = ContextResultList(results=[ContextResult(episode=_ep("a", payload="texto"), score=0.7)])
    d = rl.to_dict()
    assert d[0]["id"] == "a"
    assert d[0]["payload"] == "texto"
    assert d[0]["score"] == 0.7


def test_context_result_list_to_dict_payload_vacio() -> None:
    rl = ContextResultList(results=[ContextResult(episode=_ep("a", payload=""))])
    assert rl.to_dict()[0]["payload"] == ""


def test_retriever_search_basico() -> None:
    store = EpisodeStore()
    store.store(_ep("a", payload="uno", importance=0.5, confidence=0.5))
    store.store(_ep("b", payload="dos", importance=0.9, confidence=0.9))
    r = ContextRetriever(store)
    res = r.search(ContextQuery(k=10))
    assert res.total == 2
    assert res.results[0].episode.id == "b"  # mayor importancia primero


def test_retriever_search_por_sesion() -> None:
    store = EpisodeStore()
    store.store(_ep("a", session="s1", importance=0.5))
    store.store(_ep("b", session="s2", importance=0.9))
    r = ContextRetriever(store)
    res = r.search(ContextQuery(session_id="s1"))
    assert res.total == 1
    assert res.results[0].episode.id == "a"


def test_retriever_search_por_tags() -> None:
    store = EpisodeStore()
    store.store(_ep("a", tags=["urgente"]))
    store.store(_ep("b", tags=["normal"]))
    r = ContextRetriever(store)
    res = r.search(ContextQuery(tags=["urgente"]))
    assert res.total == 1


def test_retriever_search_offset_k() -> None:
    store = EpisodeStore()
    for i in range(5):
        store.store(_ep(f"e{i}", importance=i / 10))
    r = ContextRetriever(store)
    res = r.search(ContextQuery(k=2, offset=1))
    assert len(res.results) == 2


def test_retriever_weights_personalizados() -> None:
    store = EpisodeStore()
    store.store(_ep("a", importance=1.0, confidence=0.1))
    store.store(_ep("b", importance=0.1, confidence=1.0))
    r = ContextRetriever(store, weights={"importance": 1.0, "confidence": 0.0, "recency": 0.0})
    res = r.search(ContextQuery(k=10))
    assert res.results[0].episode.id == "a"


def test_retriever_expirado_borrado() -> None:
    store = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    store.store(_ep("a", ts=viejo, ttl=3600))
    store.store(_ep("b"))
    r = ContextRetriever(store)
    res = r.search(ContextQuery())
    assert res.total == 1
    # get_recent filtra expirados antes; el retriever los borra al detectarlos vía _is_expired
    assert store.count() >= 1


def test_retriever_recency_score_todos_iguales() -> None:
    store = EpisodeStore()
    ts = datetime.now(UTC).isoformat()
    store.store(_ep("a", ts=ts))
    store.store(_ep("b", ts=ts))
    r = ContextRetriever(store)
    res = r.search(ContextQuery())
    assert res.total == 2


def test_retriever_semantic_weight_con_embedding() -> None:
    store = EpisodeStore()
    store.store(_ep("a", embedding=[0.1, 0.2]))
    r = ContextRetriever(store, weights={"semantic": 1.0, "recency": 0.0, "importance": 0.0, "confidence": 0.0})
    res = r.search(ContextQuery(text="q"))
    assert res.results[0].semantic_score == 0.0


def test_retriever_ranks_asignados() -> None:
    store = EpisodeStore()
    store.store(_ep("a", importance=0.1))
    store.store(_ep("b", importance=0.9))
    r = ContextRetriever(store)
    res = r.search(ContextQuery())
    assert [x.rank for x in res.results] == [0, 1]


def test_retriever_k_minimo_1() -> None:
    store = EpisodeStore()
    store.store(_ep("a"))
    r = ContextRetriever(store)
    res = r.search(ContextQuery(k=0))
    assert len(res.results) == 1


# ── ramas restantes ──────────────────────────────────────────


def test_episode_ttl_cero_no_expira() -> None:
    e = _ep("e1", ttl=0)
    assert e.is_expired is False


def test_episode_ttl_negativo_no_expira() -> None:
    e = _ep("e1", ttl=-1)
    assert e.is_expired is False


def test_episode_is_expired_ttl_cero() -> None:
    e = _ep("e1", ttl=0)
    e.ttl = 0  # bypass del __post_init__ que resetea ttl<=0
    assert e.is_expired is False


def test_episode_store_load_from_db_sin_conn() -> None:
    s = EpisodeStore()
    s._conn = None
    s._load_from_db()


def test_episode_store_store_sin_id_ni_timestamp() -> None:
    s = EpisodeStore()
    e = Episode(session_id="s9")
    e.id = ""
    e.timestamp = ""
    eid = s.store(e)
    assert eid != ""
    assert e.timestamp != ""


def test_episode_get_by_session_inexistente() -> None:
    s = EpisodeStore()
    assert s.get_by_session("nope") == []


def test_episode_get_by_session_con_id_fantasma() -> None:
    s = EpisodeStore()
    s._by_session["s1"] = {"ghost"}  # id en índice pero no en _episodes
    assert s.get_by_session("s1") == []


def test_episode_clear_all_con_db(tmp_path: object) -> None:
    path = str(tmp_path / "ep.db")
    s = EpisodeStore(config=EpisodeStoreConfig(persist_path=path))
    s.store(_ep("a"))
    assert s.clear_all() == 1
    s.close()


def test_episode_store_close_sin_conn() -> None:
    s = EpisodeStore()
    s.close()  # no lanza


def test_session_memory_episode_count_solo_sesion_activa() -> None:
    sm = SessionMemory()
    sm.add_episode("s1", "x")  # sesión no creada → no cuenta
    assert sm.session_count() == 0


def test_retriever_ttl_cero_no_expira() -> None:
    store = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    store.store(_ep("a", ts=viejo, ttl=0))  # ttl<=0 → nunca expira
    r = ContextRetriever(store)
    res = r.search(ContextQuery())
    assert res.total == 1


def test_retriever_recency_max_age_cero() -> None:
    store = EpisodeStore()
    futuro = (datetime.now(UTC) + timedelta(hours=1)).isoformat()  # ts futuro → age negativo → max_age=0
    r = ContextRetriever(store)
    scored = r._score([_ep("a", ts=futuro), _ep("b", ts=futuro)], ContextQuery(), {"semantic": 0.0, "recency": 0.35, "importance": 0.35, "confidence": 0.3})
    assert scored[0].recency_score == 1.0


def test_retriever_is_expired_ttl_cero() -> None:
    store = EpisodeStore()
    r = ContextRetriever(store)
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    ep = _ep("a", ts=viejo, ttl=0)
    ep.ttl = 0  # bypass del __post_init__
    assert r._is_expired(ep) is False


def test_retriever_is_expired_borra() -> None:
    store = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    ep = _ep("a", ts=viejo, ttl=3600)
    store._episodes[ep.id] = ep
    r = ContextRetriever(store)
    assert r._is_expired(ep) is True
    assert store.count() == 0
