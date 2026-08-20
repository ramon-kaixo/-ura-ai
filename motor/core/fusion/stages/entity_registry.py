"""Entity Resolution avanzado (F25-B3).

ContextualEntityResolver con desambiguación por contexto,
LRU cache (solo entradas no ambiguas), registro inyectable
y estrategia de scoring sustituible.
"""

from __future__ import annotations

from dataclasses import dataclass

from motor.core.fusion.stages.entity_models import EntityDef

# ── Modelo de definición de entidad ──────────────────────


@dataclass
class EntityRegistry:
    """Almacenamiento de entidades conocido, separado del algoritmo.

    Puede ser reemplazado por una BD, un archivo o una consulta
    a vector DB sin modificar el resolver.

    Contrato de concurrencia:
    - El registro se construye una sola vez durante __init__ (inmutable).
    - lookup() es read-only sobre el diccionario interno.
    - No hay estado mutable compartido entre resoluciones simultáneas.
    - Si se necesita recarga dinámica (hot reload), debe reemplazarse
      la referencia completa (copy-on-write), no mutar el registro existente.
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


_DEFAULT_ENTRIES: dict[str, list[EntityDef]] = {
    "apple": [
        EntityDef(
            entity_id="E0001",
            canonical_name="Apple Inc.",
            category="organization",
            aliases=["apple inc.", "apple computer"],
            keywords=[
                "company",
                "inc",
                "iphone",
                "mac",
                "tim cook",
                "cupertino",
                "sells",
                "stock",
                "ceo",
                "revenue",
                "product",
                "store",
                "app store",
                "ios",
                "ipad",
                "watch",
                "airpods",
            ],
        ),
        EntityDef(
            entity_id="E0009",
            canonical_name="Apple (fruit)",
            category="food",
            aliases=["apple fruit", "manzana"],
            keywords=[
                "fruit",
                "eat",
                "delicious",
                "red",
                "green",
                "orchard",
                "pie",
                "juice",
                "ripe",
                "tree",
                "fresh",
                "sweet",
            ],
        ),
    ],
    "microsoft": [
        EntityDef(
            entity_id="E0002",
            canonical_name="Microsoft",
            category="organization",
            aliases=["microsoft corp.", "ms", "microsoft corporation"],
            keywords=[
                "software",
                "windows",
                "office",
                "azure",
                "satya",
                "bill gates",
                "company",
                "ceo",
                "revenue",
                "product",
            ],
        ),
    ],
    "google": [
        EntityDef(
            entity_id="E0003",
            canonical_name="Google",
            category="organization",
            aliases=["google inc.", "alphabet"],
            keywords=["search", "android", "chrome", "youtube", "sundar pichai", "company", "ads", "cloud", "gmail"],
        ),
    ],
    "amazon": [
        EntityDef(
            entity_id="E0004",
            canonical_name="Amazon.com Inc.",
            category="organization",
            aliases=["amazon.com", "amazon web services", "aws"],
            keywords=["company", "ecommerce", "aws", "cloud", "jeff bezos", "prime", "delivery", "store", "revenue"],
        ),
        EntityDef(
            entity_id="E0010",
            canonical_name="Amazon River",
            category="location",
            aliases=["amazon river", "rio amazonas"],
            keywords=["river", "rainforest", "brazil", "peru", "water", "flow", "longest", "basin", "tributary"],
        ),
    ],
    "tesla": [
        EntityDef(
            entity_id="E0006",
            canonical_name="Tesla Inc.",
            category="organization",
            aliases=["tesla inc.", "tesla motors"],
            keywords=[
                "car",
                "electric",
                "vehicle",
                "elon musk",
                "company",
                "stock",
                "revenue",
                "battery",
                "autopilot",
                "model",
            ],
        ),
        EntityDef(
            entity_id="E0011",
            canonical_name="Nikola Tesla",
            category="person",
            aliases=["nikola tesla"],
            keywords=[
                "inventor",
                "scientist",
                "ac",
                "electricity",
                "coil",
                "patent",
                "history",
                "died",
                "born",
                "invention",
            ],
        ),
    ],
    "meta": [
        EntityDef(
            entity_id="E0005",
            canonical_name="Meta Platforms",
            category="organization",
            aliases=["meta platforms", "facebook", "facebook inc."],
            keywords=[
                "social",
                "network",
                "zuckerberg",
                "company",
                "revenue",
                "ads",
                "instagram",
                "whatsapp",
                "platform",
            ],
        ),
    ],
    "nvidia": [
        EntityDef(
            entity_id="E0007",
            canonical_name="NVIDIA Corporation",
            category="organization",
            aliases=["nvidia corporation"],
            keywords=["gpu", "graphics", "chip", "ai", "jensen huang", "company", "cuda", "datacenter", "gaming"],
        ),
    ],
    "openai": [
        EntityDef(
            entity_id="E0008",
            canonical_name="OpenAI",
            category="organization",
            aliases=["open ai"],
            keywords=["ai", "gpt", "chatgpt", "research", "language model", "sam altman", "company"],
        ),
    ],
    "open ai": [
        EntityDef(
            entity_id="E0008",
            canonical_name="OpenAI",
            category="organization",
            aliases=["open ai", "openai"],
            keywords=["ai", "gpt", "chatgpt", "research", "language model", "sam altman", "company"],
        ),
    ],
    "washington": [
        EntityDef(
            entity_id="E0012",
            canonical_name="Washington (state)",
            category="location",
            aliases=["washington state"],
            keywords=["state", "seattle", "olympia", "evergreen", "west coast"],
        ),
        EntityDef(
            entity_id="E0013",
            canonical_name="Washington, D.C.",
            category="location",
            aliases=["washington dc", "district of columbia"],
            keywords=["capital", "dc", "government", "congress", "white house", "senate", "president", "federal"],
        ),
        EntityDef(
            entity_id="E0014",
            canonical_name="George Washington",
            category="person",
            aliases=["george washington"],
            keywords=["president", "founding father", "revolution", "general", "first", "mount vernon"],
        ),
    ],
    "berkshire hathaway": [
        EntityDef(
            entity_id="E0015",
            canonical_name="Berkshire Hathaway",
            category="organization",
            aliases=["berkshire"],
            keywords=["warren buffett", "investment", "company", "stock", "holding", "revenue", "ceo"],
        ),
    ],
    "jensen huang": [
        EntityDef(
            entity_id="E0016",
            canonical_name="Jensen Huang",
            category="person",
            aliases=["jen hsun huang"],
            keywords=["nvidia", "ceo", "founder", "gpu"],
        ),
    ],
    "tim cook": [
        EntityDef(
            entity_id="E0017",
            canonical_name="Tim Cook",
            category="person",
            aliases=["timothy cook"],
            keywords=["apple", "ceo", "apple inc."],
        ),
    ],
    "elon musk": [
        EntityDef(
            entity_id="E0018",
            canonical_name="Elon Musk",
            category="person",
            aliases=["elon reeve musk"],
            keywords=["tesla", "spacex", "twitter", "x", "ceo", "entrepreneur"],
        ),
    ],
}

_DEFAULT_REGISTRY = EntityRegistry(_DEFAULT_ENTRIES)


# ── LRU Cache (solo entradas independientes de contexto) ─


