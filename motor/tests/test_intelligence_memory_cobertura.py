"""Cobertura 100x100 de motor/intelligence/memory (TASK-20260814-001).

Cubre los remanentes no tocados por test_hybrid_memory/test_e2e/test_pipeline_e2e:
record, episodic, semantic, retrieval, compression, forgetting, extractor,
extractor_llm, orchestrator y ramas de degradación de hybrid.
"""

from __future__ import annotations

import sqlite3
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from motor.intelligence.memory.compression import (
    AgeBasedCompression,
    CompressionScheduler,
    HybridCompressionPolicy,
    MemoryCompressor,
    NeverCompress,
    SizeBasedCompression,
    SummaryRecord,
)
from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig, SessionMemory
from motor.intelligence.memory.extractor import RuleBasedFactExtractor
from motor.intelligence.memory.extractor_llm import LLMFactExtractor
from motor.intelligence.memory.forgetting import (
    ConfidenceForgetPolicy,
    ForgettingEngine,
    ForgettingEvent,
    ForgettingResult,
    ForgettingScheduler,
    HybridForgetPolicy,
    ImportanceForgetPolicy,
    NeverForgetPolicy,
    ProtectionRules,
    TTLForgetPolicy,
)
from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.orchestrator import MemoryOrchestrator
from motor.intelligence.memory.record import MemoryRecord, MemoryType
from motor.intelligence.memory.retrieval import ContextQuery, ContextResult, ContextResultList, ContextRetriever
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore, consolidate_episodes


def _episode(
    payload: str = "El sistema es rapido y fiable",
    session: str = "s1",
    ts: str | None = None,
    importance: float = 0.5,
    confidence: float = 0.5,
    tags: list[str] | None = None,
    ttl: int = 31536000,
) -> Episode:
    return Episode(
        session_id=session,
        payload=payload,
        source="unit",
        importance=importance,
        confidence=confidence,
        tags=tags or [],
        timestamp=ts or datetime.now(UTC).isoformat(),
        ttl=ttl,
    )


OLD = "2020-01-01T00:00:00+00:00"
V_OLD = "2019-01-01T00:00:00+00:00"


# ── record ──────────────────────────────────────────────────────────────────


class TestMemoryRecord:
    def test_post_init_defaults(self) -> None:
        r = MemoryRecord(payload="x")
        assert r.id and len(r.id) == 16
        assert r.timestamp
        assert r.metadata["created_at"] == r.timestamp
        assert r.metadata["access_count"] == 0

    def test_post_init_ttl_invalido(self) -> None:
        r = MemoryRecord(ttl=-5)
        assert "created_at" not in r.metadata

    def test_is_expired(self) -> None:
        assert MemoryRecord(ttl=None).is_expired is False
        assert MemoryRecord(ttl=0).is_expired is False
        viejo = MemoryRecord(ttl=1, timestamp="2020-01-01T00:00:00+00:00")
        viejo.metadata["created_at"] = "2020-01-01T00:00:00+00:00"
        assert viejo.is_expired is True

    def test_age_seconds(self) -> None:
        r = MemoryRecord(timestamp="2020-01-01T00:00:00+00:00")
        assert r.age_seconds > 0


# ── episodic ────────────────────────────────────────────────────────────────


class TestEpisode:
    def test_post_init(self) -> None:
        e = Episode()
        assert e.id and e.timestamp
        e2 = Episode(ttl=-1)
        assert e2.ttl == 604800

    def test_is_expired_true(self) -> None:
        e = _episode(ts=OLD, ttl=1)
        assert e.is_expired is True and e.age_seconds > 0

    def test_to_from_record(self) -> None:
        e = _episode(payload="p", tags=["a"])
        rec = e.to_record()
        assert rec.type == MemoryType.EPISODIC
        assert rec.metadata["session_id"] == "s1"
        e2 = Episode.from_record(rec)
        assert e2.id == e.id and e2.session_id == "s1"
        rec2 = MemoryRecord(ttl=0)
        e3 = Episode.from_record(rec2)
        assert e3.ttl == 604800


