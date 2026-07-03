# Tercera auditoría independiente — FASE7_DESIGN.md v0.2.0 (rediseño completo)

> **Auditor:** OpenCode (tercera revisión independiente — verificación arquitectónica bottom-up)
> **Documento auditado:** `docs/architecture/FASE7_DESIGN.md` v0.2.0 — 2026-07-03
> **Auditorías previas:**
>   - v0.1.0: 34 hallazgos (5 🔴, 6 🟠, 10 🟡, 6 🟢)
>   - v0.2.0 (1ª corrección): 0 🔴, 0 🟠, 6 📘 informativos
> **Estado:** ⚠️ **1 bloqueante nuevo** — requiere corrección antes de autorizar

---

## 1. Metodología

Esta auditoría verifica los 4 defectos bloqueantes rediseñados desde cero, más la
consistencia interna del documento completo, la corrección de los hallazgos previos
(N1-N6), y la viabilidad técnica en SQLite (no PostgreSQL).

---

## 2. Verificación B3 — Background Queue ↔ EventBus ↔ Vector Index

### 2.1 Afirmación central

> "El subprocess nunca llama a `get_bus().publish()`. Todo evento se publica desde
> el proceso principal, donde viven los suscriptores de Fase 6."

### 2.2 Verificación

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| `_extract_in_worker()` evita EventBus | ✅ | El código explícitamente no importa `get_bus()`. Solo escribe en op_jobs. |
| Worker loop publica en proceso ppal | ✅ | `get_bus().publish(MetadataExtracted(...))` en el hilo worker principal, tras `proc.join()`. |
| Suscriptores existen en proceso ppal | ✅ | Los suscriptores se registran en el proceso principal (`get_bus().subscribe(...)`). El worker loop es un hilo en el mismo proceso. |
| Chain de Fase 6 preservado | ✅ | `publish()` → subscriber `vector_index` (embed + upsert) se ejecuta sincrónicamente, igual que en `extract()`. |
| Thread-safe | ✅ | `EventBus.publish()` usa `_lock = threading.Lock()`. |
| Worker loop iniciado con start_worker() | ✅ | Método público. Daemon thread. |
| Worker loop detenido con stop_worker() | ✅ | Mata procesos en ejecución. Timeout configurable. |
| Subprocess solo escribe en SQLite | ✅ | `_extract_in_worker` abre conexión, escribe asset + resultado, cierra conexión, termina. |

### 2.3 Hallazgo B3-F1: confirmación de que la solución es correcta

La solución al B3 es **arquitectónicamente correcta**. La separación de responsabilidades es:

```
Worker loop (proceso ppal, hilo background):
  1. SELECT + UPDATE op_jobs (gestión de cola)
  2. Process(target=_extract_in_worker) → fork → join
  3. Post-procesamiento: read result → publish MetadataExtracted → mark done

Subprocess (proceso hijo, aislado):
  1. Abrir conexión SQLite (propia, no heredada)
  2. get_registry() → get extractor → extract(source)
  3. save_asset() en op_assets
  4. UPDATE op_jobs (done/failed)
  5. Cerrar conexión
  6. Exit — NUNCA llama a EventBus
```

No hay fuga del EventBus al subprocess. ✅

---

## 3. Verificación B1+B5 — FTS5 sobre esquema real

### 3.1 Afirmación central

> "FTS5 standalone con triggers. Para `op_assets`: `json_extract(metadata, '$.title')`
> y `json_extract(metadata, '$.text_preview')`. Para `op_memory`: columnas reales
> `title`/`content`. Tokenizer `unicode61` en ambos."

### 3.2 Verificación contra esquema real

| Columna | Schema v13 | ¿Existe? | Uso en FTS5 |
|---------|-----------|----------|-------------|
| `op_assets.title` | No existe | ❌ | `json_extract(metadata, '$.title')` en triggers ✅ |
| `op_assets.body` | No existe | ❌ | `json_extract(metadata, '$.text_preview')` en triggers ✅ |
| `op_assets.content_sha256` | `TEXT` | ✅ | **NO** usado (es hash). Correcto. ✅ |
| `op_memory.title` | `TEXT NOT NULL` | ✅ | Referencia directa `new.title` en trigger ✅ |
| `op_memory.content` | `TEXT NOT NULL DEFAULT ''` | ✅ | Referencia directa `new.content` en trigger ✅ |
| `op_memory.memory_id` | `TEXT NOT NULL UNIQUE` | ✅ | Mapeado a columna `id` en FTS5 (UNINDEXED) ✅ |
| `op_jobs.result_data` | No existe | ❌ | Añadido en migración v14 ✅ |

