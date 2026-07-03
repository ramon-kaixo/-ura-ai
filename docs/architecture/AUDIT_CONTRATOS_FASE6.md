# Auditoría de Contratos Públicos — Fase 6 (Protocols e Interfaces)

> **Fecha:** 2026-07-03
> **Documento auditado:** `FASE6_DESIGN.md` v0.2.0
> **Alcance:** Exclusivamente `Embedder(Protocol)`, `VectorStore(Protocol)`,
>   `VectorAugmentedRetriever` y nombres públicos
> **NO cubre:** Arquitectura general, rendimiento, código, tests

---

## 1. Embedder(Protocol)

### Contrato actual (sección 2 de FASE6_DESIGN.md)

```python
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def vector_size(self) -> int: ...
    @property
    def available(self) -> bool: ...
```

### 1.1 ¿Es mínima pero suficiente?

**Sí, es mínima.** Tres operaciones: embed, consultar dimensión, consultar
disponibilidad. No sobra nada.

**Parcialmente suficiente.** El contrato omite información sobre las
**capacidades del modelo** que el orquestador necesita para tomar decisiones:

| Ausencia | Problema | Ejemplo |
|----------|----------|---------|
| `max_input_tokens: int` | El orquestador no sabe cuándo truncar | Un texto de 8000 tokens se envía a un modelo con límite de 512 → error silencioso o embedding truncado |
| `embed_query(query: str) -> list[float]` | Algunos modelos (instructor-xl, bge) usan instrucciones distintas para query vs documento | El ranking RRF podría mejorarse con embeddings asimétricos, pero el Protocol no lo permite |

**Veredicto sobre suficiencia:**

Para v1, el contrato es suficiente. `max_input_tokens` y `embed_query` son
optimizaciones que pueden añadirse en versiones posteriores sin romper
compatibilidad (métodos nuevos en un Protocol son backward-compatible).

**⚠️ Recomendación**: Documentar en el docstring del Protocol que
`embed(texts)` es de propósito general (symmetric embedding) y que
implementaciones futuras pueden añadir `embed_query()` como extensión.

### 1.2 Casos frontera no especificados

| Input | Comportamiento esperado | ¿Documentado? |
|-------|------------------------|----------------|
| `embed([])` → `[]` | Lista vacía → lista vacía | ❌ No |
| `embed(["", "a"])` → `[[0,...], [0,...]]` | Texto vacío produce vector (embedding de string vacío) | ❌ No |
| `embed(["x"] * 1000)` → `list[list[float]]` | Lotes grandes se manejan internamente | ❌ No |
| Modelo cambia `vector_size` entre calls | ¿Error? ¿Degradación? | ❌ No |

Estos no requieren cambios en el Protocol, pero deben documentarse como
contrato implícito en la implementación de referencia (`OllamaEmbedder`).

### 1.3 Veredicto: Embedder(Protocol)

| Criterio | Estado |
|----------|--------|
| Mínimo | ✅ Sí (3 métodos, sin redundancia) |
| Suficiente | ✅ Para v1. `max_input_tokens` y `embed_query` son extensibles post-v1 |
| Casos frontera documentados | ⚠️ No. Añadir al docstring del Protocol |
| Degradación | ✅ `available` property |

---

## 2. VectorStore(Protocol)

### Contrato actual (sección 2 de FASE6_DESIGN.md)

```python
class VectorStore(Protocol):
    def search(self, query_vector: list[float], top_k: int = 10,
               filter: dict[str, Any] | None = None) -> list[VectorResult]: ...
    def upsert(self, items: list[tuple[str, list[float], str]]) -> int: ...
    def delete(self, asset_ids: list[str]) -> int: ...
    @property
    def available(self) -> bool: ...
```

### 2.1 Operaciones CRUD: ¿completa?

| Operación | Método | ¿Suficiente? |
|-----------|--------|--------------|
| Create | `upsert` (inserta si no existe) | ✅ |
| Read (by similarity) | `search` | ✅ |
| Read (by ID) | ❌ No existe | ⚠️ Ausencia justificada: el caso de uso primario es búsqueda semántica. Para leer por ID se usa `AssetStore.get_asset()`. |
| Update | `upsert` (actualiza si existe) | ✅ |
| Delete | `delete(asset_ids)` | ✅ |
| List all | ❌ No existe | ⚠️ Ausencia justificada: para v1 no se necesita. Útil para debugging pero no crítico. |
| Count | ❌ No existe | ⚠️ **Ausencia relevante**. Sin `count()`, no hay forma de saber cuántos vectores hay indexados. Impacta en observabilidad, re-indexación y validación post-migración. |