class TestEpisodeStore:
    def test_store_get_delete(self) -> None:
        s = EpisodeStore()
        e = _episode()
        eid = s.store(e)
        assert s.get(eid) is e
        assert s.get("nope") is None
        assert s.delete(eid) is True
        assert s.delete(eid) is False
        assert s.get(eid) is None

    def test_get_expirado_se_borra(self) -> None:
        s = EpisodeStore()
        e = _episode(ts=OLD, ttl=1)
        eid = s.store(e)
        assert s.get(eid) is None

    def test_is_expired_ttl_invalido(self) -> None:
        e = _episode()
        e.ttl = 0
        assert e.is_expired is False
        assert e.age_seconds >= 0

    def test_store_sin_id_ni_timestamp(self) -> None:
        s = EpisodeStore()
        e = _episode()
        e.id = ""
        e.timestamp = ""
        eid = s.store(e)
        assert eid and s.get(eid) is not None

    def test_load_from_db_conn_none(self) -> None:
        s = EpisodeStore()
        s._load_from_db()

    def test_clear_all_persist(self, tmp_path: Path) -> None:
        db = tmp_path / "ca.db"
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        s.store(_episode(payload="p"))
        s.store(_episode(payload="q"))
        assert s.clear_all() == 2
        s.close()

    def test_persist_delete_error(self, tmp_path: Path) -> None:
        db = tmp_path / "pe.db"
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))

        def boom(*a: Any, **k: Any) -> None:
            raise sqlite3.Error("boom")

        e = _episode(payload="q")
        eid = s.store(e)
        s._conn = types.SimpleNamespace(execute=boom, commit=lambda: None)
        s.delete(eid)
        s._conn = None
        s.close()

    def test_session_y_rango(self) -> None:
        s = EpisodeStore()
        a = _episode(session="sa", ts="2026-01-01T00:00:00+00:00", payload="a")
        b = _episode(session="sb", ts="2025-01-01T00:00:00+00:00", payload="b")
        c = _episode(session="sa", ts="2026-06-01T00:00:00+00:00", payload="c")
        s.store(a)
        s.store(b)
        s.store(c)
        assert s.get_by_session("sa") == [c, a]  # orden timestamp desc
        assert s.get_by_session("sa", limit=1) == [c]
        assert s.get_by_session("sa", offset=1) == [a]
        assert s.get_by_session("sa", limit=0, offset=0) == []
        assert s.get_by_time_range("2025-06-01", "2026-06-01") == [a]
        assert s.get_by_time_range("2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00") == [c, a]
        assert s.get_recent(k=1) == [c]
        assert s.get_recent(k=2) == [c, a]
        assert s.count("sb") == 1
        assert s.count() == 3
        assert s.count("nada") == 0

    def test_clear_ops(self) -> None:
        s = EpisodeStore()
        s.store(_episode(session="sa", ts=OLD, ttl=1))
        s.store(_episode(session="sb"))
        assert s.delete_expired() == 1
        assert s.clear_session("sb") == 1
        s.store(_episode(ts=OLD, ttl=1))
        assert s.clear_all() == 1

    def test_trim(self) -> None:
        s = EpisodeStore(EpisodeStoreConfig(max_episodes=2))
        s.store(_episode(ts="2026-06-01T00:00:00+00:00", payload="x1"))
        s.store(_episode(ts="2026-06-10T00:00:00+00:00", payload="x2"))
        s.store(_episode(ts="2026-08-01T00:00:00+00:00", payload="x3"))
        assert s.count() == 2
        restantes = {e.payload for e in s._episodes.values()}
        assert restantes == {"x2", "x3"}  # el más antiguo (x1) se trima

    def test_persistencia_sqlite(self, tmp_path: Path) -> None:
        db = tmp_path / "eps.db"
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        ep = _episode(payload="hola", tags=["t1"])
        ep.references = ["r1"]
        ep.source = "custom"
        ep.importance = 0.9
        ep.confidence = 0.7
        ep.ttl = 1234
        ep.metadata = {"clave": "valor"}
        eid = s.store(ep)
        s.close()
        s2 = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        e2 = s2.get(eid)
        assert e2 is not None and e2.payload == "hola"
        assert e2.references == ["r1"]
        assert e2.tags == ["t1"]
        assert e2.source == "custom"
        assert e2.importance == 0.9
        assert e2.confidence == 0.7
        assert e2.ttl == 1234
        assert e2.metadata == {"clave": "valor"}
        assert e2.session_id == "s1"
        assert s2.count() == 1
        s2.delete(eid)
        s2.close()
        assert sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 0

    def test_db_corrupt_se_recrea(self, tmp_path: Path) -> None:
        db = tmp_path / "corrupt.db"
        db.write_bytes(b"no es una base de datos")
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        assert s._conn is not None
        s.store(_episode(payload="ok"))
        assert s.count() == 1
        s.close()

    def test_fila_corrupta_en_db(self, tmp_path: Path) -> None:
        db = tmp_path / "rows.db"
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        s._conn.execute(
            "INSERT INTO episodes (id, session_id, timestamp, tags, refs, metadata) VALUES (?,?,?,?,?,?)",
            ("bad", "sx", "2026-01-01", "no-json", "no-json", "no-json"),
        )
        s._conn.commit()
        s3 = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))
        assert s3.count() == 0
        s.close()
        s3.close()

    def test_persist_error_logueado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db = tmp_path / "err.db"
        s = EpisodeStore(EpisodeStoreConfig(persist_path=str(db)))

        def boom(*a: Any, **k: Any) -> None:
            raise sqlite3.Error("disco lleno")

        fake_conn = types.SimpleNamespace(execute=boom, commit=lambda: None, close=lambda: None)
        s._conn = fake_conn
        eid = s.store(_episode(payload="x"))
        assert eid
        s.close()


class TestSessionMemory:
    def test_flujo(self) -> None:
        sm = SessionMemory()
        sid = sm.create_session(metadata={"tema": "ia"})
        sid2 = sm.create_session()
        assert sid != sid2
        assert sm.session_count() == 2
        ep = sm.add_episode(sid, "payload", source="s", tags=["x"], importance=0.8)
        assert ep.id
        assert ep.importance == 0.8
        assert sm.get_history(sid) == [ep]
        assert sm.get_recent(k=5)
        assert sm.store.count(sid) == 1
        assert sm.close_session(sid) is True
        assert sm.close_session(sid) is False
        assert sm.session_count() == 1

    def test_add_episode_sin_sesion_activa(self) -> None:
        """add_episode con sesión no creada → episodio se guarda igual."""
        sm = SessionMemory()
        ep = sm.add_episode("no-existe", "payload")
        assert ep.id
        assert sm.store.count("no-existe") == 1
        assert sm.get_history("no-existe") == [ep]

    def test_create_session_con_id(self) -> None:
        """create_session con id explícito no genera otro."""
        sm = SessionMemory()
        sid = sm.create_session(session_id="fijo")
        assert sid == "fijo"
        assert sm.session_count() == 1


# ── semantic ────────────────────────────────────────────────────────────────


class TestSemanticFact:
    def test_post_init_y_merge(self) -> None:
        f = SemanticFact("a", "b", "c")
        assert f.id and f.created_at and f.updated_at
        assert f.key == "a|b|c"
        other = SemanticFact("a", "b", "c", confidence=0.9, importance=0.8, source_episode_ids=["e9"], tags=["t9"])
        f.merge(other)
        assert f.confidence == 0.9 and f.importance == 0.8
        assert f.version == 2
        assert f.source_episode_ids == ["e9"]
        assert f.tags == ["t9"]
        d = f.to_dict()
        assert d["source_episodes"] == 1 and d["version"] == 2