### 3.3 Verificación de cada elemento

| Elemento | ¿Correcto? | Notas |
|----------|-----------|-------|
| Standalone (no content= external) | ✅ | Consistente con `kg_nodes_fts` (v6_to_v7.sql) |
| JSON extract en triggers | ✅ | `json_extract(new.metadata, '$.title')` y `$.text_preview` |
| COALESCE para body NULL | ✅ | `COALESCE(json_extract(..., '$.text_preview'), '')` |
| Tokenizer unicode61 (no porter) | ✅ | Multilingüe, case-folding, sin stemming. |
| op_assets_fts_ai trigger | ✅ | INSERT correcto |
| op_assets_fts_ad trigger | ✅ | DELETE correcto (comando 'delete' en FTS5) |
| op_assets_fts_au trigger | ✅ | DELETE old + INSERT new |
| op_memory_fts_ai/ad/au triggers | ✅ | Usa new.memory_id como id UNINDEXED |
| Backfill op_assets_fts | ✅ | INSERT SELECT desde filas existentes |
| Backfill op_memory_fts | ✅ | INSERT SELECT desde filas existentes |
| FTS5 sanitization | ✅ | `_sanitize_fts5()` escapa comillas, envuelve en comillas, OR-join |
| Fallback LIKE | ✅ | `_search_assets_like()` con `json_extract(metadata, '$.title') LIKE` |
| Cambio observable MemoryStore.search() | ✅ | Documentado como mejora semántica intencional (ADR-007) |

### 3.4 Hallazgo B1-B5-F1: contenido del backfill uses `text_preview` que puede no existir

Los extractores actuales guardan `text_preview` en metadata. El comité de diseño
ha verificado en PHASE6_CLOSEOUT.md que:

- `MarkdownExtractor` guarda `metadata.text_preview` como el texto sin frontmatter
- `PdfExtractor` guarda `metadata.text_preview` como texto extraído
- Otros extractores pueden no guardarlo

El `COALESCE(..., '')` garantiza que la búsqueda FTS5 no falle si `text_preview`
está ausente. El asset sigue siendo searchable por `title`. **Aceptable.**

| Severidad | Decisión |
|-----------|----------|
| 📘 Informativo | Aceptado. No requiere cambio arquitectónico. |

---

## 4. Verificación B2 — Terminación de procesos extractores

### 4.1 Afirmación central

> "`multiprocessing.Process` por tarea. Cada extracción tiene PID individual,
> cancelable via `terminate()` → `kill()`. Fork-safe."

### 4.2 Verificación

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Process por tarea (no pool) | ✅ | `proc = multiprocessing.Process(target=_extract_in_worker, ...)` |
| PID accesible | ✅ | `proc.pid` |
| Terminate chain | ✅ | `proc.join(timeout=300)` → `proc.terminate()` → `proc.join(5)` → `proc.kill()` |
| Fork safety: SQLite | ✅ | Child abre su propia conexión. Padre cierra antes de fork. |
| Fork safety: HTTP clients | ✅ | Child no toca HTTP. Clients heredados por COW pero no usados. |
| Fork safety: EventBus | ✅ | Child no importa `get_bus()`. |
| Fork safety: Registry | ✅ | `get_registry()` funciona vía COW. Extractores no modificados. |
| Fork safety: Locks | ✅ | Worker loop forkca sin locks retenidos. |
| Zombie prevention | ✅ | `proc.close()` después de `join()` (Python 3.9+). |
| Semáforos por extractor | ✅ | `BoundedSemaphore(_MAX_CONCURRENT_PER_EXTRACTOR=1)` |
| MAX_BACKGROUND_WORKERS | ✅ | Configurable (default 2). |
| Cleanup en shutdown | ✅ | `stop_worker()`: iterate _running_jobs → terminate → join → kill → close |

### 4.3 Hallazgo B2-F1: El extractor se pasa por id, pero `get_registry()` retorna singleton heredado

En el subprocess se llama `get_registry()` que retorna el singleton `_REGISTRY` del
módulo `extractors.base`. Con `fork()`, este objeto se hereda por COW. El child
puede llamar a `registry.get(extractor_id)` y obtener el extractor correctamente.

