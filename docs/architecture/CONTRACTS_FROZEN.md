# Contratos Congelados — Fase 6+7

> **Fecha:** 2026-07-03
> **Versión:** v2.0
> **Estado:** ✅ Congelado. No modificar sin ADR.

---

## 1. Interfaces Congeladas

Las siguientes interfaces se consideran **estables y congeladas**
para toda la Fase 6 y hasta nuevo ADR:

### Embedder(Protocol)

```python
class Embedder(Protocol):
    """Convierte textos en vectores. Opcional y degradable."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convierte textos en vectores. Retorna [] si no disponible."""

    def embed_query(self, text: str) -> list[float]:
        """Embedding optimizado para queries.
        Por defecto: llama a embed([text])[0].
        """

    @property
    def vector_size(self) -> int:
        """Dimensión de los vectores que produce."""

    @property
    def max_input_tokens(self) -> int:
        """Máximo de tokens que el modelo acepta por texto. 0 = desconocido."""

    @property
    def available(self) -> bool:
        """True si el servicio está operativo."""
```

### VectorStore(Protocol)

```python
class VectorStore(Protocol):
    """Almacén vectorial. Opcional y degradable."""

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        """Busca vectores similares. Retorna [] si no disponible.
        filter: dict plano {"campo": "valor"} para v1.
        """

    def upsert(self, items: list[VectorItem]) -> int:
        """Indexa items. Retorna número insertados."""

    def delete(self, asset_ids: list[str]) -> int:
        """Elimina vectores por asset_id."""

    def count(self) -> int:
        """Número total de vectores. 0 si no disponible."""

    def list_ids(
        self, limit: int = 100, offset: str | None = None
    ) -> tuple[list[str], str | None]:
        """Enumera asset_ids almacenados, paginados.
        Retorna (ids, next_offset). next_offset=None = última página.
        """

    @property
    def available(self) -> bool:
        """True si el almacén está operativo."""
```

### Dataclasses

```python
@dataclass(frozen=True)
class VectorItem:
    asset_id: str
    vector: list[float]
    text_preview: str

@dataclass
class VectorResult:
    asset_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

### VectorAugmentedRetriever

```python
class VectorAugmentedRetriever:
    def __init__(
        self,
        graph_retriever: GraphRetriever,
        asset_store: AssetStore,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        rrf_k: int = 60,
    ): ...

    def retrieve_assets(
        self,
        query: str,
        top_k: int = 10,
        use_vector: bool = False,
    ) -> list[KnowledgeAsset]: ...