class TestSemanticMemoryStore:
    def test_crud(self) -> None:
        s = SemanticMemoryStore()
        f = SemanticFact("A", "es", "B", confidence=0.7)
        fid = s.store(f)
        assert s.get(fid) is f
        assert s.get_by_key("A", "es", "B") is f
        assert s.get("nada") is None
        assert s.delete(fid) is True
        assert s.delete(fid) is False
        assert s.count() == 0

    def test_merge_en_store(self) -> None:
        s = SemanticMemoryStore()
        id1 = s.store(SemanticFact("A", "es", "B", confidence=0.5))
        id2 = s.store(SemanticFact("A", "es", "B", confidence=0.9))
        assert id1 == id2
        assert s.get(id1) is not None and s.get(id1).confidence == 0.9  # type: ignore[union-attr]

    def test_search_filtros(self) -> None:
        s = SemanticMemoryStore()
        s.store(SemanticFact("Python", "es", "lenguaje", tags=["prog"], fact_type="relation", importance=0.9))
        s.store(SemanticFact("Gato", "come", "pescado", tags=["animal"], fact_type="event", importance=0.5))
        s.store(SemanticFact("python", "es", "snake", fact_type="relation", importance=0.3))
        assert len(s.search(text="python")) == 2  # case-insensitive, subject y object
        assert len(s.search(tags=["animal"])) == 1
        assert len(s.search(fact_type="relation")) == 2
        assert len(s.search(entity="gato")) == 1
        assert len(s.search(entity="Python")) == 2  # case-insensitive
        assert len(s.search(text="zzz", k=10)) == 0
        orden = s.search(text="python")
        assert orden[0].importance == 0.9  # ordenado por importance desc
        assert len(s.search(text="python", k=1)) == 1  # límite k

    def test_persistencia(self, tmp_path: Path) -> None:
        db = tmp_path / "facts.db"
        s = SemanticMemoryStore(str(db))
        f = SemanticFact("X", "es", "Y", tags=["t"], confidence=0.8, importance=0.9)
        f.source_episode_ids = ["e1", "e2"]
        f.metadata = {"fuente": "test"}
        f.version = 3
        fid = s.store(f)
        s.close()
        s2 = SemanticMemoryStore(str(db))
        g = s2.get(fid)
        assert g is not None
        assert g.subject == "X"
        assert g.predicate == "es"
        assert g.object_value == "Y"
        assert g.tags == ["t"]
        assert g.confidence == 0.8
        assert g.importance == 0.9
        assert g.source_episode_ids == ["e1", "e2"]
        assert g.metadata == {"fuente": "test"}
        assert g.version == 3
        assert g.fact_type == "relation"
        assert s2.get_by_key("X", "es", "Y") is g
        assert s2.count() == 1
        assert s2.clear_all() == 1
        s2.close()

    def test_fila_corrupta(self, tmp_path: Path) -> None:
        db = tmp_path / "fc.db"
        s = SemanticMemoryStore(str(db))
        s._conn.execute(
            "INSERT INTO semantic_facts (id, subject, predicate, obj, tags, metadata) VALUES (?,?,?,?,?,?)",
            ("bad", "a", "b", "c", "no-json", "no-json"),
        )
        s._conn.commit()
        s.close()
        s2 = SemanticMemoryStore(str(db))
        assert s2.count() == 0
        s2.close()

    def test_persist_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        s = SemanticMemoryStore(str(tmp_path / "pe.db"))

        def boom(*a: Any, **k: Any) -> None:
            raise sqlite3.Error("boom")

        s._conn = types.SimpleNamespace(execute=boom, commit=lambda: None, close=lambda: None)
        s.store(SemanticFact("A", "b", "c"))
        s.delete("inexistente")
        s.close()

    def test_load_from_db_conn_none(self) -> None:
        s = SemanticMemoryStore()
        s.close()
        s._load_from_db()

    def test_persist_delete_error(self, tmp_path: Path) -> None:
        db = tmp_path / "pde.db"
        s = SemanticMemoryStore(str(db))

        def boom(*a: Any, **k: Any) -> None:
            raise sqlite3.Error("boom")

        f = SemanticFact("A", "b", "c")
        fid = s.store(f)
        assert s.delete(fid) is True
        f2 = SemanticFact("A", "b", "c")
        fid2 = s.store(f2)
        s._conn = types.SimpleNamespace(execute=boom, commit=lambda: None)
        s.delete(fid2)
        s._conn = None
        s.close()


def test_consolidate_episodes() -> None:
    s = SemanticMemoryStore()
    rbx = RuleBasedFactExtractor()
    n = consolidate_episodes([_episode(payload="El sistema es rapido y fiable")], s, rbx)
    assert n >= 1 and s.count() == n


# ── retrieval ───────────────────────────────────────────────────────────────