**🔴 Hallazgo: Falta `count()`.**

```python
def count(self) -> int:
    """Número de vectores en el almacén. 0 si no disponible."""
```

Sin `count()`, operaciones como "verificar que la re-indexación completó"
o "monitorear el crecimiento del índice" requieren consultar Qdrant
directamente. Es una omisión de operación básica de observabilidad.

**Propuesta**: Añadir `count()` al Protocol. Todas las implementaciones
pueden soportarlo (Qdrant: `GET /collections/{name}`, FAISS: `index.ntotal`,
pgvector: `SELECT COUNT(*)`, SQLite: `SELECT COUNT(*)`).

### 2.2 Búsqueda: ¿el filtro es suficientemente typed?

**🔴 Hallazgo: `filter: dict[str, Any]` es un agujero negro de tipos.**

```python
def search(self, query_vector: list[float], top_k: int = 10,
           filter: dict[str, Any] | None = None) -> list[VectorResult]:
```

El filtro es un `dict` sin schema. Esto significa:

- Cada implementación interpreta el `dict` de forma distinta
- No hay verificación en tiempo de compilación de claves válidas
- Qdrant espera una estructura de filtro específica (`must`, `should`,
  `key`, `match`, `range`, etc.)
- FAISS no soporta filtros (los ignoraría silenciosamente)
- pgvector espera `WHERE` conditions

Un `dict` sin restricciones es el punto más débil del contrato.

**Soluciones posibles:**

| Opción | Descripción | Evaluación |
|--------|-------------|------------|
| A: `filter` como `dict` documentado | Documentar la estructura esperada (campo → valor exacto) | 🟡 Aceptable para v1 si se documenta |
| B: `Filter` dataclass | `Filter(field: str, operator: str, value: Any)` | ✅ Mejor, pero más complejo |
| C: Eliminar `filter` del Protocol | El orquestador post-filtra en Python | 🟢 Más simple, pero menos eficiente |

**Propuesta**: Opción A para v1 (documentar estructura), Opción B para
v2 (dataclass tipado). El `filter` actual es demasiado débil pero
funcional para el caso de uso inmediato (sin filtros en las primeras
implementaciones).

### 2.3 Firma de `upsert()`: ¿tuple cruda o dataclass?

**🔴 Hallazgo: `items: list[tuple[str, list[float], str]]` es frágil.**

```python
def upsert(self, items: list[tuple[str, list[float], str]]) -> int:
```

Ventaja: Es minimalista y evita acoplar VectorStore al modelo de dominio.
Desventaja: Una tupla de 3 elementos sin nombres es propensa a errores
de orden. El llamante debe recordar que es `(asset_id, vector, text_preview)`
y no `(vector, asset_id, text_preview)`.

**Propuesta**: Sustituir por un dataclass `VectorItem`:

```python
@dataclass
class VectorItem:
    asset_id: str
    vector: list[float]
    text_preview: str
```

```python
def upsert(self, items: list[VectorItem]) -> int: ...
```

Esto:
- Hace el contrato autodocumentado (`item.asset_id`, `item.vector`)
- Elimina errores de orden de tupla
- No acopla a `KnowledgeAsset` (sigue siendo un tipo plano)
- Es extensible (en el futuro se puede añadir `item.metadata` sin romper nada)

### 2.4 Idempotencia y casos frontera

| Operación | Comportamiento | ¿Documentado? |
|-----------|---------------|----------------|
| `delete(["nonexistent"])` | ¿Error o no-op? | ❌ No debería ser error (idempotente) |
| `upsert([])` | ¿0 o error? | ❌ No, debe retornar 0 |
| `search(query=[], top_k=10)` | ¿Error? | ❌ No, vector vacío = error |
| `search(query=vec, top_k=0)` | ¿Error o lista vacía? | ❌ No, debe retornar `[]` |

La **idempotencia** debe especificarse en el contrato:
- `delete(ids)` con IDs inexistentes → retorna 0 (no error)
- `upsert(items)` con items ya existentes → actualiza (upsert semantics)

### 2.5 Veredicto: VectorStore(Protocol)

