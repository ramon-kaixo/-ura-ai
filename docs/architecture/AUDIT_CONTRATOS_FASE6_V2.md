# Auditoría de Contratos Públicos — Fase 6 (v2 — Pre-implementación)

> **Fecha:** 2026-07-03
> **Documento auditado:** `FASE6_DESIGN.md` v0.2.0
> **Alcance:** Únicamente contratos públicos: `Embedder(Protocol)`,
>   `VectorStore(Protocol)`, `VectorAugmentedRetriever`
> **NO cubre:** Arquitectura general, código, tests, rendimiento

---

## Resumen Ejecutivo

Los Protocols son conceptualmente sólidos y están cerca de poder
congelarse. Se identifican **3 defectos que requieren corrección**
(uno más que en la auditoría previa), **3 omisiones relevantes**
y **1 responsabilidad ausente** del diseño global que debe
documentarse como riesgo.

**Veredicto: ⚠️ Aprobado con observaciones**
(3 correcciones requeridas antes de implementar)

---

## 1. Embedder(Protocol) — Análisis de estabilidad

### Contrato actual

```python
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def vector_size(self) -> int: ...
    @property
    def available(self) -> bool: ...
```

### 1.1 ¿Qué falta?

**🔴 Hallazgo 1: Falta `max_input_tokens`.**

```python
@property
def max_input_tokens(self) -> int:
    """Máximo de tokens que el modelo acepta por texto. 0 = desconocido."""
```

**Problema**: Sin este límite, el orquestador no puede decidir cuándo
truncar. Si un asset de 8000 tokens se envía a un modelo con límite
de 512, el embedding resultante representa solo los primeros 512 tokens
(el resto se trunca silenciosamente en la API). El orquestador no tiene
forma de saber que el embedding es incompleto.

**Impacto**: El orquestador produce vectores de calidad desconocida para
textos largos. Esto afecta la calidad del ranking RRF sin que el
llamante pueda detectarlo.

**Corrección**: Añadir `max_input_tokens` como property. Todas las
implementaciones pueden proporcionarlo: OllamaEmbedder lo obtiene del
modelo, OpenAIEmbedder de la documentación, etc. Valor 0 = desconocido
(comportamiento degradado).

**🔴 Hallazgo 2: Falta `embed_query()` para modelos asimétricos.**

```python
def embed_query(self, text: str) -> list[float]:
    """Embedding optimizado para queries de búsqueda.
    Por defecto: llama a embed([text])[0].
    Modelos asimétricos (bge, instructor) sobrescriben con instrucción específica.
    """
```

**Problema**: Modelos como `bge-large` o `instructor-xl` usan instrucciones
distintas para queries ("Represent this sentence for searching...") vs
documentos ("Represent this document for indexing..."). Sin `embed_query()`,
el orquestador trata queries y documentos igual, perdiendo precisión.

**Impacto**: El ranking híbrido es subóptimo con modelos asimétricos.

**Corrección**: Añadir `embed_query()` con implementación por defecto
que delega en `embed([text])[0]`. Las implementaciones simétricas no
necesitan cambiar. Las asimétricas sobrescriben. Zero breaking change.

### 1.2 ¿Qué sobra?

Nada. Los 3 métodos actuales son esenciales.

### 1.3 Estabilidad a largo plazo

| Escenario futuro | ¿Protocol soporta? |
|------------------|-------------------|
| Nuevo modelo local (Ollama) | ✅ Solo implementar Protocol |
| Nuevo modelo remoto (OpenAI, Anthropic) | ✅ Misma interfaz |
| Modelo cambia de dimensión | ✅ `vector_size` se actualiza |
| Múltiples modelos | ✅ Crear CompositeEmbedder o lista en constructor |
| Cache LRU | ✅ Implementación interna, no del Protocol |
| Batch de 1000 textos | ✅ `embed(texts)` ya es batch |
| Texto de 100K tokens | ⚠️ `max_input_tokens` necesaria para truncar correctamente |
| Embeddings asimétricos query/document | ⚠️ `embed_query()` necesaria para precisión |