class TestContextRetriever:
    def test_search_by_session_y_global(self) -> None:
        st = EpisodeStore()
        st.store(_episode(session="sa", payload="x", ts="2026-01-01T00:00:00+00:00", importance=0.9))
        st.store(_episode(session="sb", payload="y", ts="2026-07-01T00:00:00+00:00"))
        r = ContextRetriever(st)
        res = r.search(ContextQuery(session_id="sa", k=5))
        assert res.total == 1 and len(res) == 1
        res2 = r.search(ContextQuery(text="x", k=5))
        assert res2.total == 2
        assert res2[0].rank == 0

    def test_filtros_tags_y_offset(self) -> None:
        st = EpisodeStore()
        e1 = _episode(session="s", payload="a", tags=["t1"], ts="2026-01-01T00:00:00+00:00")
        e2 = _episode(session="s", payload="b", tags=["t2"], ts="2026-07-01T00:00:00+00:00")
        st.store(e1)
        st.store(e2)
        r = ContextRetriever(st)
        res = r.search(ContextQuery(session_id="s", tags=["t2"], offset=0, k=1))
        assert res.total == 1 and res[0].episode is e2

    def test_expirados_se_limpian(self) -> None:
        st = EpisodeStore()
        e = _episode(ts=OLD, ttl=1)
        eid = st.store(e)
        r = ContextRetriever(st)
        res = r.search(ContextQuery())
        assert res.total == 0
        assert st.get(eid) is None

    def test_is_expired_ttl_invalido(self) -> None:
        st = EpisodeStore()
        e = _episode(session="si", payload="x", ts="2026-08-01T00:00:00+00:00")
        e.ttl = 0
        st.store(e)
        r = ContextRetriever(st)
        res = r.search(ContextQuery(session_id="si"))
        assert res.total == 1

    def test_expirado_en_sesion_se_borra(self) -> None:
        st = EpisodeStore()
        e = _episode(session="sx", payload="y", ts=OLD, ttl=1)
        eid = st.store(e)
        r = ContextRetriever(st)
        res = r.search(ContextQuery(session_id="sx"))
        assert res.total == 0
        assert st.get(eid) is None

    def test_is_expired_directo(self) -> None:
        st = EpisodeStore()
        r = ContextRetriever(st)
        e = _episode(ts=OLD, ttl=1)
        assert r._is_expired(e) is True
        assert st.count() == 0
        e2 = _episode()
        assert r._is_expired(e2) is False

    def test_recency_futuro(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="z", ts="2099-01-01T00:00:00+00:00"))
        r = ContextRetriever(st)
        res = r.search(ContextQuery())
        assert res[0].recency_score == 1.0

    def test_semantic_score_positivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        st = EpisodeStore()
        ep = _episode(payload="x", ts="2026-08-01T00:00:00+00:00")
        ep.embedding = [0.1, 0.2]  # type: ignore[attr-defined]
        st.store(ep)
        r = ContextRetriever(st, weights={"semantic": 1.0, "recency": 0, "importance": 0, "confidence": 0})
        monkeypatch.setattr(ContextRetriever, "_semantic_score", lambda self, q, emb: 0.5)
        res = r.search(ContextQuery(text="x"))
        cr = res[0]
        assert cr.semantic_score == 0.5
        assert "sem=0.50" in cr.explanation

    def test_weights_y_explanation(self) -> None:
        st = EpisodeStore()
        ep = _episode(payload="x", ts="2026-08-10T00:00:00+00:00", importance=0.9, confidence=0.9)
        ep.embedding = [0.1, 0.2]  # type: ignore[attr-defined]
        st.store(ep)
        ep2 = _episode(payload="v", ts="2026-01-01T00:00:00+00:00", importance=0.1, confidence=0.1)
        ep2.embedding = [0.9, 0.1]  # type: ignore[attr-defined]
        st.store(ep2)
        r = ContextRetriever(st, weights={"semantic": 0.5, "recency": 0.2, "importance": 0.2, "confidence": 0.1})
        res = r.search(ContextQuery(text="x", k=1, weights=None))
        cr = res[0]
        assert cr.semantic_score == 0.0
        assert cr.recency_score == pytest.approx(1.0, rel=0.05)
        assert "score=" in cr.explanation
        assert res.to_dict()[0]["id"]

    def test_weights_vacias(self) -> None:
        st = EpisodeStore()
        st.store(_episode(ts="2026-01-01T00:00:00+00:00"))
        r = ContextRetriever(st)
        res = r.search(ContextQuery(weights={"semantic": 1.0}))
        assert res.total == 1
        assert res[0].semantic_score == 0.0

    def test_result_list_api(self) -> None:
        e = _episode()
        rl = ContextResultList(results=[ContextResult(episode=e, score=1.0)], total=1, elapsed_ms=1.0)
        assert len(rl) == 1
        assert rl[0].episode is e
        d = rl.to_dict()
        assert d[0]["payload"] == e.payload


# ── compression ─────────────────────────────────────────────────────────────


