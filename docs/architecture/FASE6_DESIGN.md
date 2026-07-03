# Fase 6 — Backend Vectorial (Diseño técnico — v0.3.0 Contratos congelados)

> **Versión:** 0.3.0
> **Fecha:** 2026-07-03
> **Estado:** ✅ Contratos congelados (CONTRACTS_FROZEN.md) — listo para implementar
> **Dependencias:** Fase 0–5 completadas, núcleo v0.2.0, Schema v13

---

## 1. Resumen

Añadir un **backend vectorial opcional** a la Capa 11 que permita
enriquecer las búsquedas con similitud semántica (embeddings) y
almacenamiento vectorial (Qdrant).

**Principio**: El backend vectorial es siempre opcional. Sin él, el
sistema funciona exactamente igual (ranking heurístico, Fase 4).
Con él, `VectorAugmentedRetriever` (nuevo wrapper) puede incluir
resultados por similitud coseno en paralelo a los resultados
heurísticos.

**Decisiones arquitectónicas aprobadas (ver AUDIT_FASE6_DESIGN.md):**
- `VectorBackend(Protocol)` → `Embedder(Protocol)` + `VectorStore(Protocol)`
- `CompositeVectorBackend` → eliminado (los Protocols separados lo hacen innecesario)
- `GraphRetriever` → no se modifica. Se crea `VectorAugmentedRetriever` como wrapper
- `text_preview` → Opción B (dato derivado, fuera del dominio)

---

## 2. Contratos: Embedder(Protocol) y VectorStore(Protocol)

Dos Protocols independientes en `knowledge/engine/`:

```python
class Embedder(Protocol):
    """Convierte textos en vectores de forma embedding. Opcional y degradable."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convierte textos en vectores. Retorna lista vacía si no disponible."""

    def embed_query(self, text: str) -> list[float]:
        """Embedding optimizado para queries de búsqueda.
        Por defecto: llama a embed([text])[0].
        Modelos asimétricos (bge, instructor) sobrescriben con instrucción específica.
        """

    @property
    def vector_size(self) -> int:
        """Dimensión de los vectores que produce (auto-detectada)."""

    @property
    def max_input_tokens(self) -> int:
        """Máximo de tokens que el modelo acepta por texto. 0 = desconocido."""

    @property
    def available(self) -> bool:
        """True si el servicio de embeddings está operativo."""
```

```python
class VectorStore(Protocol):
    """Almacén vectorial para búsqueda por similitud. Opcional y degradable."""

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        """Busca vectores similares. Retorna lista vacía si no disponible.
        filter: dict plano {"campo": "valor"} para v1 (equivalencia exacta,
        sin operadores lógicos). Cada backend traduce a su sintaxis nativa.
        """

    def upsert(
        self,
        items: list[VectorItem],
    ) -> int:
        """Indexa items en el almacén vectorial.
        Retorna número de insertados. text_preview es derivado del dominio
        (Opción B), no un campo de KnowledgeAsset.
        """

    def delete(self, asset_ids: list[str]) -> int:
        """Elimina vectores del almacén."""

    def count(self) -> int:
        """Número total de vectores en el almacén. 0 si no disponible."""

    @property
    def available(self) -> bool:
        """True si el almacén vectorial está operativo."""
```