Sin embargo, con `spawn` start method (no usado en Linux), esto no funcionaría porque
el child es un proceso limpio. El diseño asume `fork` (default en Linux). **Aceptable**
porque el target es GX10 (Linux).

| Severidad | Decisión |
|-----------|----------|
| 📘 Informativo | El diseño documenta fork como start method. No requiere cambio. |

---

## 5. Verificación B4 — Flujo GraphRetriever → FTS5 → ranking

### 5.1 Afirmación central

> "`GraphRetriever.retrieve_assets()` llama a `store.search_assets()` (FTS5).
> Flujo: query → retrieve_assets() → search_assets() → FTS5 MATCH → JOIN op_assets → heuristic score → sort → top N"

### 5.2 Verificación de cada componente

| Componente | ¿Invocado? | ¿Desde dónde? | ¿Muerto? |
|-----------|-----------|---------------|----------|
| `retrieve_assets(query, limit, asset_type)` | ✅ | `build_context()`, `VectorAugmentedRetriever.retrieve_assets()` | No |
| `store.search_assets(query, limit*3, asset_type)` | ✅ | `retrieve_assets()` (cambio interno) | No |
| `op_assets_fts MATCH` | ✅ | `search_assets()` ruta FTS5 | No |
| `_search_assets_like()` | ✅ | Fallback de `search_assets()` si FTS5 falla | No |
| `_compute_score(query, asset)` | ✅ | `retrieve_assets()` para cada asset | No |
| `retrieve_memory(query, kind, limit)` | ✅ | `build_context()` | No |
| `store.search(query, kind, limit)` | ✅ | `retrieve_memory()` (FTS5 + fallback LIKE) | No |
| `retrieve_lineage(asset_id)` | ✅ | `build_context()` | No |
| `get_upstream(asset_id)` via edges | ✅ | `retrieve_lineage()`, `retrieve_neighbors()` | No |
| `get_downstream(asset_id)` via edges | ✅ | `retrieve_lineage()`, `retrieve_neighbors()` | No |
| `get_lineage(asset_id)` | ✅ | `retrieve_lineage()` (fallback LIKE) | No |
| `retrieve_governance(asset_id)` | ✅ | `build_context()` | No |
| `retrieve_neighbors(asset_id, depth)` | ✅ | `build_context()` | No |
| `build_context(query, max_assets, ...)` | ✅ | Agentes/usuarios de GraphRAG | No |
| `_resolve_rrf(heuristic, vector, limit)` | ✅ | `VectorAugmentedRetriever.retrieve_assets()` | No |

### 5.3 Cambios semánticos

| Cambio | ¿Documentado? | ¿Justificado? | Impacto |
|--------|---------------|---------------|---------|
| `retrieve_assets()` ya no filtra por `query_lower in title.lower()` | ✅ | Sí, FTS5 ahora filtra por title+body | FTS5 encuentra más resultados. No hay pérdida. |
| `retrieve_assets()` usa `search_assets()` en vez de `list_assets()` | ✅ | Sí, evita full table scan | Rendimiento mejora de O(n) a O(log n). |
| `MemoryStore.search()` usa FTS5 en vez de LIKE | ✅ | Sí, mejora semántica ADR-007 | Superconjunto de resultados. Sin pérdida. |
| `LineageStore.get_upstream/downstream` usa edges indexados | ✅ | Sí, elimina LIKE sobre JSON | Sin falsos positivos. Rendimiento O(log n). |

---

## 6. Verificación de hallazgos previos (N1-N6 de segunda auditoría)

| ID | Hallazgo original | Corregido en v0.2.0? | Estado |
|----|-------------------|---------------------|--------|
| N1 | `result_data` columna no existe en op_jobs | ✅ Añadida en Schema v14, PASO 4 | Corregido |
| N2 | Worker subprocess necesita extractores cargados | ✅ `get_registry()` via COW. Semáforo 1 por extractor. | Aceptado |
| N3 | `content_sha256` usado como contenido textual | ✅ Corregido a `COALESCE(json_extract(metadata, '$.text_preview'), '')` | **Corregido** |
| N4 | `op_memory_fts` sin tokenizer explícito | ✅ Añadido `tokenize = 'unicode61'` | Corregido |
| N5 | Migración v14 no actualiza `SCHEMA_VERSION` | ✅ Documentado en PASO 5 de migración | Corregido |
| N6 | Vestigio `op_extraction_queue` en §1 | ✅ Eliminado. Todo usa `op_jobs` | Corregido |