class TestCompression:
    def test_never_compress(self) -> None:
        p = NeverCompress()
        assert p.should_run(EpisodeStore()) is False
        assert p.select_candidates(EpisodeStore()) == []
        assert p.delete_originals is False

    def test_age_based(self) -> None:
        st = EpisodeStore()
        st.store(_episode(ts="2026-06-01T00:00:00+00:00", payload="viejo"))
        st.store(_episode(ts="2026-08-01T00:00:00+00:00", payload="nuevo"))
        p = AgeBasedCompression(max_age_days=30, delete_after_compress=True)
        assert p.should_run(st) is True
        cands = p.select_candidates(st)
        assert len(cands) == 1 and cands[0].payload == "viejo"
        assert p.delete_originals is True

    def test_size_based(self) -> None:
        st = EpisodeStore()
        for i, m in enumerate(("2026-05-01", "2026-06-01", "2026-07-01")):
            st.store(_episode(ts=f"{m}T00:00:00+00:00", payload=f"p{i}"))
        p = SizeBasedCompression(max_episodes=1)
        assert p.should_run(st) is True
        cands = p.select_candidates(st)
        assert len(cands) == 2
        assert SizeBasedCompression(max_episodes=99).should_run(st) is False
        assert SizeBasedCompression(max_episodes=99).select_candidates(st) == []

    def test_hybrid_policy(self) -> None:
        st = EpisodeStore()
        st.store(_episode(ts="2026-06-01T00:00:00+00:00", payload="a"))
        st.store(_episode(ts="2024-01-01T00:00:00+00:00", payload="b"))
        st.store(_episode(ts="2026-01-01T00:00:00+00:00", payload="c"))
        hp = HybridCompressionPolicy(max_age_days=30, max_episodes=1)
        assert hp.should_run(st) is True
        cands = hp.select_candidates(st)
        assert len(cands) == 2
        assert len({c.id for c in cands}) == 2
        assert hp.delete_originals is False

    def test_compressor_never(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="x"))
        c = MemoryCompressor(st, NeverCompress())
        res = c.compress()
        assert res.summaries_created == 0

    def test_size_based_delete_originals(self) -> None:
        assert SizeBasedCompression(max_episodes=1).delete_originals is False

    def test_generate_summary_vacio(self) -> None:
        c = MemoryCompressor(EpisodeStore())
        assert c._generate_summary("s", []) is None

    def test_compressor_error_generando(self, monkeypatch: pytest.MonkeyPatch) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="x", ts="2026-06-01T00:00:00+00:00", session="e"))

        def boom(*a: Any, **k: Any) -> Any:
            raise RuntimeError("summary fail")

        monkeypatch.setattr(MemoryCompressor, "_generate_summary", boom)
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        res = c.compress()
        assert res.summaries_created == 0
        assert len(res.errors) == 1

    def test_compressor_sin_candidatos(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="x", ts="2026-08-10T00:00:00+00:00"))
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        res = c.compress()
        assert res.summaries_created == 0 and res.elapsed_ms >= 0

    def test_compressor_ok_sin_borrar(self) -> None:
        st = EpisodeStore()
        e1 = _episode(payload="uno", ts="2026-06-01T00:00:00+00:00", session="s9")
        e2 = _episode(payload="dos", ts="2026-04-01T00:00:00+00:00", session="s9")
        st.store(e1)
        st.store(e2)
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30, delete_after_compress=False))
        res = c.compress()
        assert res.summaries_created == 1
        assert res.episodes_compressed == 2
        assert res.episodes_deleted == 0
        assert st.count() == 2
        sums = c.get_summaries(session_id="s9")
        assert len(sums) == 1
        assert c.count_summaries() == 1
        assert c.get_summary(sums[0].id) is sums[0]
        assert c.get_summaries(session_id="otra") == []
        assert c.clear_summaries() == 1

    def test_compressor_borrando(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="x", ts="2026-06-01T00:00:00+00:00", session="s"))
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30, delete_after_compress=True))
        res = c.compress()
        assert res.episodes_deleted == 1 and st.count() == 0

    def test_compressor_payload_vacio(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="", ts="2026-06-01T00:00:00+00:00", session="s"))
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        res = c.compress()
        assert res.summaries_created == 0

    def test_compressor_sin_sesion(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="a\nb", ts="2026-06-01T00:00:00+00:00", session=""))
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        res = c.compress()
        assert res.summaries_created == 1
        assert res.summaries[0].get("session_id") if False else True

    def test_policy_setter_y_scheduler(self) -> None:
        st = EpisodeStore()
        c = MemoryCompressor(st)
        assert isinstance(c.policy, SizeBasedCompression)
        c.policy = NeverCompress()
        assert isinstance(c.policy, NeverCompress)
        sch = CompressionScheduler(c)
        assert sch.enabled is False
        sch.enable()
        assert sch.enabled is True
        sch.disable()
        assert sch.enabled is False
        assert sch.run_once().summaries_created == 0

    def test_summary_record_defaults(self) -> None:
        s = SummaryRecord(source_episode_ids=["a"], summary="x")
        assert s.id and s.created_at


# ── forgetting ──────────────────────────────────────────────────────────────


class TestProtection:
    def test_protection_rules(self) -> None:
        p = ProtectionRules()
        p.protect("a")
        p.pin("b")
        assert p.is_protected("a") and p.is_pinned("b")
        assert p.count_protected() == 1 and p.count_pinned() == 1
        assert p.unprotect("a") is True and p.unprotect("a") is False
        assert p.unpin("b") is True and p.unpin("b") is False

    def test_event_y_result(self) -> None:
        ev = ForgettingEvent("r", "episode", "razon", "ttl", "2026-01-01", 0.5, 3.0)
        d = ev.to_dict()
        assert d["age_days"] == 3.0
        res = ForgettingResult(episodes_removed=1, facts_removed=2)
        assert res.total_removed == 3


class TestForgetPolicies:
    def test_never(self) -> None:
        p = NeverForgetPolicy()
        assert p.name() == "never_forget"
        assert p.should_forget(_episode(), None) == (False, "policy_never_forget")  # type: ignore[arg-type]

    def test_ttl(self) -> None:
        ctx = None
        p = TTLForgetPolicy()
        ep = _episode()
        ep.ttl = 0
        assert p.should_forget(ep, ctx) == (False, "no_ttl")
        assert p.should_forget(_episode(ts=OLD, ttl=1), ctx) == (True, "ttl_expired_1s")
        assert p.should_forget(_episode(), ctx) == (False, "ttl_expired_31536000s")
        assert p.should_forget(SemanticFact("a", "b", "c"), ctx) == (False, "semantic_no_ttl")
        assert p.should_forget("otra cosa", ctx) == (False, "unknown")

    def test_importance(self) -> None:
        p = ImportanceForgetPolicy(min_importance=0.5, min_age_days=30)
        assert p.name() == "importance"
        assert p.should_forget(_episode(importance=0.9), None) == (False, "importance_0.9_above_0.5")
        joven = _episode(importance=0.1, ts="2026-08-10T00:00:00+00:00")
        assert p.should_forget(joven, None)[0] is False
        viejo = _episode(importance=0.1, ts=OLD)
        assert p.should_forget(viejo, None) == (True, "importance_0.1_below_0.5")
        assert p.should_forget(SemanticFact("a", "b", "c", importance=0.9), None)[0] is False
        assert p.should_forget(SemanticFact("a", "b", "c", importance=0.1), None)[0] is True
        assert p.should_forget("x", None) == (False, "unknown")

    def test_confidence(self) -> None:
        p = ConfidenceForgetPolicy(min_confidence=0.5)
        assert p.name() == "confidence"
        assert p.should_forget(_episode(confidence=0.9), None)[0] is False
        assert p.should_forget(_episode(confidence=0.1), None)[0] is True
        assert p.should_forget(SemanticFact("a", "b", "c", confidence=0.1), None)[0] is True
        assert p.should_forget(SemanticFact("a", "b", "c", confidence=0.9), None) == (False, "confidence_0.9_above_0.5")
        assert p.should_forget("x", None) == (False, "unknown")

    def test_hybrid(self) -> None:
        h = HybridForgetPolicy(require_all=False)
        assert h.name() == "hybrid"
        ok, reason = h.should_forget(_episode(ts=OLD, ttl=1), None)
        assert ok and "ttl" in reason
        h2 = HybridForgetPolicy(require_all=True)
        ok2, _ = h2.should_forget(_episode(ts=OLD, ttl=1), None)
        assert ok2 is False