**Veredicto: ⚠️ Faltan `max_input_tokens` y `embed_query` para
estabilidad multianual. Sin ellas, el contrato es correcto pero
incompleto.**

---

## 2. VectorStore(Protocol) — Análisis multi-backend

### Contrato actual

```python
class VectorStore(Protocol):
    def search(self, query_vector, top_k=10, filter=None) -> list[VectorResult]: ...
    def upsert(self, items: list[tuple[str, list[float], str]]) -> int: ...
    def delete(self, asset_ids: list[str]) -> int: ...
    @property
    def available(self) -> bool: ...
```

### 2.1 ¿Implementable en cada backend sin cambios?

| Backend | `search()` | `upsert()` | `delete()` | `available` |
|---------|-----------|------------|------------|-------------|
| **SQLite** | ⚠️ Full scan + cosine sim en Python. Sin índice vectorial. Funcional hasta ~10K vectores. | ✅ INSERT OR REPLACE. Vectors como BLOBs. | ✅ DELETE WHERE id IN (...). | ✅ Siempre True |
| **Qdrant** | ✅ Nativo. `POST /collections/{name}/points/search`. | ✅ Nativo. `PUT /collections/{name}/points`. | ✅ Nativo. `POST /collections/{name}/points/delete`. | ✅ Health check |
| **FAISS** | ✅ `index.search(query, top_k)`. Retorna IDs + scores. | ⚠️ Parcial. `index.add_with_ids()` inserta pero NO actualiza. No hay "update". Para upsert real: `IDMap.remove_ids()` + `add_with_ids()`. | 🔴 No soporta eliminación. `IDMap.remove_ids()` existe pero es frágil. Reconstruir índice es la opción real. | ✅ Siempre True |
| **Milvus** | ✅ Nativo. `search()`. | ✅ Nativo. `upsert()`. | ✅ Nativo. `delete()`. | ✅ Health check |
| **pgvector** | ✅ `ORDER BY vector <=> query LIMIT top_k`. Con índice IVFFlat/HNSW. | ✅ `INSERT ... ON CONFLICT DO UPDATE`. | ✅ `DELETE WHERE id = ANY(...)`. | ✅ Conexión |

**🔴 Hallazgo 3: `upsert()` no es implementable correctamente en FAISS.**

FAISS no tiene operación de upsert nativa. `IDMap.remove_ids()` + `add_with_ids()`
funciona pero:
- Requiere reconstruir el índice periódicamente (fragmentación)
- No es atómico (entre remove y add, la búsqueda da resultados incompletos)
- `remove_ids()` falla si el ID no existe (no es idempotente)

**Corrección**: No modificar el Protocol — es correcto que pida `upsert()`.
La implementación FAISS debe documentar que su `upsert()` es
**eventualmente consistente** (necesita `optimize()` periódico). Esto es
una limitación de FAISS, no del contrato.

### 2.2 Operaciones mínimas: ¿qué falta?

| Operación | ¿En Protocol? | Necesidad |
|-----------|--------------|-----------|
| **upsert** | ✅ `upsert(items)` | ✅ Esencial |
| **delete** | ✅ `delete(asset_ids)` | ✅ Esencial |
| **search** | ✅ `search(query, top_k, filter)` | ✅ Esencial |
| **batch** | ✅ `upsert(items)` acepta lista. `delete(asset_ids)` acepta lista. | ✅ Ambas son batch |
| **stats** | ❌ No existe `count()` | ⚠️ Necesaria para observabilidad: ¿cuántos vectores hay? ¿la re-indexación terminó? |
| **health** | ✅ `available` property | ✅ Esencial |
| **maintenance** | ❌ No existe `rebuild()` ni `optimize()` | ⚠️ Necesaria para FAISS (reconstrucción periódica) y Qdrant (optimización de índice) |

### 2.3 El problema del `filter` (confirmado)

`filter: dict[str, Any]` es incompatible entre backends:

| Backend | Sintaxis de filtro |
|---------|-------------------|
| Qdrant | `{"must": [{"key": "type", "match": {"value": "pdf"}}]}` |
| Milvus | `{"type": {"$eq": "pdf"}}` |
| pgvector | `WHERE type = 'pdf'` (SQL) |
| FAISS | No tiene filtros. Ignora. |
| SQLite | Aplicación en Python post-query |