| Criterio | Estado |
|----------|--------|
| CRUD completo | ⚠️ Falta `count()` |
| Search typed | ⚠️ `filter: dict[str, Any]` demasiado débil |
| `upsert` firma | 🔴 Tupla cruda → debe ser `VectorItem` dataclass |
| `delete` idempotente | ⚠️ No documentado |
| Degradación | ✅ `available` property |
| Portabilidad (Qdrant, FAISS, pgvector, SQLite) | ✅ Posible en todos. `filter` es la única barrera. |

---

## 3. VectorAugmentedRetriever

### Contrato actual (sección 5 de FASE6_DESIGN.md)

```python
class VectorAugmentedRetriever:
    def __init__(self, graph_retriever: GraphRetriever,
                 embedder: Embedder | None = None,
                 vector_store: VectorStore | None = None,
                 rrf_k: int = 60): ...
    def retrieve(self, query: str, top_k: int = 10,
                 use_vector: bool = False) -> list[KnowledgeAsset]: ...
```

### 3.1 ¿Actúa solo como orquestador?

**Sí.** El diseño muestra que delega en tres componentes externos:
- `GraphRetriever.retrieve_assets()` — búsqueda heurística
- `Embedder.embed()` — generación de vectores
- `VectorStore.search()` — búsqueda semántica
- RRF — algoritmo puro de ranking (sin estado, sin side effects)

No modifica datos, no cachea resultados, no transforma KnowledgeAssets.
Pura orquestación. ✅

### 3.2 Dependencia implícita de AssetStore

**🔴 Hallazgo: `_resolve_assets()` necesita AssetStore pero no está en el constructor.**

El diseño muestra `_resolve_assets()` que convierte `VectorResult` →
`KnowledgeAsset`. Esto requiere una instancia de `AssetStore`. Sin embargo,
`AssetStore` no aparece ni en el constructor ni en los parámetros de
`retrieve()`.

```python
# El diseño dice:
def _resolve_assets(self, results: list[VectorResult]) -> list[KnowledgeAsset]:
    """Resuelve VectorResults a KnowledgeAssets via AssetStore."""
    ...
```

Pero `self._asset_store` no está definido en `__init__`. O se inyecta
o se obtiene de `GraphRetriever` (lo que acoplaría ambas clases).

**Propuesta**: Añadir `asset_store: AssetStore` al constructor:

```python
def __init__(self, graph_retriever: GraphRetriever,
             asset_store: AssetStore,  # ← necesario para resolver vectores
             embedder: Embedder | None = None,
             vector_store: VectorStore | None = None,
             rrf_k: int = 60): ...
```

### 3.3 Inconsistencia de naming con GraphRetriever

**🔴 Hallazgo: `retrieve()` vs `retrieve_assets()`.**

```python
class GraphRetriever:
    def retrieve_assets(self, ...): ...

class VectorAugmentedRetriever:
    def retrieve(self, ...): ...  # ← inconsistente
```

`VectorAugmentedRetriever` es un wrapper que pretende ser un reemplazo
mejorado de `GraphRetriever`. Si el método se llama `retrieve()` en lugar
de `retrieve_assets()`, el llamante debe conocer dos APIs distintas.

**Propuesta**: Renombrar a `retrieve_assets()`:

```python
def retrieve_assets(self, query: str, top_k: int = 10,
                    use_vector: bool = False) -> list[KnowledgeAsset]: ...
```

### 3.4 `use_vector: bool = False` — ¿escala?

Un solo booleano es suficiente para v1. Pero si en el futuro hay tres modos
(solo heurístico, solo vectorial, híbrido), un booleano se queda corto.

**Propuesta**: Mantener `bool` para v1. Si se necesitan más modos, migrar
a un enum `RetrievalMode(Enum): HYBRID, HEURISTIC_ONLY, VECTOR_ONLY`.

### 3.5 Veredicto: VectorAugmentedRetriever

| Criterio | Estado |
|----------|--------|
| Solo orquestador | ✅ Sí |
| GraphRetriever desacoplado | ✅ Sí (constructor injection) |
| AssetStore explícito | 🔴 No. Falta en constructor. |
| Naming consistente | 🔴 `retrieve()` ≠ `retrieve_assets()` |
| `use_vector` escalable | ✅ Para v1 |

---

## 4. Revisión de nombres públicos

### 4.1 Tabla de nombres