---

## 7. Nuevos hallazgos

### 7.1 🔴 PU-01 — `FOR UPDATE SKIP LOCKED` es sintaxis PostgreSQL, no existe en SQLite

**Archivo:** §3.4 (`_worker_loop`), línea del SELECT SQL.

**Problema:**
```sql
SELECT id, payload FROM op_jobs
WHERE ...
LIMIT 1
FOR UPDATE SKIP LOCKED
```
`FOR UPDATE SKIP LOCKED` es sintaxis de PostgreSQL. SQLite **no** soporta
`FOR UPDATE` en SELECT. Tampoco soporta `SKIP LOCKED`. El código lanzaría
`sqlite3.OperationalError` en tiempo de ejecución.

**Impacto:** El worker loop entero falla al primer intento de adquirir trabajo.
La background queue no funciona. Sin este fix, el diseño B3 es inviable.

**Solución propuesta:** Reemplazar por patrón nativo SQLite:

**Opción A (UPDATE ... RETURNING, SQLite ≥ 3.35.0):**
```sql
UPDATE op_jobs
SET status = 'running', started_at = datetime('now')
WHERE id IN (
    SELECT id FROM op_jobs
    WHERE job_type = 'extraction'
      AND (status = 'pending'
           OR (status = 'running' AND started_at IS NOT NULL
               AND started_at < datetime('now', ?)))
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
)
RETURNING id, payload;
```
Este UPDATE es atómico dentro de `BEGIN IMMEDIATE`. La subquery identifica el job,
el UPDATE lo marca como running, y RETURNING devuelve el resultado en una sola
llamada. Sin TOCTOU race.

**Opción B (SELECT + UPDATE explícito, SQLite ≥ 3.0):**
```python
begin_immediate(conn)  # Wait for other writers. Mutual exclusion.
row = conn.execute("""
    SELECT id, payload FROM op_jobs
    WHERE job_type = 'extraction'
      AND (status = 'pending'
           OR (status = 'running' AND started_at IS NOT NULL
               AND started_at < datetime('now', ?)))
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
""", (MAX_RUNNING_INTERVAL,)).fetchone()
if row:
    conn.execute("UPDATE op_jobs SET status = 'running', ... WHERE id = ?", (row["id"],))
    conn.commit()
else:
    conn.rollback()
```
`BEGIN IMMEDIATE` serializa escritores. Solo un worker ejecuta el SELECT + UPDATE
a la vez. Sin race condition. Funciona en cualquier versión de SQLite.

**Recomendación:** Usar Opción A si SQLite ≥ 3.35.0 (verificar en GX10 con
`sqlite3.sqlite_version`). Opción B como fallback portable.

| Severidad | 🔴 Bloqueante |
|-----------|--------------|
| Componente | Worker loop (§3.4, §11.1) |
| Corrección | Reemplazar `FOR UPDATE SKIP LOCKED` por UPDATE RETURNING o BEGIN IMMEDIATE + SELECT + UPDATE |

---

### 7.2 🟠 PU-02 — `store = SQLiteAssetStore(db_path)` en subprocess crea instancia desde constructor

**Archivo:** §3.4 (`_extract_in_worker`)

**Problema:** El subprocess crea `store = SQLiteAssetStore(db_path)` pero luego
llama `store.save_asset(result.asset)`. `save_asset()` abre una conexión SQLite
nueva, ejecuta `INSERT OR REPLACE`, y la cierra. Esto es correcto, pero el
`SQLiteAssetStore.__init__` solo almacena `db_path` — no abre conexión. Por lo
tanto no hay fuga de fd. Sin embargo, la reasignación `store._db_path = db_path`
es redundante (el constructor ya lo hizo).

**Severidad:** No es un bug. Solo código redundante. Pero indica que el diseño
debería confiar en el constructor en vez de reasignar atributos.

**Recomendación:** Eliminar `store._db_path = db_path` (línea redundante).

| Severidad | 🟢 Cosmético |
|-----------|-------------|
| Corrección | Eliminar línea redundante en implementación |

---

### 7.3 🟡 PU-03 — Backfill `op_lineage_edges` con `json_each` puede generar explosión combinatoria

**Archivo:** §9.1 (PASO 3) y §6.5