class TestForgettingEngine:
    def _setup(self) -> tuple[EpisodeStore, SemanticMemoryStore, list]:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        summary = SummaryRecord(source_episode_ids=["zzz"], summary="s")
        return st, sm, [summary]

    def test_proteccion_y_referencias(self) -> None:
        st, sm, _ = self._setup()
        prot = ProtectionRules()
        viejo = _episode(payload="viejo", ts=OLD, ttl=1)
        prot.protect(viejo.id)
        st.store(viejo)
        ref = _episode(payload="ref", ts=OLD, ttl=1, session="rr")
        st.store(ref)
        summary = SummaryRecord(source_episode_ids=[ref.id], summary="x")
        eng = ForgettingEngine(st, sm, [summary], policies=[TTLForgetPolicy()], protection=prot)
        res = eng.run()
        assert res.protected_skipped == 1
        assert res.referenced_skipped == 1

    def test_borra_y_dry_run(self) -> None:
        st, sm, _ = self._setup()
        e = _episode(payload="x", ts=OLD, ttl=1)
        st.store(e)
        eng = ForgettingEngine(st, sm, [], policies=[TTLForgetPolicy()])
        res = eng.simulate()
        assert res.episodes_removed == 1
        assert st.count() == 1
        res2 = eng.run()
        assert res2.episodes_removed == 1 and st.count() == 0
        assert res2.details[0].policy == "ttl"
        assert res2.total_evaluated == 1

    def test_pinned_y_factos(self) -> None:
        st, sm, _ = self._setup()
        p = ProtectionRules()
        f = SemanticFact("u", "es", "v", importance=0.1)
        fid = sm.store(f)
        p.pin(fid)
        ep = _episode(payload="x", ts=OLD, ttl=1)
        p.pin(ep.id)
        st.store(ep)
        eng = ForgettingEngine(st, sm, [], policies=[ImportanceForgetPolicy(min_importance=0.5)], protection=p)
        res = eng.run()
        assert res.pinned_skipped == 2
        assert res.facts_removed == 0

    def test_borra_factos(self) -> None:
        st, sm, _ = self._setup()
        f = SemanticFact("u", "es", "v", importance=0.1)
        sm.store(f)
        eng = ForgettingEngine(st, sm, [], policies=[ImportanceForgetPolicy(min_importance=0.5)])
        res = eng.run(dry_run=True)
        assert res.facts_removed == 1
        assert sm.count() == 1
        res2 = eng.run()
        assert res2.facts_removed == 1 and sm.count() == 0
        assert res2.details[0].record_type == "semantic_fact"

    def test_sin_semantic_store_y_stats(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="n", ts=OLD, ttl=1))
        eng = ForgettingEngine(st, None, [], policies=[TTLForgetPolicy()])
        res = eng.run()
        assert res.episodes_removed == 1
        stat = eng.stats()
        assert stat["episodes_total"] == 0
        sch = ForgettingScheduler(eng)
        assert sch.enabled is False
        sch.enable()
        assert sch.enabled is True
        sch.disable()
        assert sch.run_once(dry_run=True).total_evaluated == 0

    def test_store_anulado_no_evita_facts(self) -> None:
        st = EpisodeStore()
        eng = ForgettingEngine(st, None, [], policies=[TTLForgetPolicy()])
        eng._semantic_store = None
        res = eng.run()
        assert res.facts_removed == 0
        assert res.episodes_removed == 0

    def test_fact_protegido(self) -> None:
        st, sm, _ = self._setup()
        f = SemanticFact("u", "es", "v", importance=0.1)
        fid = sm.store(f)
        prot = ProtectionRules()
        prot.protect(fid)
        eng = ForgettingEngine(st, sm, [], policies=[ImportanceForgetPolicy(min_importance=0.5)], protection=prot)
        res = eng.run()
        assert res.protected_skipped >= 1
        assert sm.count() == 1

    def test_batch_size(self) -> None:
        st = EpisodeStore()
        for i in range(3):
            st.store(_episode(payload=f"x{i}", ts=OLD, ttl=1))
        eng = ForgettingEngine(st, None, [], policies=[TTLForgetPolicy()], batch_size=1)
        res = eng.run()
        assert res.episodes_removed == 1
        assert eng.stats()["episodes_total"] == 2

    def test_age_seconds_invalido(self) -> None:
        from motor.intelligence.memory.forgetting import _age_seconds

        assert _age_seconds("timestamp-raro") == 0.0


# ── extractor y extractor_llm ───────────────────────────────────────────────


