"""Tests para F25-B3: Entity Resolution Avanzado.

Cubre:
- ContextualEntityResolver con desambiguación contextual
- LRUCache hit/miss/eviction
- Polisemia: Apple empresa vs fruta, Tesla empresa vs persona, etc.
- N-gram extraction (Berkshire Hathaway como una entidad)
- AMBIGUOUS status cuando el contexto no permite decidir
- UNKNOWN status para texto irreconocible
- EntityResolutionStage con n-gramas y contexto
- Cache stats en provenance
- Backward compatibility con RuleBasedEntityResolver
"""

from __future__ import annotations

import pytest

from motor.core.fusion.models import (
    FusionContext,
    KnowledgeClaim,
    ResolutionStatus,
    ResolvedEntity,
    make_claim_id,
)
from motor.core.fusion.stages.entity_resolver import (
    _DEFAULT_REGISTRY,
    CachePolicy,
    ContextualEntityResolver,
    EntityDef,
    EntityRegistry,
    EntityResolutionStage,
    LRUCache,
    RuleBasedEntityResolver,
    ScoringStrategy,
    _extract_entity_candidates,
)

# ── B3.1: LRUCache ──────────────────────────────────────

def test_lru_cache_get_miss() -> None:
    c = LRUCache(maxsize=10)
    assert c.get("missing") is None


def test_lru_cache_put_and_get() -> None:
    c = LRUCache(maxsize=10)
    e = ResolvedEntity(entity_id="E0001", canonical_name="Apple Inc.", confidence=0.95)
    c.put("apple", e)
    assert c.get("apple") is e


def test_lru_cache_eviction() -> None:
    c = LRUCache(maxsize=3)
    for i in range(5):
        e = ResolvedEntity(entity_id=f"E{i:04d}", canonical_name=f"Entity{i}", confidence=0.9)
        c.put(f"key{i}", e)
    assert c.size == 3
    assert c.get("key0") is None  # evicted (LRU)
    assert c.get("key4") is not None  # most recent


def test_lru_cache_clear() -> None:
    c = LRUCache(maxsize=10)
    e = ResolvedEntity(entity_id="E0001", canonical_name="X", confidence=0.9)
    c.put("x", e)
    c.clear()
    assert c.size == 0


def test_lru_cache_move_to_end_on_get() -> None:
    c = LRUCache(maxsize=3)
    for i in range(3):
        e = ResolvedEntity(entity_id=f"E{i:04d}", canonical_name=f"E{i}", confidence=0.9)
        c.put(f"key{i}", e)
    # Access key0 — should move to end (not evicted next)
    assert c.get("key0") is not None
    c.put("key3", ResolvedEntity(entity_id="E9999", canonical_name="New", confidence=0.9))
    # key1 should be evicted (was LRU), key0 should remain (was accessed)
    assert c.get("key0") is not None
    assert c.get("key1") is None


# ── B3.2: ContextualEntityResolver — disambiguation ─────

