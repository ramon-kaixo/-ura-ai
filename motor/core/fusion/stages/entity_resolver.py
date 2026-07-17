"""Entity Resolution avanzado (F25-B3).

ContextualEntityResolver con desambiguación por contexto,
LRU cache (solo entradas no ambiguas), registro inyectable
y estrategia de scoring sustituible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage, EntityResolver
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import ResolutionStatus, ResolvedEntity

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext


# ── Modelo de definición de entidad ──────────────────────


@dataclass
class EntityDef:
    """Definición de una entidad conocida.

    Separada del resolver para permitir almacenamiento externo
    (BD, vector DB, archivo YAML) sin modificar el algoritmo.
    """

    entity_id: str
    canonical_name: str
    category: str = ""
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


# ── Registro de entidades (inyectable) ───────────────────


class EntityRegistry:
    """Almacenamiento de entidades conocido, separado del algoritmo.

    Puede ser reemplazado por una BD, un archivo o una consulta
    a vector DB sin modificar el resolver.
    """

    def __init__(self, entries: dict[str, list[EntityDef]] | None = None) -> None:
        self._entries: dict[str, list[EntityDef]] = entries or {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._all_names: set[str] = set()
        for key, entry_list in self._entries.items():
            self._all_names.add(key)
            for entry in entry_list:
                for alias in entry.aliases:
                    self._all_names.add(alias.strip().lower())

    def lookup(self, name: str) -> list[EntityDef]:
        """Retorna todas las definiciones para un nombre (0, 1 o varias)."""
        return list(self._entries.get(name.strip().lower(), []))

    @property
    def known_names(self) -> set[str]:
        return set(self._all_names)

    def __len__(self) -> int:
        return len(self._entries)


# ── Estrategia de scoring para desambiguación ────────────


class ScoringStrategy(ABC):
    """Estrategia de desambiguación sustituible.

    La implementación por defecto usa keywords. Puede reemplazarse
    por un scorer basado en embeddings, TF-IDF, o LLM sin modificar
    la pipeline.
    """

    @abstractmethod
    def select(self, entries: list[EntityDef], context: str) -> int | None:
        """Retorna índice de la mejor entrada, o None si ambiguo."""
        ...


class KeywordScorer(ScoringStrategy):
    """Puntúa cada entrada contando keywords presentes en el contexto.

    Si hay empate o ninguna keyword coincide → None (AMBIGUOUS).
    """

    def select(self, entries: list[EntityDef], context: str) -> int | None:
        if len(entries) == 1:
            return 0
        ctx_lower = context.lower()
        scores = [sum(1 for kw in e.keywords if kw in ctx_lower) for e in entries]
        max_score = max(scores)
        if max_score == 0 or scores.count(max_score) > 1:
            return None
        return scores.index(max_score)


# ── Registro por defecto ─────────────────────────────────

_DEFAULT_ENTRIES: dict[str, list[EntityDef]] = {
    "apple": [
        EntityDef(
            entity_id="E0001", canonical_name="Apple Inc.", category="organization",
            aliases=["apple inc.", "apple computer"],
            keywords=["company", "inc", "iphone", "mac", "tim cook", "cupertino",
                      "sells", "stock", "ceo", "revenue", "product", "store",
                      "app store", "ios", "ipad", "watch", "airpods"],
        ),
        EntityDef(
            entity_id="E0009", canonical_name="Apple (fruit)", category="food",
            aliases=["apple fruit", "manzana"],
            keywords=["fruit", "eat", "delicious", "red", "green", "orchard",
                      "pie", "juice", "ripe", "tree", "fresh", "sweet"],
        ),
    ],
    "microsoft": [
        EntityDef(
            entity_id="E0002", canonical_name="Microsoft", category="organization",
            aliases=["microsoft corp.", "ms", "microsoft corporation"],
            keywords=["software", "windows", "office", "azure", "satya", "bill gates",
                      "company", "ceo", "revenue", "product"],
        ),
    ],
    "google": [
        EntityDef(
            entity_id="E0003", canonical_name="Google", category="organization",
            aliases=["google inc.", "alphabet"],
            keywords=["search", "android", "chrome", "youtube", "sundar pichai",
                      "company", "ads", "cloud", "gmail"],
        ),
    ],
    "amazon": [
        EntityDef(
            entity_id="E0004", canonical_name="Amazon.com Inc.", category="organization",
            aliases=["amazon.com", "amazon web services", "aws"],
            keywords=["company", "ecommerce", "aws", "cloud", "jeff bezos",
                      "prime", "delivery", "store", "revenue"],
        ),
        EntityDef(
            entity_id="E0010", canonical_name="Amazon River", category="location",
            aliases=["amazon river", "rio amazonas"],
            keywords=["river", "rainforest", "brazil", "peru", "water", "flow",
                      "longest", "basin", "tributary"],
        ),
    ],
    "tesla": [
        EntityDef(
            entity_id="E0006", canonical_name="Tesla Inc.", category="organization",
            aliases=["tesla inc.", "tesla motors"],
            keywords=["car", "electric", "vehicle", "elon musk", "company",
                      "stock", "revenue", "battery", "autopilot", "model"],
        ),
        EntityDef(
            entity_id="E0011", canonical_name="Nikola Tesla", category="person",
            aliases=["nikola tesla"],
            keywords=["inventor", "scientist", "ac", "electricity", "coil",
                      "patent", "history", "died", "born", "invention"],
        ),
    ],
    "meta": [
        EntityDef(
            entity_id="E0005", canonical_name="Meta Platforms", category="organization",
            aliases=["meta platforms", "facebook", "facebook inc."],
            keywords=["social", "network", "zuckerberg", "company", "revenue",
                      "ads", "instagram", "whatsapp", "platform"],
        ),
    ],
    "nvidia": [
        EntityDef(
            entity_id="E0007", canonical_name="NVIDIA Corporation", category="organization",
            aliases=["nvidia corporation"],
            keywords=["gpu", "graphics", "chip", "ai", "jensen huang", "company",
                      "cuda", "datacenter", "gaming"],
        ),
    ],
    "openai": [
        EntityDef(
            entity_id="E0008", canonical_name="OpenAI", category="organization",
            aliases=["open ai"],
            keywords=["ai", "gpt", "chatgpt", "research", "language model",
                      "sam altman", "company"],
        ),
    ],
    "open ai": [
        EntityDef(
            entity_id="E0008", canonical_name="OpenAI", category="organization",
            aliases=["open ai", "openai"],
            keywords=["ai", "gpt", "chatgpt", "research", "language model",
                      "sam altman", "company"],
        ),
    ],
    "washington": [
        EntityDef(
            entity_id="E0012", canonical_name="Washington (state)", category="location",
            aliases=["washington state"],
            keywords=["state", "seattle", "olympia", "evergreen", "west coast"],
        ),
        EntityDef(
            entity_id="E0013", canonical_name="Washington, D.C.", category="location",
            aliases=["washington dc", "district of columbia"],
            keywords=["capital", "dc", "government", "congress", "white house",
                      "senate", "president", "federal"],
        ),
        EntityDef(
            entity_id="E0014", canonical_name="George Washington", category="person",
            aliases=["george washington"],
            keywords=["president", "founding father", "revolution", "general",
                      "first", "mount vernon"],
        ),
    ],
    "berkshire hathaway": [
        EntityDef(
            entity_id="E0015", canonical_name="Berkshire Hathaway", category="organization",
            aliases=["berkshire"],
            keywords=["warren buffett", "investment", "company", "stock", "holding",
                      "revenue", "ceo"],
        ),
    ],
    "jensen huang": [
        EntityDef(
            entity_id="E0016", canonical_name="Jensen Huang", category="person",
            aliases=["jen hsun huang"],
            keywords=["nvidia", "ceo", "founder", "gpu"],
        ),
    ],
    "tim cook": [
        EntityDef(
            entity_id="E0017", canonical_name="Tim Cook", category="person",
            aliases=["timothy cook"],
            keywords=["apple", "ceo", "apple inc."],
        ),
    ],
    "elon musk": [
        EntityDef(
            entity_id="E0018", canonical_name="Elon Musk", category="person",
            aliases=["elon reeve musk"],
            keywords=["tesla", "spacex", "twitter", "x", "ceo", "entrepreneur"],
        ),
    ],
}

_DEFAULT_REGISTRY = EntityRegistry(_DEFAULT_ENTRIES)


# ── LRU Cache (solo entradas independientes de contexto) ─


class LRUCache:
    """Cache LRU para resoluciones deterministas.

    Solo almacena entradas cuya resolución NO depende del contexto:
    - Entidades con una única definición (no ambiguas)
    - Resultados UNKNOWN

    Las entidades ambiguas (múltiples definiciones) NO se cachean
    para evitar falsos aciertos cuando el contexto cambia.
    """

    def __init__(self, maxsize: int = 2048) -> None:
        self._cache: OrderedDict[str, ResolvedEntity] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> ResolvedEntity | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, entity: ResolvedEntity) -> None:
        self._cache[key] = entity
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def clear(self) -> None:
        self._cache.clear()


# ── Funciones auxiliares ─────────────────────────────────


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
            phrase = " ".join(words[i:i + n]).strip().lower()
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
    ) -> None:
        self._registry = registry if registry is not None else _DEFAULT_REGISTRY
        self._scorer = scorer if scorer is not None else KeywordScorer()
        self._cache = LRUCache(maxsize=cache_maxsize)

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

        # Cache hit — solo para entradas deterministas (no ambiguas)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        entries = self._registry.lookup(key)
        if not entries:
            result = self._resolve_unknown(text)
            self._cache.put(key, result)  # UNKNOWN siempre es determinista
            return result

        # Una sola definición → determinista, se puede cachear
        if len(entries) == 1:
            result = self._build_resolved(entries[0])
            self._cache.put(key, result)
            return result

        # Múltiples definiciones → depende del contexto → NO se cachea
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

        return self._build_resolved(entries[idx])

    def resolve_many(
        self, texts: list[str], context: dict | None = None,
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
            context.warnings.append(
                f"Ambiguous entities: {', '.join(sorted(set(ambiguous_entity_ids)))}"
            )

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