```python
@dataclass(frozen=True)
class VectorItem:
    """Item para indexar en un VectorStore.

    Encapsula la tripleta (asset_id, vector, text_preview) en un
    tipo con nombre, eliminando errores de orden y haciendo el
    contrato autodocumentado.
    """
    asset_id: str
    vector: list[float]
    text_preview: str

@dataclass
class VectorResult:
    asset_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

**Cambios clave desde v0.1.0:**
- `VectorBackend` único → `Embedder` + `VectorStore` (ISP compliance)
- `upsert()` no recibe `KnowledgeAsset` — recibe `list[VectorItem]`
  desacoplando VectorStore de la ontología del dominio
- Zero `NotImplementedError` en implementaciones normales (cada clase implementa
  solo su Protocol)
- `VectorItem` dataclass reemplaza la tupla `(asset_id, vector, text_preview)`
  (resuelve auditoría AUDIT_CONTRATOS_FASE6.md, hallazgo B1)
- `max_input_tokens` y `embed_query()` añadidos a Embedder (hallazgos N1, N2 de AUDIT_CONTRATOS_FASE6_V2.md)
- `count()` añadido a VectorStore (hallazgo N3)
- `filter: dict[str, Any]` documentado como dict plano para v1 (hallazgo N4)

---

## 3. Justificación de la Opción B (text_preview fuera del dominio)

**Decisión:** `text_preview` NO se incorpora a `KnowledgeAsset`.

Razonamiento:
1. **`text_preview` es derivado**: Se genera durante la extracción como
   subproducto (primeros 500 chars del texto plano). No es un atributo
   ontológico del conocimiento, es un artefacto de indexación.
2. **Menor acoplamiento**: Si `text_preview` estuviera en `KnowledgeAsset`,
   cualquier cambio en la política de truncado (500→1000 chars, o摘要
   generado por LLM) requeriría modificar el modelo de dominio.
3. **Separación de concerns**: El dominio modela *qué* es el conocimiento.
   La indexación vectorial decide *cómo* representarlo para búsqueda.
4. **No determinista si cambia**: Si en el futuro el preview se genera
   con un LLM (resumen), dejaría de ser determinista. Mantenerlo fuera
   del dominio protege el determinismo del núcleo.

**Mecanismo**: El suscriptor de `MetadataExtracted` obtiene el
`KnowledgeAsset` de `AssetStore`, llama a `asset.metadata.get("text_preview", "")[:500]`
y pasa ese string a `VectorStore.upsert()` como `VectorItem.text_preview`.
El dominio nunca ve `text_preview`.

---

## 4. Implementaciones

### 4.1 OllamaEmbedder

```python
class OllamaEmbedder:
    """Embedder usando API de embeddings de Ollama.

    Dependencia: httpx (ya disponible).
    URL por defecto: http://localhost:11434/api/embed
    """

    def __init__(self, model: str = "nomic-embed-text",
                 base_url: str = "http://localhost:11434",
                 cache_ttl: int = 300):
        self._model = model
        self._client = httpx.Client(base_url=base_url, timeout=30)
        self._cache: LRUCache[str, list[float]] = LRUCache(ttl=cache_ttl)
        self._degraded = False
        self._vector_size: int = 0
```

**Comportamiento**:
- `embed()`: POST `/api/embed` con `{"model": model, "input": texts}`.
  Cache LRU con TTL 5min (suficiente para monoinstancia GX10).
- `embed_query()`: delega en `embed([text])[0]` (modelo simétrico por defecto).
- `vector_size`: auto-detectado del primer embedding, almacenado en `_vector_size`.
- `max_input_tokens`: consultado vía `/api/show` para el modelo configurado.
  0 si no se puede determinar.
- `available`: True si Ollama responde a `/api/tags`.
- **No tiene `search()`, `upsert()`, `delete()`** — solo es Embedder.

### 4.2 QdrantVectorStore

```python
class QdrantVectorStore:
    """Almacén vectorial usando Qdrant (HTTP directo, sin qdrant-client).

    Dependencia: httpx (ya disponible).
    URL por defecto: http://localhost:6333
    Colección por defecto: ura_assets (dimensión auto-detectada)
    """

    def __init__(self, collection: str = "ura_assets",
                 host: str = "localhost", port: int = 6333,
                 vector_size: int | None = None):
        self._collection = collection
        self._vector_size = vector_size  # None = auto-detect
        self._client = httpx.Client(base_url=f"http://{host}:{port}", timeout=10)
        self._degraded = False