def test_resolve_apple_company_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("apple", context={"claim_text": "Apple Inc. sells iPhones"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Apple Inc."
    assert e.entity_id == "E0001"


def test_resolve_apple_fruit_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("apple", context={"claim_text": "I ate a delicious red apple"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Apple (fruit)"
    assert e.entity_id == "E0009"


def test_resolve_tesla_company_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("tesla", context={"claim_text": "Tesla sold 500k electric cars"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Tesla Inc."


def test_resolve_tesla_person_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("tesla", context={"claim_text": "Nikola Tesla invented the AC motor in 1888"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Nikola Tesla"


def test_resolve_amazon_company_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("amazon", context={"claim_text": "Amazon reported record revenue this quarter"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Amazon.com Inc."


def test_resolve_amazon_river_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("amazon", context={"claim_text": "The Amazon river flows through Brazil"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Amazon River"


def test_resolve_washington_state_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("washington", context={"claim_text": "Washington state is known for coffee"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Washington (state)"


def test_resolve_washington_dc_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("washington", context={"claim_text": "The White House is in Washington D.C."})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Washington, D.C."


def test_resolve_washington_person_by_context() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("washington", context={"claim_text": "George Washington was the first president"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "George Washington"


# ── B3.3: AMBIGUOUS status ──────────────────────────────

def test_resolve_ambiguous_no_context() -> None:
    r = ContextualEntityResolver()
    # "apple" without context keywords → ambiguous
    e = r.resolve("apple", context={"claim_text": "I like apple"})
    assert e.status == ResolutionStatus.AMBIGUOUS
    assert e.entity_id == ""


def test_resolve_ambiguous_tie() -> None:
    r = ContextualEntityResolver()
    # No disambiguation keywords → tie → AMBIGUOUS
    e = r.resolve("apple", context={
        "claim_text": "I looked at the apple"
    })
    assert e.status == ResolutionStatus.AMBIGUOUS


# ── B3.4: UNKNOWN status ────────────────────────────────

def test_resolve_unknown() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("nonexistentcorp12345")
    assert e.status == ResolutionStatus.UNKNOWN
    assert e.entity_id == ""


def test_resolve_empty_text() -> None:
    r = ContextualEntityResolver()
    e = r.resolve("")
    assert e.status == ResolutionStatus.UNKNOWN


# ── B3.5: Cache integration ─────────────────────────────

def test_cache_does_not_cache_multi_entry() -> None:
    """Multi-entry entities (apple) are NOT cached — depends on context."""
    r = ContextualEntityResolver()
    ctx_a = {"claim_text": "Apple Inc. sells iPhones"}
    ctx_b = {"claim_text": "I ate an apple fruit"}
    a = r.resolve("apple", context=ctx_a)
    b = r.resolve("apple", context=ctx_b)
    assert a is not b  # different objects (no cache hit)
    assert a.entity_id == "E0001"  # Apple Inc.
    assert b.entity_id == "E0009"  # Apple fruit


def test_cache_hit_single_entry() -> None:
    """Single-entry entities (nvidia) ARE cached."""
    r = ContextualEntityResolver()
    first = r.resolve("nvidia")
    cached = r.resolve("nvidia")
    assert cached is first  # same object (cache hit)


def test_cache_stats_in_stage() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "NVIDIA makes GPUs"),
                text="NVIDIA makes GPUs", confidence=0.9,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert "resolver_cache_size" in result.statistics
    # NVIDIA is single-entry → cached
    assert result.statistics["resolver_cache_size"] >= 1


# ── B3.6: N-gram extraction ─────────────────────────────

def test_extract_candidates_single_word() -> None:
    assert "apple" in _extract_entity_candidates("Apple sells oranges", _DEFAULT_REGISTRY)


def test_extract_candidates_multi_word() -> None:
    assert "berkshire hathaway" in _extract_entity_candidates(
        "Berkshire Hathaway bought a company", _DEFAULT_REGISTRY
    )


def test_extract_candidates_multi_word_three() -> None:
    assert "elon musk" in _extract_entity_candidates(
        "Elon Musk is the CEO of Tesla", _DEFAULT_REGISTRY
    )


def test_extract_candidates_does_not_include_unknown() -> None:
    candidates = _extract_entity_candidates("The quick brown fox jumps", _DEFAULT_REGISTRY)
    assert len(candidates) == 0


def test_extract_candidates_no_duplicates() -> None:
    candidates = _extract_entity_candidates("Apple Apple Apple", _DEFAULT_REGISTRY)
    assert candidates.count("apple") == 1


# ── B3.7: EntityResolutionStage ─────────────────────────

def test_stage_resolves_apple_vs_fruit() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "Apple sold 10M iPhones"),
                text="Apple sold 10M iPhones", confidence=0.9,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert result.statistics["entities_resolved"] >= 1
    assert result.statistics["entities_ambiguous"] == 0
    # Should resolve to Apple Inc., not Apple fruit
    for entity in result.entities:
        if "apple" in entity.canonical_name.lower():
            assert entity.entity_id == "E0001"
            break


def test_stage_ambiguous_when_no_context() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "I like apple"),
                text="I like apple", confidence=0.5,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    # No disambiguation keywords → AMBIGUOUS
    # (resolved_count=0 for apple, ambiguous_count > 0)
    assert "entities_ambiguous" in result.statistics


def test_stage_multiple_entities() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "Apple sells iPhones and Tesla makes electric cars"),
                text="Apple sells iPhones and Tesla makes electric cars",
                confidence=0.9,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert result.statistics["entities_resolved"] >= 2
    # Should include both Apple Inc. and Tesla Inc.
    entity_names = {e.canonical_name for e in result.entities}
    assert "Apple Inc." in entity_names
    assert "Tesla Inc." in entity_names


def test_stage_provenance_records_resolver_version() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "NVIDIA makes GPUs"),
                text="NVIDIA makes GPUs", confidence=0.9,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert result.provenance.resolver_name == "ContextualEntityResolver"
    assert result.provenance.resolver_version == "3.1.0"


# ── B3.8: Backward compatibility ────────────────────────

def test_legacy_resolver_still_works() -> None:
    resolver = RuleBasedEntityResolver()
    e = resolver.resolve("apple")
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Apple"
    assert e.resolver_name == "RuleBasedEntityResolver"


def test_legacy_resolver_unknown() -> None:
    resolver = RuleBasedEntityResolver()
    e = resolver.resolve("nonexistent")
    assert e.status == ResolutionStatus.UNKNOWN
    assert e.entity_id == ""


def test_stage_accepts_custom_resolver() -> None:
    """EntityResolutionStage debe aceptar un EntityResolver inyectado."""
    custom = RuleBasedEntityResolver()
    stage = EntityResolutionStage(resolver=custom)
    assert stage._resolver is custom


# ── B3.9: Determinism ──────────────────────────────────

def test_resolve_deterministic_same_context() -> None:
    """Mismo texto + mismo contexto → misma entidad."""
    r = ContextualEntityResolver()
    ctx = {"claim_text": "Apple sells iPhones"}
    a = r.resolve("apple", context=ctx)
    b = r.resolve("apple", context=ctx)
    assert a.entity_id == b.entity_id
    assert a.canonical_name == b.canonical_name


def test_stage_deterministic() -> None:
    """EntityResolutionStage es determinista."""
    claims = [
        KnowledgeClaim(
            id=make_claim_id("ev1", "NVIDIA makes GPUs"),
            text="NVIDIA makes GPUs", confidence=0.9,
        ),
        KnowledgeClaim(
            id=make_claim_id("ev2", "Tim Cook runs Apple"),
            text="Tim Cook runs Apple", confidence=0.9,
        ),
    ]
    r1 = EntityResolutionStage().execute(FusionContext(claims=list(claims)))
    r2 = EntityResolutionStage().execute(FusionContext(claims=list(claims)))
    assert len(r1.entities) == len(r2.entities)


# ── B3.10: Resolver respects context parameter ─────────

def test_resolve_without_context_fallback() -> None:
    """Sin contexto, entidades sin ambigüedad se resuelven igual."""
    r = ContextualEntityResolver()
    e = r.resolve("nvidia")
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "NVIDIA Corporation"


def test_resolve_without_context_ambiguous() -> None:
    """Sin contexto, entidades ambiguas retornan AMBIGUOUS."""
    r = ContextualEntityResolver()
    e = r.resolve("apple")  # no context → ambiguous
    assert e.status == ResolutionStatus.AMBIGUOUS


# ── B3.11: EntityRegistry injection ─────────────────────

def test_custom_registry_injection() -> None:
    """El resolver acepta un EntityRegistry personalizado."""
    custom = EntityRegistry({
        "customcorp": [
            EntityDef(entity_id="E9999", canonical_name="Custom Corp",
                      category="organization", keywords=["custom"]),
        ],
    })
    r = ContextualEntityResolver(registry=custom)
    assert r.registry is custom
    e = r.resolve("customcorp", context={"claim_text": "Custom Corp makes products"})
    assert e.status == ResolutionStatus.RESOLVED
    assert e.entity_id == "E9999"


def test_custom_registry_does_not_see_default() -> None:
    """Un resolver con registry personalizado no ve las entidades por defecto."""
    custom = EntityRegistry()
    r = ContextualEntityResolver(registry=custom)
    e = r.resolve("nvidia")
    assert e.status == ResolutionStatus.UNKNOWN  # not in custom registry


def test_entity_registry_known_names() -> None:
    reg = EntityRegistry({
        "test": [
            EntityDef(entity_id="T1", canonical_name="Test", aliases=["test alias"]),
        ],
    })
    assert "test" in reg.known_names
    assert "test alias" in reg.known_names


def test_entity_registry_len() -> None:
    reg = EntityRegistry({"a": [], "b": []})
    assert len(reg) == 2


# ── B3.12: ScoringStrategy injection ────────────────────

class _AlwaysFirst(ScoringStrategy):
    """Estrategia de testing: siempre elige la primera entrada."""
    def select(self, entries: list[EntityDef], context: str) -> int | None:
        return 0 if entries else None


def test_custom_scorer_injection() -> None:
    """El resolver acepta un ScoringStrategy personalizado."""
    r = ContextualEntityResolver(
        scorer=_AlwaysFirst(),
    )
    # "apple" sin contexto → _AlwaysFirst returns index 0 (Apple Inc.)
    e = r.resolve("apple")
    assert e.status == ResolutionStatus.RESOLVED
    assert e.canonical_name == "Apple Inc."


def test_custom_scorer_returns_ambiguous() -> None:
    """Un scorer que retorna None genera AMBIGUOUS."""
    class _AlwaysAmbiguous(ScoringStrategy):
        def select(self, entries: list[EntityDef], context: str) -> int | None:
            return None
    r = ContextualEntityResolver(scorer=_AlwaysAmbiguous())
    e = r.resolve("apple", context={"claim_text": "Apple sells iPhones"})
    assert e.status == ResolutionStatus.AMBIGUOUS


def test_stage_has_ambiguous_entity_ids() -> None:
    """El stage reporta qué entidades quedaron ambiguas."""
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "I like apple"),
                text="I like apple", confidence=0.5,
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert "ambiguous_entity_ids" in result.statistics
    if result.statistics["entities_ambiguous"] > 0:
        assert len(result.statistics["ambiguous_entity_ids"]) > 0


# ── B3.13: CachePolicy validation ───────────────────────

def test_cache_policy_from_string_valid() -> None:
    assert CachePolicy.from_string("deterministic_only") == CachePolicy.DETERMINISTIC_ONLY
    assert CachePolicy.from_string("all") == CachePolicy.ALL
    assert CachePolicy.from_string("disabled") == CachePolicy.DISABLED


def test_cache_policy_from_string_invalid() -> None:
    import re
    with pytest.raises(ValueError, match=re.escape("Invalid cache policy: 'invalid'")):
        CachePolicy.from_string("invalid")


def test_cache_policy_from_string_case_sensitive() -> None:
    with pytest.raises(ValueError):
        CachePolicy.from_string("ALL")  # must be lowercase


def test_cache_policy_accepts_enum_in_constructor() -> None:
    r = ContextualEntityResolver(cache_policy=CachePolicy.DISABLED)
    assert r.cache_policy == CachePolicy.DISABLED


def test_cache_policy_accepts_string_in_constructor() -> None:
    r = ContextualEntityResolver(cache_policy="disabled")
    assert r.cache_policy == CachePolicy.DISABLED


def test_cache_disabled_does_not_cache() -> None:
    r = ContextualEntityResolver(cache_policy=CachePolicy.DISABLED)
    a = r.resolve("nvidia")
    b = r.resolve("nvidia")
    # Sin caché → objetos distintos
    assert a is not b
    assert a.entity_id == b.entity_id