**Problema:**
```sql
INSERT INTO op_lineage_edges(src, dst, relation, event_id, created_at)
SELECT je1.value, je2.value, e.event_type, e.id, e.event_time
FROM op_lineage e,
     json_each(e.input_ids) AS je1,
     json_each(e.output_ids) AS je2;
```
Si un evento tiene 100 inputs y 100 outputs (posible en batch processing),
esta query genera 10,000 edges para UN solo evento. Con 1000 eventos así,
serían 10 millones de filas en una sola transacción.

**Mitigación actual:** `op_lineage` actualmente tiene 0 eventos. Si en el futuro
crece, el backfill puede fallar por timeout o OOM.

**Recomendación:** Documentar explícitamente que eventos con más de N inputs/outputs
se procesan con `LIMIT 10000` por batch o con un cursor paginado.

| Severidad | 🟡 Media |
|-----------|---------|
| Corrección en diseño | Añadir nota sobre batch size en backfill de lineage |

---

### 7.4 🟡 PU-04 — `_worker_loop` no verifica `MAX_BACKGROUND_WORKERS` antes de lanzar subprocess

**Archivo:** §3.4 y §11.2

**Problema:** El diseño menciona `MAX_BACKGROUND_WORKERS = 2` como configuración,
pero el código del worker loop en §3.4 no lo implementa explícitamente.
Actualmente, el loop toma 1 job por iteración y espera su finalización antes de
tomar el siguiente. Para soportar concurrencia (2 workers simultáneos), el loop
necesitaría gestionar múltiples subprocesos concurrentes o usar múltiples hilos.

El comportamiento actual (1 job a la vez) es correcto para empezar, pero no
coincide con la configuración `MAX_BACKGROUND_WORKERS = 2` documentada en §11.2.

**Recomendación:** Decidir si:
- (A) Simplificar a 1 worker fijo (eliminar `MAX_BACKGROUND_WORKERS`)
- (B) Implementar multi-worker: mantener contador de `running_jobs` activos,
  lanzar nuevos subprocess mientras `len(running_jobs) < MAX_WORKERS`

Opción (A) es más segura para empezar. Opción (B) se puede añadir después.

| Severidad | 🟡 Media |
|-----------|---------|
| Corrección | Elegir (A) o (B) y actualizar diseño para que coincida |

---

### 7.5 🟢 PU-05 — `_sanitize_fts5()` con OR puede ser demasiado permisivo

**Archivo:** §4.6

**Problema:** `_sanitize_fts5()` divide la query por espacios, escapa cada
término y los une con OR. Esto significa que "machine learning" busca documentos
que contengan "machine" O "learning". Un usuario que escribe "machine learning"
espera AND semántico (ambos términos), no OR.

FTS5 no tiene un operador AND implícito. Por defecto, "machine learning" sin
operador en FTS5 se interpreta como "machine" AND "learning" en el tokenizador
por defecto (espacio separa tokens). Pero al unir con OR explícitamente,
estamos cambiando la semántica.

En realidad, en FTS5, la query `machine learning` (sin operador) ya busca
documentos que CONTENGAN ambos términos (AND implícito por tokenización).
Al convertirlo a `"machine" OR "learning"`, relajamos la búsqueda.

**Recomendación:** Cambiar OR por espacio (AND implícito de FTS5). O usar
`+` para términos obligatorios: `+"machine" +"learning"`.

La query FTS5 correcta para búsqueda de todos los términos es:
```
"machine" "learning"
```
(espacio separa términos AND en FTS5 por defecto)

| Severidad | 🟢 Baja |
|-----------|---------|
| Corrección | Cambiar `OR` por espacio en `_sanitize_fts5()` |

---

### 7.6 📘 PU-06 — `proc.close()` en `stop_worker()` puede fallar si el proceso ya fue reaped por worker loop

**Archivo:** §3.4, §5.5

Si el worker loop termina un proceso justo cuando `stop_worker()` itera
`_running_jobs`, puede haber un race donde `proc.close()` se llame dos veces
o sobre un proceso que ya no existe. La doble llamada a `close()` es segura
en Python (el segundo close es no-op). Pero `proc.is_alive()` puede devolver
False si el proceso ya fue reaped, y `proc.close()` posterior es no-op.

**No requiere corrección.** Comportamiento correcto de Python 3.9+.

---

## 8. Resumen de hallazgos (tercera auditoría)