```

**Comportamiento**:
- `search()`: `POST /collections/{name}/points/search` con vector query.
  Payload devuelto: `asset_id`, `asset_type`, `title`, `quality`, `extracted_at`, `text_preview`.
- `upsert(items)`: `PUT /collections/{name}/points`. Cada `VectorItem`
  se serializa a punto Qdrant. La colección se crea automáticamente
  con `vector_size` del primer item si no existe.
- `delete()`: `POST /collections/{name}/points/delete`.
- `count()`: `POST /collections/{name}/points/count`. Retorna 0 si colección no existe.
- `available`: True si Qdrant responde a `/health`.
- **No tiene `embed()`** — solo es VectorStore.
- **Sin `qdrant-client`**: HTTP directo con httpx (elimina dependencia opcional).

### 4.3 Composite eliminado

`CompositeVectorBackend` se elimina. Ya no es necesario porque
`VectorAugmentedRetriever` (ver sección 5) compone directamente
`Embedder + VectorStore + GraphRetriever`.

---

## 5. Integración: VectorAugmentedRetriever

**NO se modifica `GraphRetriever`**. Se crea un nuevo componente independiente:

```python
class VectorAugmentedRetriever:
    """Wrapper que compone GraphRetriever + AssetStore + Embedder + VectorStore + RRF.

    No modifica ninguna clase existente. Delega en GraphRetriever para
    la búsqueda heurística y en Embedder/VectorStore para la semántica.
    AssetStore es necesaria para resolver VectorResult a KnowledgeAsset.
    """

    def __init__(
        self,
        graph_retriever: GraphRetriever,
        asset_store: AssetStore,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        rrf_k: int = 60,
    ):
        self._graph = graph_retriever
        self._asset_store = asset_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._rrf_k = rrf_k

    def retrieve_assets(
        self,
        query: str,
        top_k: int = 10,
        use_vector: bool = False,
    ) -> list[KnowledgeAsset]:
        # 1. Búsqueda heurística (siempre)
        heuristic = self._graph.retrieve_assets(query, top_k=top_k)

        # 2. Búsqueda vectorial (opcional)
        vector: list[KnowledgeAsset] = []
        if use_vector and self._embedder and self._embedder.available and self._vector_store and self._vector_store.available:
            query_vec = self._embedder.embed_query(query)
            if query_vec:
                vec_hits = self._vector_store.search(query_vec, top_k=top_k)
                vector = self._resolve_assets(vec_hits)

        # 3. Fusión RRF
        return self._fuse(heuristic, vector, top_k)

    def _resolve_assets(self, results: list[VectorResult]) -> list[KnowledgeAsset]:
        """Resuelve VectorResults a KnowledgeAssets via AssetStore."""
        return [
            asset for r in results
            if (asset := self._asset_store.get_asset(r.asset_id)) is not None
        ]

    def _fuse(self, heuristic: list[KnowledgeAsset],
              vector: list[KnowledgeAsset], top_k: int) -> list[KnowledgeAsset]:
        """Reciprocal Rank Fusion con k=60."""
        scores: dict[str, float] = {}
        for rank, a in enumerate(heuristic):
            scores[a.asset_id] = 1.0 / (self._rrf_k + rank)
        for rank, a in enumerate(vector):
            scores[a.asset_id] = scores.get(a.asset_id, 0.0) + 1.0 / (self._rrf_k + rank)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        asset_map = {a.asset_id: a for a in heuristic + vector}
        return [asset_map[aid] for aid, _ in ranked[:top_k]]
```

**Por qué esto evita modificar GraphRetriever:**
- `GraphRetriever.retrieve_assets()` no se toca
- `VectorAugmentedRetriever` es un nuevo componente que *compone* el existente
- El API público (o la CLI) puede instanciar `VectorAugmentedRetriever` en
  lugar de `GraphRetriever` cuando se desee búsqueda vectorial, usando
  `retrieve_assets()` con la misma firma que `GraphRetriever.retrieve_assets()`
- `GraphRetriever` sigue funcionando exactamente igual sin cambios

---

## 6. Eventos

### 6.1 Evento: MetadataExtracted

```python
@dataclass
class MetadataExtracted:
    asset_id: str
    asset_type: AssetType
    extractor: str
    success: bool
    duration_ms: float
```

### 6.2 Suscriptor: _make_vector_index_subscriber()

```python
def _make_vector_index_subscriber(store: AssetStore,
                                   embedder: Embedder,
                                   vector_store: VectorStore):
    def handler(event: MetadataExtracted) -> None:
        if not event.success:
            return
        asset = store.get_asset(event.asset_id)
        if asset is None:
            return
        text = asset.metadata.get("text_preview", "")[:500]
        if not text:
            return
        # Truncar según límite del modelo si está disponible
        max_chars = min(500, embedder.max_input_tokens * 4) if embedder.max_input_tokens else 500
        truncated = text[:max_chars]
        vectors = embedder.embed([truncated])
        if vectors:
            item = VectorItem(asset_id=event.asset_id, vector=vectors[0], text_preview=text)
            vector_store.upsert([item])
    return handler
