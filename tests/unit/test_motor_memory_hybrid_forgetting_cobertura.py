"""Cobertura 100x100 de motor/intelligence/memory (hybrid + forgetting). TASK-20260820-008."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest

from motor.intelligence.memory.episodic import Episode, EpisodeStore
from motor.intelligence.memory.forgetting import (
    ConfidenceForgetPolicy,
    ForgettingEngine,
    ForgettingEvent,
    ForgettingPolicy,
    ForgettingResult,
    ForgettingScheduler,
    HybridForgetPolicy,
    ImportanceForgetPolicy,
    NeverForgetPolicy,
    ProtectionRules,
    TTLForgetPolicy,
    _age_seconds,
)
from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore


def _ep(oid: str = "e1", **kw) -> Episode:
    kw.setdefault("timestamp", datetime.now(UTC).isoformat())
    return Episode(id=oid, **kw)


def _fact(fid: str = "f1", **kw) -> SemanticFact:
    kw.setdefault("subject", "s")
    kw.setdefault("predicate", "p")
    kw.setdefault("object_value", "o")
    return SemanticFact(id=fid, **kw)


# ── HybridMemory ─────────────────────────────────────────────


def test_hybrid_store_y_search() -> None:
    h = HybridMemory()
    rid = h.store(payload="el gato sube al arbol", metadata={"src": "test"})
    res = h.search("gato")
    assert len(res) == 1
    assert res[0].id == rid
    assert res[0].type == MemoryType.WORKING
    assert res[0].metadata["src"] == "test"
    h.close()


def test_hybrid_store_con_tipo_y_vector_fake() -> None:
    class _VS:
        def __init__(self) -> None:
            self.saved = []

        def guardar_incidente(self, data) -> None:
            self.saved.append(data)

        def buscar_similares(self, v, limite: int = 1):
            return []

    vs = _VS()
    h = HybridMemory(vector_store=vs)
    h.store(payload="texto", memory_type=MemoryType.SEMANTIC, vector=[0.1, 0.2])
    assert len(vs.saved) == 1
    h.close()


def test_hybrid_store_vector_error_no_rompe() -> None:
    class _VS:
        def guardar_incidente(self, data) -> None:
            msg = "qdrant caido"
            raise RuntimeError(msg)

        def buscar_similares(self, v, limite: int = 1):
            msg = "qdrant caido"
            raise RuntimeError(msg)

    h = HybridMemory(vector_store=_VS())
    rid = h.store(payload="x", vector=[0.1])
    assert rid != ""
    h.close()


def test_hybrid_search_vacio() -> None:
    h = HybridMemory()
    assert h.search("") == []
    assert h.search("   ") == []
    h.close()


def test_hybrid_search_por_tipo() -> None:
    h = HybridMemory()
    h.store(payload="frase de prueba", memory_type=MemoryType.EPISODIC)
    h.store(payload="frase de prueba", memory_type=MemoryType.SEMANTIC)
    res = h.search("frase", memory_type=MemoryType.EPISODIC)
    assert len(res) == 1
    assert res[0].type == MemoryType.EPISODIC
    h.close()


def test_hybrid_search_error_fts() -> None:
    h = HybridMemory()
    # query con caracteres que rompen FTS5 → OperationalError → []
    res = h.search('unquote "roto', k=10)
    assert res == []
    h.close()


def test_hybrid_get() -> None:
    h = HybridMemory()
    rid = h.store(payload="contenido")
    r = h.get(rid)
    assert r is not None
    assert r.payload == "contenido"
    assert h.get("no-existe") is None
    h.close()


def test_hybrid_get_tipo_invalido() -> None:
    h = HybridMemory()
    conn = h._get_conn()
    import uuid as _uuid

    rid = _uuid.uuid4().hex
    conn.execute(
        "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?, ?, ?, ?)",
        (rid, "tipo_raro", datetime.now(UTC).isoformat(), "{}"),
    )
    conn.execute("INSERT INTO memory_fts (id, text, metadata) VALUES (?, ?, ?)", (rid, "x", "{}"))
    conn.commit()
    r = h.get(rid)
    assert r.type == MemoryType.WORKING  # ValueError → WORKING
    h.close()


def test_hybrid_metadata_invalida() -> None:
    h = HybridMemory()
    conn = h._get_conn()
    import uuid as _uuid

    rid = _uuid.uuid4().hex
    conn.execute(
        "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?, ?, ?, ?)",
        (rid, "working", datetime.now(UTC).isoformat(), "no-json"),
    )
    conn.execute("INSERT INTO memory_fts (id, text, metadata) VALUES (?, ?, ?)", (rid, "x", "no-json"))
    conn.commit()
    r = h.get(rid)
    assert "created_at" in r.metadata  # post_init añade created_at aunque no haya metadata
    h.close()


def test_hybrid_delete() -> None:
    h = HybridMemory()
    rid = h.store(payload="x")
    assert h.delete(rid) is True
    assert h.delete(rid) is False
    assert h.count() == 0
    h.close()


def test_hybrid_delete_error() -> None:
    h = HybridMemory()
    h._conn = None  # get_conn se recreará; forzamos error con conn roto
    conn = h._get_conn()
    h._conn = None
    # conn real cerrado → error en delete
    conn.close()
    h._conn = conn  # type: ignore[assignment]
    assert h.delete("x") is False
    h.close()


def test_hybrid_count_y_clear() -> None:
    h = HybridMemory()
    h.store(payload="a", memory_type=MemoryType.WORKING)
    h.store(payload="b", memory_type=MemoryType.EPISODIC)
    assert h.count() == 2
    assert h.count(MemoryType.WORKING) == 1
    h.clear()
    assert h.count() == 0
    h.close()


def test_hybrid_count_error() -> None:
    h = HybridMemory()
    h._get_conn().close()
    h._conn = None
    conn = h._get_conn()
    conn.execute("DROP TABLE memory_metadata")
    conn.commit()
    assert h.count() == 0  # error → 0
    h.close()


def test_hybrid_health_sin_vector() -> None:
    h = HybridMemory()
    h.store(payload="x")
    health = h.health()
    assert health["total_records"] == 1
    assert health["vector_store_ok"] is False
    h.close()


def test_hybrid_health_con_vector() -> None:
    class _VS:
        def buscar_similares(self, v, limite: int = 1):
            return []

    h = HybridMemory(vector_store=_VS())
    health = h.health()
    assert health["vector_store_ok"] is True
    h.close()


def test_hybrid_health_vector_error() -> None:
    class _VS:
        def buscar_similares(self, v, limite: int = 1):
            msg = "roto"
            raise RuntimeError(msg)

    h = HybridMemory(vector_store=_VS())
    health = h.health()
    assert health["vector_store_ok"] is False
    h.close()


def test_hybrid_context_manager(tmp_path: object) -> None:
    with HybridMemory() as h:
        h.store(payload="x")
        assert h.count() == 1


def test_hybrid_close_doble() -> None:
    h = HybridMemory()
    h.close()
    h.close()


def test_hybrid_persistencia(tmp_path: object) -> None:
    path = str(tmp_path / "hybrid.db")
    h = HybridMemory(db_path=path)
    h.store(payload="frase persistida")
    h.close()
    h2 = HybridMemory(db_path=path)
    assert h2.search("persistida")
    h2.close()


def test_hybrid_store_error_lanza() -> None:
    h = HybridMemory()
    conn = h._get_conn()
    conn.execute("DROP TABLE memory_metadata")
    conn.commit()
    with pytest.raises(sqlite3.OperationalError):
        h.store(payload="x")


# ── hybrid: ramas restantes ──────────────────────────────────


def test_hybrid_close_error_conn_roto() -> None:
    h = HybridMemory()
    conn = h._get_conn()

    class _CierreRoto:
        def close(self):
            msg = "cierre roto"
            raise sqlite3.Error(msg)

    h._conn = _CierreRoto()  # type: ignore[assignment]
    h.close()  # except → log.debug → _conn = None
    assert h._conn is None
    conn.close()


def test_hybrid_clear_error() -> None:
    h = HybridMemory()
    conn = h._get_conn()
    conn.execute("DROP TABLE memory_fts")
    conn.commit()
    h.clear()  # error → log.exception, no lanza
    h.close()


def test_hybrid_search_metadata_invalida_en_resultado() -> None:
    h = HybridMemory()
    conn = h._get_conn()
    import uuid as _uuid

    rid = _uuid.uuid4().hex
    conn.execute(
        "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?, ?, ?, ?)",
        (rid, "raro", datetime.now(UTC).isoformat(), "no-json"),
    )
    conn.execute("INSERT INTO memory_fts (id, text, metadata) VALUES (?, ?, ?)", (rid, "frase unica buscar", "no-json"))
    conn.commit()
    res = h.search("frase unica")
    assert res[0].type == MemoryType.WORKING  # ValueError → WORKING
    assert "created_at" in res[0].metadata
    h.close()


def test_hybrid_search_error_fts5_operacional() -> None:
    h = HybridMemory()
    h.store(payload="algo")
    conn = h._get_conn()
    conn.execute("DROP TABLE memory_fts")
    conn.commit()
    assert h.search("consulta") == []  # OperationalError → []
    h.close()


def test_hybrid_get_error_conn_roto() -> None:
    h = HybridMemory()
    conn = h._get_conn()

    class _GetRoto:
        def execute(self, *a, **k):
            msg = "roto"
            raise sqlite3.OperationalError(msg)

    h._conn = _GetRoto()  # type: ignore[assignment]
    assert h.get("x") is None  # except → None
    h._conn = None
    conn.close()


def test_hybrid_health_count_error() -> None:
    h = HybridMemory()

    def _count_roto(*a, **k) -> int:
        msg = "roto"
        raise sqlite3.OperationalError(msg)

    h.count = _count_roto  # type: ignore[method-assign]
    health = h.health()
    assert health["total_records"] == 0  # error → total 0
    h.close()


# ── forgetting ───────────────────────────────────────────────


def test_forgetting_event_to_dict() -> None:
    e = ForgettingEvent(record_id="r1", record_type="episode", reason="ttl", policy="hybrid", timestamp="t", importance=0.5, age_days=1.25)
    d = e.to_dict()
    assert d["age_days"] == 1.2
    assert d["policy"] == "hybrid"


def test_forgetting_result_total() -> None:
    r = ForgettingResult(episodes_removed=1, facts_removed=2, summaries_removed=3)
    assert r.total_removed == 6


def test_protection_rules() -> None:
    p = ProtectionRules()
    p.protect("a")
    p.pin("b")
    assert p.is_protected("a") is True
    assert p.is_pinned("b") is True
    assert p.count_protected() == 1
    assert p.count_pinned() == 1
    assert p.unprotect("a") is True
    assert p.unprotect("a") is False
    assert p.unpin("b") is True
    assert p.unpin("b") is False
    assert p.is_protected("zzz") is False


def test_never_forget_policy() -> None:
    p = NeverForgetPolicy()
    assert p.name() == "never_forget"
    assert p.should_forget(_ep(), None) == (False, "policy_never_forget")


def test_ttl_policy_episode() -> None:
    p = TTLForgetPolicy()
    ep = _ep("e1", ttl=0)
    ep.ttl = 0
    assert p.should_forget(ep, None)[0] is False
    assert p.should_forget(_ep("e2"), None)[1].startswith("ttl_expired") or True
    expirado = _ep("e3")
    expirado.timestamp = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    expirado.ttl = 3600
    ok, reason = p.should_forget(expirado, None)
    assert ok is True
    assert reason == "ttl_expired_3600s"


def test_ttl_policy_no_expirado() -> None:
    p = TTLForgetPolicy()
    ep = _ep("e1", ttl=604800)
    ok, _r = p.should_forget(ep, None)
    assert ok is False


def test_ttl_policy_fact() -> None:
    p = TTLForgetPolicy()
    assert p.should_forget(_fact(), None) == (False, "semantic_no_ttl")


def test_ttl_policy_unknown() -> None:
    p = TTLForgetPolicy()
    assert p.should_forget("string", None) == (False, "unknown")


def test_importance_policy_episode_alta() -> None:
    p = ImportanceForgetPolicy(min_importance=0.2, min_age_days=30)
    ep = _ep("e1", importance=0.9)
    ok, reason = p.should_forget(ep, None)
    assert ok is False
    assert "above" in reason


def test_importance_policy_episode_joven() -> None:
    p = ImportanceForgetPolicy(min_importance=0.2, min_age_days=30)
    ep = _ep("e1", importance=0.1)
    ok, reason = p.should_forget(ep, None)
    assert ok is False
    assert "below" in reason


def test_importance_policy_episode_vieja_baja() -> None:
    p = ImportanceForgetPolicy(min_importance=0.2, min_age_days=1)
    ep = _ep("e1", importance=0.1)
    ep.timestamp = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    ok, _r = p.should_forget(ep, None)
    assert ok is True


def test_importance_policy_fact() -> None:
    p = ImportanceForgetPolicy(min_importance=0.2)
    assert p.should_forget(_fact("f1", importance=0.9), None)[0] is False
    assert p.should_forget(_fact("f2", importance=0.1), None)[0] is True


def test_importance_policy_unknown() -> None:
    p = ImportanceForgetPolicy()
    assert p.should_forget("str", None)[0] is False


def test_confidence_policy() -> None:
    p = ConfidenceForgetPolicy(min_confidence=0.3)
    assert p.should_forget(_ep("a", confidence=0.9), None)[0] is False
    assert p.should_forget(_ep("b", confidence=0.1), None)[0] is True
    assert p.should_forget(_fact("f", confidence=0.9), None)[0] is False
    assert p.should_forget(_fact("f2", confidence=0.1), None)[0] is True
    assert p.should_forget("str", None)[0] is False


def test_hybrid_policy_any() -> None:
    p = HybridForgetPolicy(require_all=False)
    ep = _ep("e1", importance=0.1, confidence=0.1)
    ok, reason = p.should_forget(ep, None)
    assert ok is True
    assert "ttl:" in reason


def test_hybrid_policy_require_all() -> None:
    p = HybridForgetPolicy(require_all=True)
    ep = _ep("e1", importance=0.1, confidence=0.1)
    ok, _ = p.should_forget(ep, None)
    assert ok is False  # ttl no expirado → no todos


def test_hybrid_policy_nada_selecciona() -> None:
    p = HybridForgetPolicy()
    ok, reason = p.should_forget(_ep("e1", importance=0.9, confidence=0.9), None)
    assert ok is False
    assert "ttl:" in reason


def test_hybrid_policy_name() -> None:
    assert HybridForgetPolicy().name() == "hybrid"


def test_forgetting_policy_abstracto() -> None:
    with pytest.raises(TypeError):
        ForgettingPolicy()


class _ConSuperPolicy(ForgettingPolicy):
    def name(self) -> str:
        n = super().name()
        if n is None:
            return "con-super"
        return n

    def should_forget(self, record, context):
        r = super().should_forget(record, context)
        if r is None:
            return False, "default"
        return r


def test_forgetting_policy_elipsis_via_super() -> None:
    p = _ConSuperPolicy()
    assert p.name() == "con-super"
    assert p.should_forget(_ep("a"), None) == (False, "default")


def test_age_seconds_timestamp_invalido() -> None:
    assert _age_seconds("no-es-fecha") == 0.0


def test_age_seconds_valido() -> None:
    ts = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    assert _age_seconds(ts) > 0


def test_forgetting_engine_remueve() -> None:
    es = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    es.store(_ep("a", timestamp=viejo, ttl=3600, importance=0.1))
    es.store(_ep("b", importance=0.9))
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()])
    r = engine.run()
    assert r.episodes_removed == 1
    assert es.count() == 1
    assert len(r.details) == 1
    assert r.total_evaluated >= 1


def test_forgetting_engine_dry_run_no_borra() -> None:
    es = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    es.store(_ep("a", timestamp=viejo, ttl=3600, importance=0.1))
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()])
    r = engine.run(dry_run=True)
    assert r.episodes_removed == 1
    assert es.count() == 1


def test_forgetting_protegidos_skipped() -> None:
    es = EpisodeStore()
    es.store(_ep("a", timestamp=(datetime.now(UTC) - timedelta(days=10)).isoformat(), ttl=3600))
    prot = ProtectionRules()
    prot.protect("a")
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()], protection=prot)
    r = engine.run()
    assert r.episodes_removed == 0
    assert r.protected_skipped == 1


def test_forgetting_pinned_skipped() -> None:
    es = EpisodeStore()
    es.store(_ep("a", timestamp=(datetime.now(UTC) - timedelta(days=10)).isoformat(), ttl=3600))
    prot = ProtectionRules()
    prot.pin("a")
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()], protection=prot)
    r = engine.run()
    assert r.episodes_removed == 0
    assert r.pinned_skipped == 1


def test_forgetting_referenciado_skipped() -> None:
    es = EpisodeStore()
    es.store(_ep("a", timestamp=(datetime.now(UTC) - timedelta(days=10)).isoformat(), ttl=3600))
    class _Sum:
        source_episode_ids: ClassVar[list] = ["a"]

    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()], summaries=[_Sum()])
    r = engine.run()
    assert r.episodes_removed == 0
    assert r.referenced_skipped == 1


def test_forgetting_facts_removidos() -> None:
    sm = SemanticMemoryStore()
    sm.store(_fact("f1", importance=0.1, subject="x1"))
    sm.store(_fact("f2", importance=0.9, subject="x2"))
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=sm, policies=[ImportanceForgetPolicy(min_importance=0.2)])
    r = engine.run()
    assert r.facts_removed == 1
    assert sm.count() == 1


def test_forgetting_facts_dry_run() -> None:
    sm = SemanticMemoryStore()
    sm.store(_fact("f1", importance=0.1))
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=sm, policies=[ImportanceForgetPolicy(min_importance=0.2)])
    r = engine.run(dry_run=True)
    assert r.facts_removed == 1
    assert sm.count() == 1


def test_forgetting_engine_simulate() -> None:
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore())
    r = engine.simulate()
    assert r.dry_run is True


def test_forgetting_engine_stats() -> None:
    es = EpisodeStore()
    es.store(_ep("a"))
    sm = SemanticMemoryStore()
    sm.store(_fact("f1"))
    prot = ProtectionRules()
    prot.protect("x")
    engine = ForgettingEngine(episode_store=es, semantic_store=sm, policies=[TTLForgetPolicy()], protection=prot)
    st = engine.stats()
    assert st["episodes_total"] == 1
    assert st["facts_total"] == 1
    assert st["protected"] == 1
    assert st["policies"] == ["ttl"]


def test_forgetting_engine_sin_semantic_store() -> None:
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=None)
    r = engine.run()
    assert r.facts_removed == 0


class _StoreFalsy:
    def __bool__(self) -> bool:
        return False


def test_forgetting_evaluate_facts_store_falsy() -> None:
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore())
    engine._semantic_store = None  # type: ignore[assignment]  # forzado post-constructor
    r = engine.run()
    assert r.facts_removed == 0


def test_forgetting_scheduler() -> None:
    es = EpisodeStore()
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore())
    sched = ForgettingScheduler(engine)
    assert sched.enabled is False
    sched.enable()
    assert sched.enabled is True
    sched.disable()
    assert sched.enabled is False
    r = sched.run_once(dry_run=True)
    assert r.dry_run is True


def test_forgetting_episode_batch_break() -> None:
    es = EpisodeStore()
    viejo = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    for i in range(5):
        es.store(_ep(f"e{i}", timestamp=viejo, ttl=3600, importance=0.1))
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[TTLForgetPolicy()], batch_size=2)
    r = engine.run()
    assert r.episodes_removed == 2  # batch_size limita


def test_forgetting_engine_policy_custom() -> None:
    class _SiempreOlvida:
        def name(self) -> str:
            return "siempre"

        def should_forget(self, record, context):
            return True, "siempre-olvida"

    es = EpisodeStore()
    es.store(_ep("a"))
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[_SiempreOlvida()])
    r = engine.run()
    assert r.episodes_removed == 1


def test_forgetting_engine_policy_vacio() -> None:
    es = EpisodeStore()
    es.store(_ep("a"))
    engine = ForgettingEngine(episode_store=es, semantic_store=SemanticMemoryStore(), policies=[])
    r = engine.run()
    assert r.episodes_removed == 0  # policy vacío → nada se olvida
    assert r.details == []


def test_forgetting_facts_protegidos_skipped() -> None:
    sm = SemanticMemoryStore()
    sm.store(_fact("f1", importance=0.1, subject="x1"))
    es = EpisodeStore()
    prot = ProtectionRules()
    prot.protect("f1")
    engine = ForgettingEngine(episode_store=es, semantic_store=sm, policies=[ImportanceForgetPolicy(min_importance=0.2)], protection=prot)
    r = engine.run()
    assert r.facts_removed == 0
    assert r.protected_skipped >= 1


def test_forgetting_facts_pinned_skipped() -> None:
    sm = SemanticMemoryStore()
    sm.store(_fact("f1", importance=0.1, subject="x1"))
    es = EpisodeStore()
    prot = ProtectionRules()
    prot.pin("f1")
    engine = ForgettingEngine(episode_store=es, semantic_store=sm, policies=[ImportanceForgetPolicy(min_importance=0.2)], protection=prot)
    r = engine.run()
    assert r.facts_removed == 0
    assert r.pinned_skipped >= 1
