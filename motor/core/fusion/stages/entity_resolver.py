"""Entity Resolution avanzado (F25-B3) — módulo dividido en 4 subunidades.

API pública intacta (re-exports desde los submódulos):
  entity_models, entity_registry, entity_cache, entity_scoring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, EntityResolver
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import ResolutionStatus, ResolvedEntity
from motor.core.fusion.stages.entity_cache import LRUCache
from motor.core.fusion.stages.entity_models import CachePolicy, EntityDef
from motor.core.fusion.stages.entity_registry import _DEFAULT_REGISTRY, EntityRegistry
from motor.core.fusion.stages.entity_scoring import KeywordScorer, ScoringStrategy

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext

def _extract_entity_candidates(text: str, registry: EntityRegistry, max_ngram: int = 3) -> list[str]:
    """Extrae n-gramas del texto que coinciden con entidades conocidas.

    Solo genera candidatos si el n-grama está en registry.known_names.
    Elimina duplicados (mismo n-grama aparece una sola vez por texto).
    Complejidad: O(n * max_ngram) donde n = palabras del texto.
    """
    words = text.split()
    candidates: list[str] = []
    seen: set[str] = set()
    known = registry.known_names
    for n in range(1, max_ngram + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n]).strip().lower()
            if phrase in known and phrase not in seen:
                seen.add(phrase)
                candidates.append(phrase)
    return candidates


# ── RuleBasedEntityResolver (backward compatible) ────────


class RuleBasedEntityResolver(EntityResolver):
    """Resolución básica por diccionario estático (B2).

    Mantenido para compatibilidad. Usar ContextualEntityResolver
    para producción: soporta desambiguación contextual y cache.
    """

    _LEGACY: dict[str, dict[str, str | list[str]]] = {
        "apple": {"id": "E0001", "name": "Apple", "aliases": ["apple inc.", "apple computer"]},
        "microsoft": {"id": "E0002", "name": "Microsoft", "aliases": ["microsoft corp.", "ms"]},
        "google": {"id": "E0003", "name": "Google", "aliases": ["google inc.", "alphabet"]},
        "amazon": {"id": "E0004", "name": "Amazon", "aliases": ["amazon.com", "amazon web services"]},
        "meta": {"id": "E0005", "name": "Meta", "aliases": ["meta platforms", "facebook"]},
        "tesla": {"id": "E0006", "name": "Tesla", "aliases": ["tesla inc.", "tesla motors"]},
        "nvidia": {"id": "E0007", "name": "NVIDIA", "aliases": ["nvidia corporation"]},
        "openai": {"id": "E0008", "name": "OpenAI", "aliases": ["open ai"]},
    }

    @property
    def version(self) -> str:
        return "1.0.0"

    def resolve(self, text: str, context: dict | None = None) -> ResolvedEntity:
        key = text.strip().lower()
        info = self._LEGACY.get(key)
        if info is not None:
            return ResolvedEntity(
                entity_id=info["id"],  # type: ignore[arg-type]
                canonical_name=info["name"],  # type: ignore[arg-type]
                confidence=0.95,
                status=ResolutionStatus.RESOLVED,
                aliases=tuple(info["aliases"]),  # type: ignore[arg-type]
                resolver_name="RuleBasedEntityResolver",
                resolver_version=self.version,
            )
        return ResolvedEntity(
            entity_id="",
            canonical_name=text,
            confidence=0.0,
            status=ResolutionStatus.UNKNOWN,
            resolver_name="RuleBasedEntityResolver",
            resolver_version=self.version,
        )

    def resolve_many(self, texts: list[str], context: dict | None = None) -> list[ResolvedEntity]:
        return [self.resolve(t) for t in texts]

    def normalize(self, text: str) -> str:
        return text.strip().lower()


# ── ContextualEntityResolver ─────────────────────────────


class ContextualEntityResolver(EntityResolver):
    """Resuelve entidades usando el contexto completo del claim.

    Componentes inyectables:
    - registry: EntityRegistry — almacenamiento de entidades conocido
    - scorer: ScoringStrategy — algoritmo de desambiguación

    Características:
    - Desambiguación contextual (Apple empresa vs fruta)
    - N-gramas (resuelve "Berkshire Hathaway" como entidad única)
    - Cache LRU solo para entradas deterministas (no ambiguas)
    - Retorno AMBIGUOUS cuando el contexto no permite decidir
    - Diseñado para extenderse con embeddings en F26
    """

    def __init__(
        self,
        registry: EntityRegistry | None = None,
        scorer: ScoringStrategy | None = None,
        cache_maxsize: int = 2048,
        cache_policy: CachePolicy | str = CachePolicy.DETERMINISTIC_ONLY,
    ) -> None:
        self._registry = registry if registry is not None else _DEFAULT_REGISTRY
        self._scorer = scorer if scorer is not None else KeywordScorer()
        if not isinstance(cache_policy, CachePolicy):
            self._cache_policy = CachePolicy.from_string(cache_policy)
        else:
            self._cache_policy = cache_policy
        self._cache = LRUCache(maxsize=cache_maxsize)

    @property
    def cache_policy(self) -> CachePolicy:
        """Política de caché activa."""
        return self._cache_policy

    @property
    def registry(self) -> EntityRegistry:
        return self._registry

    @property
    def scorer(self) -> ScoringStrategy:
        return self._scorer

    @property
    def cache(self) -> LRUCache:
        return self._cache

    @property
    def version(self) -> str:
        return "3.1.0"

    def resolve(self, text: str, context: dict | None = None) -> ResolvedEntity:
        key = text.strip().lower()
        if not key:
            return self._resolve_unknown(text)

        # Cache hit (según política)
        if self._cache_policy != CachePolicy.DISABLED:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        entries = self._registry.lookup(key)
        if not entries:
            result = self._resolve_unknown(text)
            if self._cache_policy != CachePolicy.DISABLED:
                self._cache.put(key, result)  # UNKNOWN es determinista
            return result

        # Una sola definición → determinista
        if len(entries) == 1:
            result = self._build_resolved(entries[0])
            if self._cache_policy != CachePolicy.DISABLED:
                self._cache.put(key, result)
            return result

        # Múltiples definiciones → depende del contexto
        ctx_text = (context or {}).get("claim_text", text)
        idx = self._scorer.select(entries, ctx_text)

        if idx is None:
            entity_ids = tuple(e.entity_id for e in entries)
            return ResolvedEntity(
                entity_id="",
                canonical_name=text,
                confidence=0.0,
                status=ResolutionStatus.AMBIGUOUS,
                aliases=entity_ids,
                resolver_name=self.__class__.__name__,
                resolver_version=self.version,
            )

        result = self._build_resolved(entries[idx])
        # Solo cachear multi-entry si política es ALL (usa contexto en clave)
        if self._cache_policy == CachePolicy.ALL:
            ctx_key = f"{key}:{ctx_text.strip().lower()}"
            self._cache.put(ctx_key, result)
        return result

    def resolve_many(
        self,
        texts: list[str],
        context: dict | None = None,
    ) -> list[ResolvedEntity]:
        return [self.resolve(t, context=context) for t in texts]

    def normalize(self, text: str) -> str:
        return text.strip().lower()

    # ── helpers ──────────────────────────────────────

    @staticmethod
    def _resolve_unknown(text: str) -> ResolvedEntity:
        return ResolvedEntity(
            entity_id="",
            canonical_name=text,
            confidence=0.0,
            status=ResolutionStatus.UNKNOWN,
            resolver_name="ContextualEntityResolver",
            resolver_version="3.1.0",
        )

    @staticmethod
    def _build_resolved(entry: EntityDef) -> ResolvedEntity:
        return ResolvedEntity(
            entity_id=entry.entity_id,
            canonical_name=entry.canonical_name,
            confidence=0.95,
            status=ResolutionStatus.RESOLVED,
            aliases=tuple(entry.aliases),
            resolver_name="ContextualEntityResolver",
            resolver_version="3.1.0",
        )


# ── EntityResolutionStage (B3) ───────────────────────────


class EntityResolutionStage(BaseStage):
    """Etapa que resuelve entidades usando el contexto completo del claim.

    Extrae candidatos mediante n-gramas y pasa el claim completo
    como contexto al resolver para desambiguación semántica.
    """

    def __init__(self, resolver: EntityResolver | None = None) -> None:
        self._resolver = resolver or ContextualEntityResolver()

    @property
    def stage(self) -> FusionStage:
        return FusionStage.ENTITY_RESOLUTION

    @property
    def name(self) -> str:
        return "EntityResolutionStage"

    @property
    def version(self) -> str:
        return "3.1.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        resolved_count = 0
        ambiguous_count = 0
        unknown_count = 0
        entities: list[ResolvedEntity] = []
        ambiguous_entity_ids: list[str] = []

        # Obtener registry del resolver si es ContextualEntityResolver
        registry = getattr(self._resolver, "registry", None)

        for claim in context.claims:
            text = claim.normalized_text or claim.text
            ctx = {
                "claim_text": claim.text,
                "claim_id": claim.id,
                "normalized_text": claim.normalized_text,
            }

            candidates = _extract_entity_candidates(text, registry or _DEFAULT_REGISTRY)
            seen_ids: set[str] = set()

            for candidate in candidates:
                entity = self._resolver.resolve(candidate, context=ctx)
                if entity.status == ResolutionStatus.RESOLVED:
                    if entity.entity_id not in seen_ids:
                        seen_ids.add(entity.entity_id)
                        entities.append(entity)
                    resolved_count += 1
                elif entity.status == ResolutionStatus.AMBIGUOUS:
                    ambiguous_count += 1
                    ambiguous_entity_ids.append(candidate)
                else:
                    unknown_count += 1

        if ambiguous_entity_ids:
            context.warnings.append(f"Ambiguous entities: {', '.join(sorted(set(ambiguous_entity_ids)))}")

        context.entities = entities
        context.statistics["entities_resolved"] = resolved_count
        context.statistics["entities_ambiguous"] = ambiguous_count
        context.statistics["entities_unknown"] = unknown_count
        context.statistics["ambiguous_entity_ids"] = ambiguous_entity_ids
        context.provenance.resolver_name = self._resolver.__class__.__name__
        context.provenance.resolver_version = self._resolver.version

        cache = getattr(self._resolver, "cache", None)
        if cache is not None:
            context.statistics["resolver_cache_size"] = cache.size
            context.statistics["resolver_cache_maxsize"] = cache.maxsize

        return context