```

El suscriptor se registra en `subscribe_all()` dentro de `subscribers.py`
(mismo patrón que G04a en Fase 4b). No se modifica `eventbus.py`.

### 6.3 Payload en Qdrant

```json
{
  "vector": [0.1, 0.2, ...],   // 768-dim float[]
  "payload": {
    "asset_id": "abc123",
    "asset_type": "pdf",
    "title": "...",
    "quality": 0.85,
    "extracted_at": "2026-07-03T...",
    "text_preview": "..."
  }
}
```

`text_preview` truncado a 500 chars (límite Qdrant payload ~1MB,
pero por consistencia se trunca igual que en el suscriptor).

---

## 7. Degradación Graceful

| Escenario | Comportamiento |
|-----------|----------------|
| Ollama caído | `OllamaEmbedder.available = False`. `VectorAugmentedRetriever` solo usa búsqueda heurística. |
| Qdrant caído | `QdrantVectorStore.available = False`. No hay búsqueda vectorial. Embeddings generados pero no almacenados. |
| Ambos caídos | Sistema funciona sin backend vectorial (comportamiento Fase 4). |
| Timeout embeddings (30s) | Retry 2x. Si persiste → `_degraded = True`. Log warning. |
| Timeout Qdrant (10s) | Retry 1x. Si persiste → `_degraded = True`. Log warning. |
| Colección no existe | `upsert()` crea la colección con `vector_size` del primer item. |
| Vector size mismatch | Error loggeado. No upsert. Degradación graceful. |
| Embeddings vacíos | `embed()` retorna `[]`. `search()` no se ejecuta. |

---

## 8. Archivos Nuevos (solo Capa 11)

| Archivo | Propósito |
|---------|-----------|
| `knowledge/engine/vector_base.py` | `Embedder(Protocol)`, `VectorStore(Protocol)`, `VectorItem`, `VectorResult` |
| `knowledge/engine/vector_ollama.py` | `OllamaEmbedder` (solo embed) |
| `knowledge/engine/vector_qdrant.py` | `QdrantVectorStore` (search/upsert/delete/count, HTTP directo) |
| `knowledge/engine/vector_retriever.py` | `VectorAugmentedRetriever` (wrapper que compone GraphRetriever + Embedder + VectorStore) |

**4 archivos** (antes 4 + 1 composite = 5). Ninguno del núcleo se modifica.

`scripts/pro/reindex_vectors.py` — script para re-indexación batch de
assets existentes (no forma parte de la Fase 6, se documenta para Fase 7).

---

## 9. Tests Propuestos

| Test | Objetivo | Propósito |
|------|----------|-----------|
| `test_embed_texts` | OllamaEmbedder | `embed()` retorna vectores de dimensión correcta |
| `test_embed_empty` | OllamaEmbedder | Lista vacía → lista vacía |
| `test_embed_cache_hit` | OllamaEmbedder | Mismo texto → cache, no llama a API |
| `test_embed_cache_ttl` | OllamaEmbedder | Cache expira tras TTL |
| `test_search_similar` | QdrantVectorStore | `search()` retorna resultados ordenados por score |
| `test_search_empty` | QdrantVectorStore | Sin vectores → lista vacía |
| `test_upsert_items` | QdrantVectorStore | `upsert([VectorItem(id, vec, txt)])` → puntos creados |
| `test_upsert_auto_create` | QdrantVectorStore | Colección se crea si no existe |
| `test_delete` | QdrantVectorStore | Eliminación de puntos |
| `test_degraded_ollama` | Integration | Ollama caído → embedder.available=False |
| `test_degraded_qdrant` | Integration | Qdrant caído → store.available=False |
| `test_retriever_heuristic_only` | VectorAugmentedRetriever | Sin embedder/store → solo heurístico |
| `test_retriever_vector` | VectorAugmentedRetriever | Con ambos → RRF fusiona resultados |
| `test_retriever_rrf` | VectorAugmentedRetriever | RRF con rankings conocidos |
| `test_subscriber_upserts` | Integration | MetadataExtracted → upsert automático |
| `test_subscriber_no_text` | Integration | Asset sin text_preview → no upsert |
| `test_subscriber_failed_extraction` | Integration | success=False → no upsert |
| `test_determinism_embed` | OllamaEmbedder | Mismos textos → mismos vectores (seed fijo) |
| `test_embed_query` | OllamaEmbedder | `embed_query` retorna vector correcto |
| `test_max_input_tokens` | OllamaEmbedder | `max_input_tokens` retorna valor > 0 o 0 |
| `test_count` | QdrantVectorStore | `count()` retorna número de vectores |
| `test_filter_flat_dict` | QdrantVectorStore | Filtro plano `{"asset_type": "pdf"}` funciona |
| `test_upsert_empty` | QdrantVectorStore | `upsert([])` → retorna 0 sin error |
| `test_delete_nonexistent` | QdrantVectorStore | `delete(["fake_id"])` → retorna 0 (idempotente) |
| `test_count_empty` | QdrantVectorStore | `count()` en store vacío → 0 |
| `test_retriever_embedder_only` | VectorAugmentedRetriever | embedder presente, vector_store=None → solo heurístico |
| `test_retriever_store_only` | VectorAugmentedRetriever | vector_store presente, embedder=None → solo heurístico |
| `test_subscriber_backend_down` | Integration | embedder/vector_store no disponible → handler no crashea |
| `test_subscriber_asset_missing` | Integration | asset no existe en AssetStore → handler no crashea |

**Total estimado**: 28–34 tests nuevos.

**Mocking**: httpx respuestas simuladas. Sin conexión real a Ollama/Qdrant.

---

## 10. Dependencias

| Dependencia | Obligatoria | Para |
|-------------|-------------|------|
| `httpx` | ✅ Sí (ya existe) | API Ollama + API Qdrant |

`qdrant-client` se elimina como dependencia opcional. Todo el tráfico
a Qdrant es HTTP directo con httpx (ya disponible). Esto elimina una
dependencia externa y simplifica el mantenimiento.

No se añaden dependencias obligatorias nuevas.

---

## 11. Riesgos y Decisiones Cerradas

| Riesgo/Decisión | Resolución |
|-----------------|------------|
| **ISP violation** | ✅ `VectorBackend` → `Embedder` + `VectorStore` |
| **GraphRetriever coupling** | ✅ No se modifica. `VectorAugmentedRetriever` como wrapper |
| **Composite overengineering** | ✅ Eliminado. Protocols separados lo hacen innecesario |
| **Gap de contenido** | ✅ Opción B: `text_preview` fuera del dominio, el suscriptor puentea |
| **Dimensión de vectores** | ✅ Auto-detectada del primer embedding. Fallback configurable 768 |
| **Cache de embeddings** | ✅ LRU in-process TTL 5min (suficiente para GX10 monoinstancia) |
| **Payload en Qdrant** | ✅ Solo `asset_id`, `type`, `title`, `quality`, `extracted_at`, `text_preview[:500]` |
| **Re-indexación** | ✅ Script independiente `scripts/pro/reindex_vectors.py` |
| **qdrant-client** | ✅ Eliminado. HTTP directo con httpx. |
| **No-determinismo** | ✅ Aceptado: `retrieve_assets(use_vector=True)` no es determinista por definición (embeddings variables). |
| **Sincronización AssetStore↔VectorStore** | ⚠️ Diferido a Fase 7. Sin reconciliación automática: asset eliminado → vector huérfano, suscriptor falla → asset sin vector, cambio de embedder → todos los vectores inválidos. Se abordará con job periódico de reconciliación en Fase 7. |

---

## 12. Lo que NO incluye esta Fase

- ❌ No se modifica `GraphRetriever`
- ❌ No se modifica `eventbus.py`
- ❌ No se modifica `AssetStore`
- ❌ No se añaden endpoints REST para búsqueda vectorial directa
- ❌ No se implementa re-rank con LLM (reservado para fase posterior)
- ❌ No se modifica el CLI existente
- ❌ No se incluye `reindex_vectors.py` (se documenta, se implementa en Fase 7)

---

## 13. Criterios de Aceptación

1. ✅ `Embedder(Protocol)` + `VectorStore(Protocol)` definidos e implementados
2. ✅ Degradación graceful: sin Qdrant/Ollama → sistema funciona igual
3. ✅ RRF fusiona correctamente resultados heurísticos y vectoriales
4. ✅ `VectorAugmentedRetriever.retrieve_assets(use_vector=True)` funciona end-to-end
5. ✅ MetadataExtracted → suscriptor → upsert automático
6. ✅ 28+ tests nuevos pasando (todos los métodos con test positivo, negativo, degradación y determinismo)
7. ✅ Sin regresiones en los 236 tests existentes
8. ✅ Sin modificaciones al núcleo ni a módulos de Fase 0–5
9. ✅ Zero `NotImplementedError` en implementaciones normales
10. ✅ `upsert()` no conoce `KnowledgeAsset` (recibe `list[VectorItem]`)

---

*Documento de diseño v0.3.0 — Contratos congelados — Knowledge Engine — Fase 6 — 2026-07-03*