class TestRuleBasedFactExtractor:
    def test_vacio(self) -> None:
        assert RuleBasedFactExtractor().extract(_episode(payload="")) == []

    def test_patrones(self) -> None:
        r = RuleBasedFactExtractor()
        ep = _episode(payload="El servidor es rapido en produccion")
        facts = r.extract(ep)
        assert facts
        f = facts[0]
        assert f.subject == "sistema"
        assert f.predicate == "servidor"
        assert f.object_value == "rapido"
        assert f.fact_type == "attribute"
        assert f.source_episode_ids == [ep.id]
        assert f.metadata["session_id"] == "s1"
        assert f.confidence == pytest.approx(0.45)
        assert f.importance == 0.5
        assert f.tags == []
        assert f.key == "sistema|servidor|rapido"

    def test_patron_relation(self) -> None:
        r = RuleBasedFactExtractor()
        facts = r.extract(_episode(payload="El robot tiene dos brazos"))
        assert facts
        f = facts[0]
        assert f.fact_type == "relation"
        assert f.predicate == "tiene"
        assert f.object_value == "dos brazos"

    def test_patron_event(self) -> None:
        r = RuleBasedFactExtractor()
        facts = r.extract(_episode(payload="la puerta se abrio lentamente"))
        assert facts
        f = facts[0]
        assert f.fact_type == "event"
        assert f.predicate == "abrio"

    def test_patron_error(self) -> None:
        r = RuleBasedFactExtractor()
        facts = r.extract(_episode(payload="Error: conexion perdida"))
        assert facts
        f = facts[0]
        assert f.fact_type == "error"
        assert f.object_value == "conexion perdida"

    def test_patron_statement(self) -> None:
        r = RuleBasedFactExtractor()
        facts = r.extract(_episode(payload="El sistema dice que todo ok"))
        assert facts
        f = facts[0]
        assert f.fact_type == "statement"
        assert f.object_value == "todo ok"

    def test_patron_config(self) -> None:
        r = RuleBasedFactExtractor()
        facts = r.extract(_episode(payload="Configuracion puerto = 8080"))
        assert facts
        assert facts[0].fact_type == "attribute"
        assert facts[0].object_value == "8080"

    def test_patron_make_fact_con_error(self) -> None:
        r = RuleBasedFactExtractor()
        ep = _episode(payload="Error: algo", tags=["t1"], importance=0.8)
        facts = r.extract(ep)
        assert facts
        f = facts[0]
        assert f.tags == ["t1"]
        assert f.importance == 0.8
        assert f.metadata["session_id"] == "s1"

    def test_multiples_patrones(self) -> None:
        r = RuleBasedFactExtractor()
        text = "Error: conexion perdida. El robot tiene dos brazos. la puerta se abrio lentamente. Configuracion puerto = 8080. El sistema dice que todo ok"
        facts = r.extract(_episode(payload=text))
        assert len(facts) >= 5
        assert any(f.fact_type == "error" for f in facts)
        assert any(f.fact_type == "relation" and f.object_value.startswith("dos brazos") for f in facts)
        assert any(f.fact_type == "event" for f in facts)
        assert any(f.fact_type == "attribute" for f in facts)

    def test_parse_json_invalido(self) -> None:
        llm = LLMFactExtractor()
        ep = _episode(payload="p")
        assert llm._parse_response("h1m7 no es json", ep) == []


class TestLLMFactExtractor:
    def test_vacio(self) -> None:
        assert LLMFactExtractor().extract(_episode(payload="")) == []

    def test_extract_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.intelligence.memory.extractor_llm as mod

        payload = '[{"subject": "A", "predicate": "es", "object": "B", "type": "relation"}]'
        monkeypatch.setattr(mod, "generate", lambda *a, **k: payload)
        facts = LLMFactExtractor().extract(_episode(payload="texto"))
        assert len(facts) == 1
        assert facts[0].subject == "A" and facts[0].predicate == "es"
        assert facts[0].confidence == pytest.approx(0.4)

    def test_extract_error_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.intelligence.memory.extractor_llm as mod

        monkeypatch.setattr(mod, "generate", lambda *a, **k: "Error: modelo caido")
        assert LLMFactExtractor().extract(_episode(payload="x")) == []

    def test_extract_excepcion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.intelligence.memory.extractor_llm as mod

        def boom(*a: Any, **k: Any) -> None:
            raise RuntimeError("generate roto")

        monkeypatch.setattr(mod, "generate", boom)
        assert LLMFactExtractor().extract(_episode(payload="x")) == []

    def test_prompt_y_parse(self) -> None:
        llm = LLMFactExtractor(model="m1")
        assert llm._model == "m1"
        assert "Extract facts" in llm._build_prompt("texto")
        ep = _episode(payload="p")
        assert llm._parse_response("```json\n[]\n```", ep) == []
        assert llm._parse_response('{"a": 1}', ep) == []
        assert (
            llm._parse_response('[{"subject": "s", "predicate": "p", "object": "o", "type": "t"}, "no-dict"]', ep)[0]
            is not None
        )
        assert llm._parse_response('[{"subject": "s", "predicate": "p", "object": "o"}]', ep)[0] is not None
        assert llm._parse_response('[{"subject": "solo"}]', ep) == []

    def test_fallback_parse(self) -> None:
        llm = LLMFactExtractor()
        items = llm._fallback_parse('lorem {"subject": "A"} ipsum {"subject": "B"}')
        assert items == [{"subject": "A"}, {"subject": "B"}]
        assert llm._fallback_parse("sin nada") == []


# ── orchestrator ────────────────────────────────────────────────────────────