```

---

## 2. Reglas de Evolución

Estas interfaces pueden evolucionar **solo mediante ADR** y bajo las
siguientes reglas:

### ✅ Permitido (sin ADR)
- Añadir nuevos métodos (backward-compatible)
- Añadir nuevos fields opcionales a dataclasses
- Añadir implementations nuevas del Protocol
- Añadir type aliases

### ⚠️ Requiere ADR
- Añadir methods requeridos al Protocol (los implementadores existentes
  dejarían de cumplir el Protocol)
- Cambiar defaults de métodos existentes
- Añadir fields requeridos a dataclasses

### ❌ Prohibido
- Renombrar o eliminar métodos existentes
- Cambiar firma de métodos existentes (parámetros, tipos, retorno)
- Cambiar comportamiento observado de métodos existentes
- Eliminar dataclasses o sus fields
- Introducir dependencias de backend en los Protocols

---

## 3. Justificación de los 3 Cambios Post-Auditoría

Los siguientes cambios se aplicaron sobre el diseño v0.2.0 como resultado
de `AUDIT_CONTRATOS_FASE6.md` antes de la congelación:

| # | Hallazgo | Corrección | Archivo |
|---|----------|------------|---------|
| B1 | `upsert()` usaba `tuple[str, list[float], str]` frágil y no autodocumentado | `VectorItem` dataclass inmutable | `vector_base.py` |
| B2 | `VectorAugmentedRetriever.retrieve()` inconsistente con `GraphRetriever.retrieve_assets()` | Renombrado a `retrieve_assets()` | `vector_retriever.py` |
| B3 | `_resolve_assets()` necesitaba `AssetStore` no inyectado | Añadido `asset_store: AssetStore` al constructor | `vector_retriever.py` |

---

## 4. Interfaces NO Congeladas (Experimentales)

| Interfaz | Motivo |
|----------|--------|
| `VectorStore.search(filter)` | El `filter: dict[str, Any]` plano es limitado. Se migrará a dataclass tipado en v2. |
| `VectorAugmentedRetriever` (comportamiento completo) | Puede necesitar `reranker`, modos de búsqueda adicionales, múltiples embedders/stores en Fase 7. |
| `VectorStore` post-Fase 7 | Posible `rebuild()`, `optimize()`, `stats()`. `count()` ya está incluido en v1. |

---

## 5. Archivos donde se implementan

| Archivo | Contratos |
|---------|-----------|
| `knowledge/engine/vector_base.py` | `Embedder(Protocol)`, `VectorStore(Protocol)`, `VectorItem`, `VectorResult` |
| `knowledge/engine/vector_ollama.py` | `OllamaEmbedder` (implementa `Embedder`) |
| `knowledge/engine/vector_qdrant.py` | `QdrantVectorStore` (implementa `VectorStore`) |
| `knowledge/engine/vector_retriever.py` | `VectorAugmentedRetriever` |

---

## 6. Fase 7 — Extensiones Congeladas

Las siguientes extensiones se añaden en Fase 7. Son **backward-compatible** con Fase 6
(no modifican interfaces existentes, solo añaden métodos/tablas nuevas).

### 6.1 AssetStore — search_assets()

```python
class AssetStore(Protocol):
    # ... métodos de Fase 6 sin cambios ...

    # NUEVO: Búsqueda FTS5 sobre assets. Fallback a LIKE.
    def search_assets(
        self,
        query: str,
        limit: int = 10,
        asset_type: AssetType | None = None,
    ) -> list[KnowledgeAsset]: ...
```

### 6.2 MetadataExtractionService — Background Queue

```python
class MetadataExtractionService:
    # ... métodos existentes sin cambios (extract, extract_path) ...

    # NUEVOS:
    def queue_extract(self, source: AssetSource) -> str:
        """Encola extracción. Retorna job_id (str)."""

    def get_queue_status(self, job_id: str) -> dict:
        """Estado del job: status, error, result_data, started_at, completed_at."""

    def start_worker(self) -> None:
        """Inicia worker loop en hilo background."""

    def stop_worker(self, timeout: float = 30.0) -> None:
        """Detiene worker loop y termina procesos."""
```

### 6.3 VectorStore — available + check_available

```python
class VectorStore(Protocol):
    # ... métodos de Fase 6 sin cambios ...

    @property
    def available(self) -> bool:
        """O(1), sin side-effects. Refleja último estado conocido."""

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real. HTTP + mutación de estado."""
```

### 6.4 VectorAugmentedRetriever — reconcile

```python
class VectorAugmentedRetriever:
    # ... métodos de Fase 6 sin cambios ...

    def reconcile(
        self,
        dry_run: bool = True,
        batch_size: int = 100,
    ) -> dict[str, int]:
        """Reconcilia AssetStore con VectorStore en batches."""
```

### 6.5 Nuevas tablas SQLite (Schema v14)

| Tabla | Propósito |
|-------|-----------|
| `op_assets_fts` | FTS5 virtual table para búsqueda textual en assets |
| `op_memory_fts` | FTS5 virtual table para búsqueda textual en memorias |
| `op_lineage_edges` | Desnormalizada para queries rápidas de lineage |

| Columna nueva | Tabla | Propósito |
|---------------|-------|-----------|
| `result_data` | `op_jobs` | Comunicación subprocess → worker (JSON) |

### 6.6 VectorAugmentedRetriever — _get_vector_ids

```python
class VectorAugmentedRetriever:
    # ... métodos de Fase 6+7 sin cambios ...

    def _get_vector_ids(self) -> set[str]:
        """Obtiene IDs de todos los vectores vía list_ids() paginada.

        Internamente llama a VectorStore.list_ids() en un loop
        de paginación. Mantiene seen_offsets para detectar y romper
        loops infinitos. Retorna set vacío si VectorStore falla.
        """
```

---

*Contratos congelados — Knowledge Engine — Fase 6+7 — 2026-07-03*