**Un mismo `dict` produce comportamientos distintos en cada backend.**
Esto viola el principio de que un Protocol debe comportarse igual
independientemente de la implementación.

**Corrección propuesta**: Para v1, documentar explícitamente que el
`filter` tiene una sintaxis plana `{"campo": "valor"}` (equivalencia
exacta, sin operadores lógicos). Cada backend la traduce a su sintaxis
nativa. Esto es limitado pero consistente entre backends.

O mejor: eliminar `filter` del contrato base y permitir que cada
implementación ofrezca filtros como extensión propia. `VectorAugmentedRetriever`
hace post-filtrado en Python si es necesario.

### 2.4 Veredicto VectorStore

| Criterio | Estado |
|----------|--------|
| CRUD completo | ⚠️ Falta `count()`. `upsert` problemático en FAISS. |
| Multi-backend | ✅ Contrato portable. FAISS requiere `rebuild()` para mantenimiento. |
| Batch | ✅ `upsert` y `delete` aceptan listas |
| `filter` consistente | 🔴 `dict[str, Any]` produce comportamientos distintos por backend |
| `upsert` firma | 🔴 Tupla cruda → debe ser `VectorItem` dataclass (de auditoría previa) |

---

## 3. VectorAugmentedRetriever — Verificación de orquestador

### Contrato actual

```python
class VectorAugmentedRetriever:
    def __init__(self, graph_retriever, embedder=None, vector_store=None, rrf_k=60): ...
    def retrieve(self, query, top_k=10, use_vector=False) -> list[KnowledgeAsset]: ...
```

### 3.1 ¿GraphRetriever completamente independiente? ✅

- Inyectado en constructor
- Nunca importado directamente
- No se modifica, no se extiende, no se parchea
- `VectorAugmentedRetriever` solo llama a `graph_retriever.retrieve_assets()`

### 3.2 ¿Lógica de dominio nueva? ✅

No. La clase orquesta cuatro operaciones:
1. `graph_retriever.retrieve_assets(query)` → búsqueda existente
2. `embedder.embed([query])` → vectorización
3. `vector_store.search(query_vec)` → búsqueda vectorial
4. `_fuse(heuristica, vectorial)` → RRF (algoritmo puro, 15 líneas)

No crea KnowledgeAssets. No modifica el grafo. No persiste nada.

### 3.3 ¿Acoplamiento con Qdrant? ✅

Cero. QdrantVectorStore implementa VectorStore(Protocol).
VectorAugmentedRetriever solo conoce VectorStore. Qdrant es invisible.

### 3.4 Defecto previo confirmado: falta `asset_store` en constructor

`_resolve_assets()` necesita AssetStore para convertir `VectorResult` →
`KnowledgeAsset`. No está en el constructor. Debe añadirse.

### 3.5 Defecto previo confirmado: `retrieve()` debe ser `retrieve_assets()`

Inconsistencia con `GraphRetriever.retrieve_assets()`. Corregir.

---

## 4. Evolución futura — Compatibilidad

| Escenario futuro | Contrato actual | ¿Funciona? |
|-----------------|-----------------|------------|
| **Múltiples embedders** | Embedder único en constructor | ⚠️ Añadir `embedders: list[Embedder]` o crear `CompositeEmbedder(Embedder)` |
| **Múltiples vector stores** | VectorStore único en constructor | ⚠️ Igual que embedders. `CompositeVectorStore(VectorStore)` o lista |
| **Reranker (re-rank)** | No existe | 🔴 **Genuina ausencia.** No hay `Reranker(Protocol)`. Sería Fase 7. |
| **Búsqueda híbrida** | `use_vector: bool` | ⚠️ Booleano suficiente para v1. Tres modos (heuristic/vector/hybrid) requerirían enum. |
| **GraphRAG avanzado** | Solo `retrieve_assets()` | ⚠️ `retrieve_memory()`, `retrieve_neighbors()`, `build_context()` no están aumentados. |
| **Modelos locales y remotos** | Embedder(Protocol) | ✅ Misma interfaz para Ollama (local) y OpenAI (remoto). |
| **Embeddings asimétricos** | `embed()` simétrico | ⚠️ `embed_query()` necesaria para precisión con modelos bge/instructor. |