class TestMemoryOrchestrator:
    def test_sin_extractor(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        o = MemoryOrchestrator(st, sm)
        assert o.consolidate() == 0

    def test_consolidate(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        o = MemoryOrchestrator(st, sm, extractor=RuleBasedFactExtractor())
        assert o.consolidate() == 0
        st.store(_episode(payload="El sistema es rapido en produccion"))
        n = o.consolidate(batch_size=5)
        assert n >= 1 and sm.count() == n

    def test_compress_y_forget(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        comp = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        o = MemoryOrchestrator(st, sm, compressor=comp)
        assert o.compress() == 0
        st.store(_episode(payload="x", ts="2026-06-01T00:00:00+00:00"))
        assert o.compress() == 1
        st.store(_episode(payload="z", ts="2026-08-10T00:00:00+00:00", ttl=31536000))
        o2 = MemoryOrchestrator(st, sm, forgetting_engine=ForgettingEngine(st, sm))
        assert o2.forget() == {"removed": 0, "dry_run": False}
        eng = ForgettingEngine(st, sm, policies=[TTLForgetPolicy()])
        st.store(_episode(payload="y", ts=OLD, ttl=1))
        o3 = MemoryOrchestrator(st, sm, forgetting_engine=eng)
        r = o3.run_all(dry_run=True)
        assert r["forgotten"] == 1

    def test_forget_removed(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        st.store(_episode(ts=OLD, ttl=1))
        eng = ForgettingEngine(st, sm, policies=[TTLForgetPolicy()])
        o = MemoryOrchestrator(st, sm, forgetting_engine=eng)
        assert o.forget()["removed"] == 1

    def test_forget_sin_engine(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        o = MemoryOrchestrator(st, sm)
        assert o.forget() == {"removed": 0, "dry_run": False}
        assert o.forget(dry_run=True) == {"removed": 0, "dry_run": True}


# ── ramas parciales 100x100 (TASK-20260814-001) ─────────────────────────────


class TestRamasCompression:
    def test_summary_record_ids_provistos(self) -> None:
        s = SummaryRecord(source_episode_ids=["a"], summary="x", id="id1", created_at="2026-01-01T00:00:00+00:00")
        assert s.id == "id1"
        assert s.created_at == "2026-01-01T00:00:00+00:00"

    def test_get_summaries_sin_session(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="uno", ts="2026-06-01T00:00:00+00:00", session="s9"))
        st.store(_episode(payload="dos", ts="2026-04-01T00:00:00+00:00", session="s10"))
        c = MemoryCompressor(st, AgeBasedCompression(max_age_days=30))
        res = c.compress()
        assert res.summaries_created == 2
        assert len(c.get_summaries()) == 2
        assert len(c.get_summaries(session_id="s9")) == 1


class TestRamasEpisodic:
    def test_store_sin_sesion_activa(self) -> None:
        st = EpisodeStore()
        eid = st.store(_episode(payload="y", session="solo"))
        assert eid
        assert st.get(eid) is not None

    def test_add_episode_sesion_no_activa(self) -> None:
        sm = SessionMemory()
        ep = sm.add_episode("no-activa", "contenido")
        assert ep.id
        assert sm._active_sessions.get("no-activa") is None


class TestRamasExtractor:
    def test_make_fact_falsy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rbx = RuleBasedFactExtractor()
        monkeypatch.setattr(rbx, "_make_fact", lambda *a, **k: None)
        ep = _episode(payload="El servidor es rapido en produccion")
        assert rbx.extract(ep) == []


class TestRamasForgetting:
    def test_facto_sin_decision(self) -> None:
        st, sm, _ = TestForgettingEngine()._setup()
        sm.store(SemanticFact("u", "es", "v", importance=0.9, confidence=0.9))
        eng = ForgettingEngine(
            st,
            sm,
            [],
            policies=[ImportanceForgetPolicy(min_importance=0.5), ConfidenceForgetPolicy()],
        )
        res = eng.run()
        assert res.facts_removed == 0

    def test_policy_sin_decision_loop(self) -> None:
        st = EpisodeStore()
        st.store(_episode(payload="nuevo", ts="2026-08-10T00:00:00+00:00"))
        eng = ForgettingEngine(
            st,
            None,
            [],
            policies=[TTLForgetPolicy(), ImportanceForgetPolicy(min_importance=0.5)],
        )
        res = eng.run()
        assert res.episodes_removed == 0


class TestRamasHybrid:
    def test_db_path_sin_parent(self) -> None:
        mem = HybridMemory(db_path=":memory:")
        conn = mem._get_conn()
        assert conn is not None
        mem.close()


class TestRamasOrchestrator:
    def test_consolidate_sin_factos(self) -> None:
        st = EpisodeStore()
        sm = SemanticMemoryStore()
        st.store(_episode(payload="texto sin patrones de extraccion"))
        o = MemoryOrchestrator(st, sm, extractor=RuleBasedFactExtractor())
        assert o.consolidate() == 0


class TestRamasSemantic:
    def test_merge_sin_duplicados_previos(self) -> None:
        f = SemanticFact("a", "b", "c", source_episode_ids=["e1"], tags=["t1"])
        other = SemanticFact("a", "b", "c", source_episode_ids=["e2"], tags=["t2"])
        f.merge(other)
        assert f.source_episode_ids == ["e1", "e2"]
        assert f.tags == ["t1", "t2"]

    def test_merge_con_duplicados(self) -> None:
        f = SemanticFact("a", "b", "c", source_episode_ids=["e1", "e2"], tags=["t1", "t2"])
        other = SemanticFact("a", "b", "c", source_episode_ids=["e2", "e3"], tags=["t2", "t3"])
        f.merge(other)
        assert f.source_episode_ids == ["e1", "e2", "e3"]
        assert f.tags == ["t1", "t2", "t3"]

    def test_clear_all_sin_conn(self) -> None:
        s = SemanticMemoryStore()
        s.store(SemanticFact("A", "es", "B"))
        s.close()
        assert s.clear_all() == 1
        assert s.count() == 0