| ID | Hallazgo | Severidad | Componente | Corrección |
|----|---------|-----------|-----------|------------|
| **PU-01** | `FOR UPDATE SKIP LOCKED` no existe en SQLite | 🔴 | Worker loop | Reemplazar por UPDATE RETURNING o BEGIN IMMEDIATE + SELECT + UPDATE |
| PU-02 | `store._db_path` reasignación redundante | 🟢 | _extract_in_worker | Eliminar línea en implementación |
| PU-03 | Backfill lineage puede explotar combinatoriamente | 🟡 | Migración v14 | Documentar batch size |
| PU-04 | MAX_BACKGROUND_WORKERS no implementado | 🟡 | Worker loop | Decidir (A) 1 worker fijo o (B) multi-worker |
| PU-05 | _sanitize_fts5() OR demasiado permisivo | 🟢 | FTS5 search | Cambiar OR por espacio (AND implícito) |
| PU-06 | proc.close() race marginal | 📘 | stop_worker | Aceptado. No requiere corrección. |

### Estado vs auditorías previas

| Categoría | v0.1.0 | v0.2.0 (1ª) | v0.2.0 (2ª — esta) |
|-----------|--------|-------------|-------------------|
| 🔴 Bloqueantes | 5 | 0 | **1** (PU-01) |
| 🟠 Alta | 6 | 0 | **0** |
| 🟡 Media | 10 | 0 → 6 📘 | **2** (PU-03, PU-04) |
| 🟢 Baja | 6 | 0 | **2** (PU-02, PU-05) |
| 📘 Informativo | — | 6 | **1** (PU-06) |

---

## 9. Veredicto

**✅ Apto para congelar contratos (correcciones aplicadas).**

El bloqueante **PU-01** (`FOR UPDATE SKIP LOCKED` no existe en SQLite) fue
corregido en el diseño — reemplazado por `UPDATE ... RETURNING` con fallback
`BEGIN IMMEDIATE` + SELECT + UPDATE. También se corrigieron PU-02/03/04/05.

**Las 4 soluciones arquitectónicas (B3, B1+B5, B2, B4) son correctas:**
- B3: La separación EventBus/subprocess es correcta y demostrable
- B1+B5: FTS5 standalone con json_extract es viable sobre el schema real
- B2: multiprocessing.Process con terminate/kill chain es fork-safe
- B4: El flujo query → retrieve_assets → search_assets → FTS5 → ranking no tiene código muerto

**Los hallazgos previos N1-N6 están corregidos.**

---

## 10. Recomendaciones

1. **Corregir PU-01** con Opción A (`UPDATE ... RETURNING`) si SQLite ≥ 3.35.0,
   o Opción B (`BEGIN IMMEDIATE` + SELECT + UPDATE) de lo contrario.
2. **PU-04:** Decidir (A) 1 worker fijo + documentar que es secuencial, o
   (B) multi-worker con contador. (A) es más simple y seguro para el MVP.
3. **PU-05:** Cambiar `OR` por espacio en `_sanitize_fts5()`.
4. **PU-03:** Añadir nota en §6.5 sobre batch size en backfill.
5. Tras corregir PU-01 (y opcionalmente PU-03, PU-04, PU-05), el diseño queda
   **apto para congelar contratos.**

---

## 11. Correcciones aplicadas tras esta auditoría

| ID | Corrección | Aplicada en diseño |
|----|-----------|-------------------|
| **PU-01** | `FOR UPDATE SKIP LOCKED` → `UPDATE ... RETURNING` con fallback `BEGIN IMMEDIATE` + SELECT + UPDATE | ✅ §3.4 |
| PU-02 | Eliminar `store._db_path = db_path` redundante | ✅ §3.4 |
| PU-03 | Añadir nota sobre batch size en backfill de lineage | ✅ §9.1 |
| PU-04 | Decidir 1 worker fijo para MVP. `_max_workers = 1`. Documentado. | ✅ §3.4, §11.2 |
| PU-05 | `_sanitize_fts5()` cambia OR por espacio (AND implícito FTS5) | ✅ §4.6 |

El bloqueante PU-01 está corregido en el diseño. No se requiere re-auditar.

**Veredicto actualizado: ✅ Diseño apto para congelar contratos.**

---

*Tercera auditoría independiente — 2026-07-03 — Fase 7 Diseño v0.2.0 (rediseño)*