### 🔴 Reranker: la ausencia más notable

El pipeline natural de búsqueda moderna es:

```
query → embed → vector search → candidates → RERANKER → top-k
```

VectorAugmentedRetriever implementa `embed → search → fuse (RRF)`.
Pero no hay lugar para un reranker después del vector search. El reranker
es el componente que más impacto tiene en calidad de búsqueda (más que
el embedding), y no está considerado.

**No es bloqueante** para v1, pero debe documentarse como evolución
natural para v2. El diseño de VectorAugmentedRetriever debería permitir
inyectar un reranker sin cambiar la API pública:

```python
# Futuro (v2):
class VectorAugmentedRetriever:
    def __init__(self, graph_retriever, embedder=None,
                 vector_store=None, reranker=None, rrf_k=60):
        self._reranker = reranker
```

---

## 5. Congelación de interfaces

### ✅ Pueden congelarse ahora (estables)

| Interfaz | Versión | Notas |
|----------|---------|-------|
| `Embedder(Protocol)` | v1.0 | ✅ Después de añadir `max_input_tokens` y `embed_query()` |
| `VectorResult` | v1.0 | ✅ Frozen |
| `VectorItem` | v1.0 | ✅ Frozen (crear antes de implementar) |

### ⚠️ Experimentales (no congelar)

| Interfaz | Versión | Motivo |
|----------|---------|--------|
| `VectorAugmentedRetriever` | v0.9 | El patrón de orquestación puede necesitar refinamiento. Reranker, modos de búsqueda, multi-embedder. |
| `VectorStore.search(filter)` | v0.9 | El `filter` es demasiado débil. Pendiente de definir un schema cross-backend. |
| `VectorStore(Protocol)` | v0.9 | Falta `count()`. Posible necesidad de `rebuild()` para FAISS. |

### ❌ Requerirán cambios en futuras fases

| Interfaz | Fase | Cambio esperado |
|----------|------|-----------------|
| `VectorAugmentedRetriever.__init__` | Fase 7 | Aceptar reranker, múltiples embedders/stores |
| `VectorAugmentedRetriever.retrieve_assets()` | Fase 7 | Más modos de búsqueda (solo vectorial, solo reranker) |
| `VectorStore` | Post-Fase 7 | Posible `rebuild()`, `optimize()`, `count()` como obligatorio |

---

## 6. Auditoría Inversa

### ¿Qué responsabilidad importante no aparece en el diseño de Fase 6?

**🔴 Responsabilidad ausente: Sincronización garantizada entre AssetStore y VectorStore.**

El diseño asume que:
1. MetadataExtracted → suscriptor → upsert en VectorStore
2. Asset eliminado → ¿? → nada borra el vector
3. Embedder cambia → ¿? → todos los vectores existentes son inválidos
4. Suscriptor falla → ¿? → asset existe, vector no, nadie lo detecta

**El sistema no garantiza que AssetStore y VectorStore estén sincronizados.**

Casos de divergencia silenciosa:

| Evento | AssetStore | VectorStore | ¿Detectable? |
|--------|-----------|-------------|-------------|
| Extracción exitosa, suscriptor falla | ✅ Asset existe | ❌ Vector no existe | No |
| Asset eliminado | ❌ No existe | ✅ Vector huérfano | No |
| Re-extracción (mismo asset_id, nuevo texto) | ✅ Texto actualizado | ⚠️ Vector puede estar cacheado (stale) | No |
| Embedder cambia | ✅ Assets intactos | ❌ Todos los vectores en espacio semántico incorrecto | No |

**Esto no es un defecto del Protocol**, es una responsabilidad
**del sistema** que no está asignada en el diseño de Fase 6.

**Recomendación**: No implementar ahora (sería Fase 7). Pero **documentar
explícitamente** en FASE6_DESIGN.md que la sincronización entre stores
es una responsabilidad diferida, con una nota de riesgo:

> **Riesgo conocido**: Fase 6 no implementa reconciliación entre
> AssetStore y VectorStore. La divergencia silenciosa es posible.
> En Fase 7 se abordará con un job de reconciliación periódico
> que compare `op_assets` vs vectores indexados y corrija
> discrepancias.

---

## 7. Resumen de Hallazgos

### 🔴 Bloqueantes (corregir antes de implementar)

| # | Hallazgo | Corrección |
|---|----------|------------|
| B1 | `upsert()` usa tupla `tuple[str, list[float], str]` → frágil | Crear `VectorItem(asset_id, vector, text_preview)` dataclass |
| B2 | `retrieve()` inconsistente con `GraphRetriever.retrieve_assets()` | Renombrar a `retrieve_assets()` |
| B3 | `_resolve_assets()` necesita AssetStore pero no está en constructor | Añadir `asset_store: AssetStore` al `__init__` |

### ⚠️ No bloqueantes (corregir antes de congelar, o en v1.1)

| # | Hallazgo | Corrección propuesta |
|---|----------|---------------------|
| N1 | `Embedder` sin `max_input_tokens` | Añadir property. El orquestador la necesita para truncar. |
| N2 | `Embedder` sin `embed_query()` | Añadir método con default que delega en `embed()`. Breaking change cero. |
| N3 | `VectorStore` sin `count()` | Añadir `count() -> int`. Necesaria para observabilidad. |
| N4 | `filter: dict[str, Any]` produce comportamiento inconsistente | Documentar filtro plano `{"campo": "valor"}` para v1. Migrar a dataclass en v2. |

### 📝 Riesgos documentados (no requieren acción ahora)

| # | Riesgo | Plan |
|---|--------|------|
| R1 | Sin `Reranker(Protocol)` | Fase 7 |
| R2 | Sin reconciliación AssetStore↔VectorStore | Fase 7 — job periódico |
| R3 | FAISS no soporta `upsert()` atómico | Documentar eventual consistency |
| R4 | Cache LRU puede servir embeddings stale | Aceptado para v1. TTL 5min mitiga. |
| R5 | Cambio de embedder invalida todos los vectores | Fase 7 — versionado de colecciones |

---

## 8. Recomendaciones para la implementación

### Orden de implementación sugerido

```
1. VectorItem dataclass (B1)
2. vector_base.py: Embedder + VectorStore Protocols (con N1, N2, N3)
3. vector_base.py: VectorResult + VectorItem dataclasses
4. vector_ollama.py: OllamaEmbedder
5. vector_qdrant.py: QdrantVectorStore
6. vector_retriever.py: VectorAugmentedRetriever (con B2, B3)
7. Tests (mock httpx)
8. Suscriptor MetadataExtracted
```

### Forma final recomendada de los Protocols

```python
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    @property
    def vector_size(self) -> int: ...
    @property
    def max_input_tokens(self) -> int: ...
    @property
    def available(self) -> bool: ...

class VectorStore(Protocol):
    def search(self, query_vector: list[float],
               top_k: int = 10,
               filter: Filter | None = None) -> list[VectorResult]: ...
    def upsert(self, items: list[VectorItem]) -> int: ...
    def delete(self, asset_ids: list[str]) -> int: ...
    def count(self) -> int: ...
    @property
    def available(self) -> bool: ...

@dataclass
class VectorItem:
    asset_id: str
    vector: list[float]
    text_preview: str

@dataclass
class VectorResult:
    asset_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

class VectorAugmentedRetriever:
    def __init__(self, graph_retriever: GraphRetriever,
                 asset_store: AssetStore,
                 embedder: Embedder | None = None,
                 vector_store: VectorStore | None = None,
                 rrf_k: int = 60): ...
    def retrieve_assets(self, query: str,
                        top_k: int = 10,
                        use_vector: bool = False) -> list[KnowledgeAsset]: ...
```

---

*Auditoría de contratos públicos v2 — Fase 6 — 2026-07-03*
*Veredicto: ⚠️ Aprobado con observaciones — corregir B1, B2, B3 antes de implementar*