| Nombre | Tipo | ¿Estable? | Observaciones |
|--------|------|-----------|---------------|
| `Embedder` | Protocol | ✅ | Claro. Sigue convención `Xxxer` (como `Extractor`) |
| `embed()` | Method | ✅ | Estándar en NLP |
| `vector_size` | Property | ✅ | Claro. Podría ser `dimension` pero `vector_size` es más obvio |
| `available` | Property | ✅ | Ya usado en extractores. Consistente. |
| `VectorStore` | Protocol | ✅ | Claro. Sigue convención `XxxStore` (como `AssetStore`) |
| `search()` | Method | ✅ | Estándar en IR |
| `upsert()` | Method | ⚠️ | Correcto pero acuñado. Alternativa: `index()`. Mantener por ser término estándar en bases de datos. |
| `delete()` | Method | ✅ | Claro |
| `VectorResult` | Dataclass | ✅ | Claro |
| `VectoAugmentedRetriever` | Class | ⚠️ | Muy largo (27 chars). Pero descriptivo. |
| `retrieve_assets()` | Method | ✅ | Consistente con `GraphRetriever.retrieve_assets()` |
| `VectorItem` | Dataclass | ✅ | Claro (propuesto para sustituir tuple) |
| `VectorResult` | Dataclass | ✅ | Claro |

### 4.2 Inconsistencias detectadas

1. **`VectoAugmentedRetriever`** usa `Augmented` (adjetivo inglés) →
   **Correcto**, no hay inconsistencia. Pero es largo.

2. **`Embedder` vs `VectorStore`** — Uno es `-er` (agente), otro es
   `Store` (contenedor). Es semánticamente correcto pero asimétrico.
   Alternativa: `EmbeddingService` vs `VectorStore`. No cambiar.

3. **`search` vs `query` vs `retrieve`** — El Protocol usa `search()`,
   el Retriever usa `retrieve_assets()`. Son sinónimos aceptables.
   `search()` es el término estándar en Qdrant/FAISS/pgvector.

### 4.3 Nombres que congelar

| Nombre | Estado | Acción |
|--------|--------|--------|
| `Embedder` | ✅ Congelar | |
| `VectorStore` | ✅ Congelar | |
| `VectorAugmentedRetriever` | ⚠️ Congelar pero largo | Aceptar como está |
| `VectorResult` | ✅ Congelar | |
| `VectorItem` | ⚠️ Propuesto | Añadir antes de implementar |
| `retrieve_assets` | 🔴 Cambiar | Renombrar de `retrieve()` a `retrieve_assets()` |

---

## 5. Veredicto Final: ¿Protocolos listos para congelar?

### Defectos bloqueantes (corregir antes de implementar)

| # | Protocolo | Defecto | Corrección |
|---|-----------|---------|------------|
| 1 | `VectorStore` | `upsert()` usa tupla cruda `tuple[str, list[float], str]` | Crear `VectorItem` dataclass |
| 2 | `VectorAugmentedRetriever` | `retrieve()` debería ser `retrieve_assets()` por consistencia | Renombrar |
| 3 | `VectorAugmentedRetriever` | `AssetStore` necesario pero no inyectado | Añadir al constructor |

### Defectos no bloqueantes (documentar y posponer)

| # | Protocolo | Defecto | Plan |
|---|-----------|---------|------|
| 4 | `VectorStore` | Falta `count()` | Añadir en v1.1 |
| 5 | `VectorStore` | `filter: dict[str, Any]` es débil | Documentar estructura en docstring. Migrar a dataclass en v2. |
| 6 | `Embedder` | Sin `max_input_tokens` | Añadir en v1.1 como property opcional |
| 7 | `Embedder` | Casos frontera no documentados | Añadir al docstring del Protocol |

### ¿Congelar o no?

**Veredicto: ✅ Congelar después de corregir los 3 defectos bloqueantes.**

Los Protocols son sólidos conceptualmente. Los tres defectos bloqueantes
son correcciones menores (renombrar, añadir parámetro, crear dataclass).
Una vez corregidos, las interfaces pueden congelarse para toda la Fase 6
y evolucionar solo con métodos nuevos (backward-compatible) en adelante.

**Contrato de estabilidad propuesto:**
- `Embedder(Protocol)` — estable v1.0 (solo additions post-freeze)
- `VectorStore(Protocol)` — estable v1.0 (solo additions post-freeze)
- `VectorAugmentedRetriever` — estable v1.0 (solo additions post-freeze)
- `VectorResult` — congelado
- `VectorItem` — congelado (nuevo)

---

*Auditoría de contratos públicos — Fase 6 v0.2.0 — 2026-07-03*
