# Auditoría independiente — FASE7_DESIGN.md v0.1.0

> **Auditor:** OpenCode (tercero independiente — revisión adversarial)
> **Documento auditado:** `docs/architecture/FASE7_DESIGN.md` — 2026-07-03
> **Estado:** 🔴 No apto para congelar — 27 hallazgos (5 bloqueantes, 6 altos, 10 medios, 6 bajos)

---

## 🔴 Bloqueantes

### B1 — `op_assets.title` no existe como columna (defecto de schema)

**Dónde:** §5.7 p1 ("Crear tabla virtual `op_assets_fts USING fts5(id UNINDEXED, title, content)`")

**Descubrimiento:** El diseño asume que `op_assets` tiene una columna `title`. No la tiene.
El título vive dentro de `op_assets.metadata` como campo JSON. La sintaxis FTS5 content=
referencia columnas de la tabla base, no expresiones SQL. `json_extract(metadata, '$.title')`
no es una columna, no se puede usar en `content=op_assets`.

**Alternativas disponibles:**
- `ALTER TABLE op_assets ADD COLUMN title TEXT` + trigger de sincronización desde metadata
- FTS5 standalone (sin content=) alimentado manualmente vía INSERT
- FTS5 external con vistas (no soportado por SQLite)

**Impacto:** La migración v13→v14 falla. Sin `op_assets.title`, el FTS5 para assets no puede
implementarse como está escrito. Se necesitan cambios de schema adicionales no documentados.

---

### B2 — `ProcessPoolExecutor` no permite cancelar tareas individuales

**Dónde:** §3.2 l11 ("ProcessPoolExecutor para whisper/OCR con SIGTERM"), §8.1 l322

**Descubrimiento:** `concurrent.futures.ProcessPoolExecutor.submit()` devuelve un `Future`.
`Future.cancel()` solo evita que la tarea arranque si no se ha despachado aún. No expone el
PID del proceso hijo. `wait(future, timeout=T)` espera pero no mata. No hay `future.terminate()`.

**Cita textual del diseño:** "RUN extractor (ProcessPoolExecutor con timeout configurable)"
y "ProcessPoolExecutor para whisper/OCR con SIGTERM". Ambas afirmaciones son falsas:
ProcessPoolExecutor no puede hacer SIGTERM a una tarea específica.

**Impacto:** Un extractor colgado (whisper en deadlock, git clone colgado en red) nunca se
recupera. El worker loop queda bloqueado. El job queda 'running' para siempre. Es EXACTAMENTE
el bug S01 que Fase 7 promete resolver, pero la solución propuesta es la misma técnica que
ya falla (ThreadPoolExecutor → ProcessPoolExecutor: ambos dejan procesos zombis).

---

### B3 — `EventBus` in-memory no cruza procesos: background queue rompe vector indexing

**Dónde:** §3.3 l127-135 (flujo background), §5.4 (queue_extract), §8.1 (Worker loop)

**Descubrimiento:** El EventBus es un singleton en memoria (`eventbus.py:_BUS`). Los
suscriptores se registran en el proceso principal vía `subscribe_all()`. Cuando el worker
se ejecuta en un proceso hijo (ProcessPoolExecutor), `get_bus()` crea una instancia NUEVA
del EventBus. La publicación de `MetadataExtracted` dentro del worker no tiene receptores.

**Secuencia exacta que falla:**

```
Proceso principal:
  subscribe_all(bus, ..., embedder, store)
    → bus.subscribe(MetadataExtracted, vector_index_handler)
      → handler captura embedder y store en closure

Proceso hijo (worker):
  ExtractionService.queue_extract() insertó op_jobs
  Worker lee op_jobs, ejecuta extractor
  AssetStore.save_asset()
  get_bus().publish(MetadataExtracted(...))
    → _BUS es nuevo → NO hay suscriptores → NADIE indexa vectores
  El asset se guarda pero nunca se vectoriza
```

**Impacto:** La funcionalidad principal de background queue (desbloquear el pipeline) rompe la
cadena de indexación vectorial establecida en Fase 6. Los assets extraídos en background
NUNCA reciben embedding. Solo la reconciliación periódica los recuperaría, con un gap temporal
no especificado.

---

### B4 — GraphRetriever "sin cambios" contradice "FTS5 en vez de LIKE"

**Dónde:** §3.1 diagrama l81 ("GraphRetriever (sin cambios)") vs l82 ("retrieve_assets() → FTS5
en vez de LIKE")

**Descubrimiento:** El diagrama dice "sin cambios" pero la descripción dice que
`retrieve_assets()` usará FTS5. El código actual de `GraphRetriever.retrieve_assets()` llama
a `store.list_assets()` y filtra en Python (`if query_lower not in title.lower()`).
Nunca llama a `store.search_assets()`. **No existe código que llame a `search_assets()`**
en ningún lugar del diseño.

**O esto o lo otro:**
- Si GraphRetriever no cambia → FTS5 en `search_assets()` es dead code, nunca se usa
- Si GraphRetriever cambia → contradice "sin cambios" y requiere modificar GraphRetriever

**Impacto:** Sin GraphRetriever usando FTS5, la optimización de búsqueda textual es inútil.
El principal consumidor de búsqueda de assets (GraphRetriever.retrieve_assets()) seguiría
usando LIKE.

---

### B5 — `op_assets_fts content=`: FTS5 external requiere columnas reales y
        backfill para datos existentes

**Dónde:** §5.7 p2 ("Crear triggers `op_assets_ai/au/ad` para mantener FTS5 sincronizada")

**Descubrimiento:** FTS5 content= external content requiere que la tabla base tenga TODAS
las columnas referenciadas como columnas reales. `op_assets` no tiene columnas `title` ni
`content` (ver B1). Los triggers AI/AU/AD funcionan sobre columnas, no sobre expresiones
JSON. No hay manera de hacer un trigger que haga `INSERT INTO op_assets_fts(rowid, title,
content) VALUES (new.rowid, json_extract(new.metadata, '$.title'), '')` porque los triggers
FTS5 no pueden hacer `content=` y al mismo tiempo ser standalone.

**Los triggers FTS5 content= esperan que el usuario haga INSERT en la tabla virtual solo
para operaciones de DELETE. Las inserciones/actualizaciones se sincronizan automáticamente
desde la tabla base cuando se consulta. Pero esto requiere que la tabla FTS se cree con
content= y que SQLite pueda leer las columnas de la tabla base.**

Si se usa FTS5 standalone (sin content=), los triggers deben copiar EXPLÍCITAMENTE los datos:
```
CREATE TRIGGER op_assets_ai AFTER INSERT ON op_assets BEGIN
  INSERT INTO op_assets_fts(rowid, title, content)
  VALUES (new.rowid, json_extract(new.metadata, '$.title'), '');
END;
```
Pero el diseño menciona content=? y no aclara qué estrategia se sigue. La opción §4 recomienda
(A) "Crear op_assets_fts como tabla virtual FTS5 apuntando a op_assets.title", que es content=
external con la tabla base. Pero esto requiere columnas title/content REALES.

**Impacto:** La migración no especifica qué dialecto FTS5 se usa (standalone vs external).
Cada uno requiere schema diferente y triggers diferentes. Implementar cualquiera de los dos
requiere cambios no documentados.

---

## 🟠 Alta

### A1 — `available` property con side-effects de red y mutación de estado

**Dónde:** §8.3 l344-349

**Descubrimiento:** El diseño propone que `available` (property) haga una llamada HTTP de
health check, modifique `self._degraded`, y modifique `self._backoff`. Esto viola PEP 8:
"properties should not have side effects or be expensive."

Además, `available` se consulta en hotspots:
- `VectorAugmentedRetriever._vector_available()` → llama a `_embedder.available`
  y `_vector_store.available`
- `VectorStore.search()` y `OllamaEmbedder.embed()` → llaman a `self.available`
- `_vector_available()` se ejecuta en CADA búsqueda con `use_vector=True`

Si el backend está degradado, cada búsqueda (100+ queries concurrentes) dispara un health
check HTTP, saturando el backend caído con peticiones de health check.

**Impacto:** Race condition en el flag _degraded (dos hilos entran en _try_recover
simultáneamente). El health check puede saturar al backend caído.

---

### A2 — FTS5 cambia el comportamiento observable de MemoryStore.search()

**Dónde:** §5.3, §10.4 CA2

**Descubrimiento:** ADR-007 exige: "observable behavior of existing functions may not change".
`MemoryStore.search()` hoy usa `LIKE '%query%'` → substring exacta. FTS5 con tokenizador
`porter` aplica stemming: `search("testing")` retorna "test", "testing", "tested".
FTS5 también ignora stopwords ("the", "a", "in"), términos de 1 carácter ("a", "I"),
y tokeniza partiendo por espacios y puntuación ("ABC-123" → busca "ABC" o "123").

CA2 afirma: "retorna los mismos assets que LIKE". Esto es falso. FTS5 retorna un conjunto
diferente (usualmente mayor, pero no siempre: "ABC-123" retorna menos con FTS5 que con LIKE).

**Impacto:** El comportamiento observable CAMBIA. CA2 es incorrecto. La auditoría propia del
diseño (C02) dice "mismo comportamiento" pero el contrato propuesto dice "más resultados".
Hay contradicción interna.

---

### A3 — Reconciliación N+1: un HTTP call por asset

**Dónde:** §3.3 l140 ("Para cada asset sin vector → Embedder.embed() → VectorStore.upsert()")

**Descubrimiento:** El diseño itera asset por asset, llamando a `embed()` y `upsert()`
individualmente. El Protocolo `Embedder.embed()` acepta `list[str]` (batch), pero el diseño
no lo usa. Para 100K assets sin vector:
- 100K llamadas HTTP a Ollama para embedding (~50ms c/u ≈ 83 min)
- 100K llamadas HTTP a Qdrant para upsert (~20ms c/u ≈ 33 min)
- Total: ~2 horas de operación secuencial

**Impacto:** La reconciliación es impracticable para datasets medianos. Obliga a mantener
ventanas de mantenimiento prolongadas.

---

### A4 — Jobs stuck en 'running' sin heartbeat ni watchdog

**Dónde:** §8.1 l313-324

**Descubrimiento:** El worker loop actualiza status='running' y luego ejecuta el extractor.
Si el proceso muere (segfault, OOM kill, SIGKILL externo), el job queda 'running' para
siempre. El dedup_key en op_jobs (`WHERE status IN ('pending', 'running')`) impide
re-encolar el mismo source mientras el zombie está 'running'.

No hay columna `started_at`. No hay heartbeat periódico. No hay timeout de running.
No hay watchdog que verifique que el worker sigue vivo.

**Impacto:** Fuente de leaks en op_jobs. Un crash del worker produce un job zombie
irrecuperable.

---

### A5 — `reconcile()` y `reindex_vectors.py` son redundantes entre sí

**Dónde:** §3.2, §5.6 vs §3.3, §12 p10 y p11

**Descubrimiento:** El diseño define dos mecanismos para lo mismo:
1. `VectorAugmentedRetriever.reconcile(dry_run=True)` → método Python que reconcilia
   AssetStore con VectorStore
2. `reindex_vectors.py [--dry-run] [--embedder]` → script CLI independiente que "lista
   todos los assets en op_assets... Embedder.embed()... VectorStore.upsert()"

Ambos hacen: listar assets, comprobar vector, crear si falta. El script es un wrapper
del método, pero el diseño no lo articula así. El plan de implementación los separa
como pasos 10 y 11, asumiendo que son independientes.

**Impacto:** Duplicación de mantenimiento. Si la lógica de reconciliación cambia, ambos
deben actualizarse. Riesgo de deriva entre script y método.

---

### A6 — FTS5 content= en op_assets_fts requiere columna real

**Dónde:** §4 l157 (FTS5: tabla separada vs columna content->fts)

**Descubrimiento adicional a B1/B5:** La decisión arquitectónica §4 compara opción A (FTS5
externa apuntando a op_assets) vs opción B (columna title extraída), y RECOMIENDA A.
Pero la opción A no es viable sin extraer title a columna (ver B1). La opción A dice
"apuntando a op_assets.title" pero op_assets NO tiene columna title. La opción B dice
"Almacenar title en columna TEXT en op_assets y crear FTS5 externa" pero la descripción
contradice la comparación (B es la que propone columna explícita, no A).

**La tabla de decisión tiene las opciones intercambiadas o mal descritas.**

---

## 🟡 Media

### M1 — search_assets() default implementation: OOM potencial

**Dónde:** §5.1, autoauditoría C01

**Descubrimiento:** El default en AssetStore(Protocol) dice "retorna list_assets() y filtra
en Python". `list_assets(sin limit)` cargaría TODOS los assets en memoria (incluyendo
metadata JSON) para filtrar en Python. Con 100K assets de 1KB metadata promedio = 100MB.

**Impacto:** OOM para implementaciones que no sobrescriban el default.

---

### M2 — `get_lineage_edges() -> list[dict[str, str]]`: tipo débil

**Dónde:** §5.2 l200

**Descubrimiento:** `dict[str, str]` no documenta las claves esperadas, no permite evolución.
Si en el futuro una arista necesita timestamp, peso, o dirección, cambiar el tipo rompe
todos los consumidores. Además, la autoauditoría dice que S01 eliminó `get_lineage_edges()`
del Protocolo, pero §5.2 lo incluye. Hay contradicción entre §13.2 S01 y §5.2.

---

### M3 — `get_queue_status() -> dict[str, Any]`: agujero de tipado

**Dónde:** §5.4 l222

**Descubrimiento:** `Any` desactiva el type checker. El formato documentado
`{"status": ..., "asset_id": ..., "error": ...}` no está garantizado por el tipo.

---

### M4 — FTS5 sanitization: subestimación de la complejidad

**Dónde:** §9 l370 ("Las queries FTS5 se sanitizan mediante parámetros posicionales")

**Descubrimiento:** FTS5 MATCH no usa SQL parameters de la misma forma que WHERE.
`MATCH ?` acepta un string que es parseado como sintaxis de query FTS5:
- `"hello world"` → frase exacta
- `hello OR world` → unión
- `hello AND world` → intersección
- `hello NEAR/5 world` → proximidad
- `hello*` → prefijo
- `"^hello"` → anchor inicio
- `NOT world` → exclusión

Escapar caracteres especiales no es trivial. La forma correcta es construir la query
término a término, escapando cada uno como frase: `'"' + term + '"'` unidos con AND.
Un simple `replace()` puede producir queries malformadas.

**Impacto:** Queries de usuarios con caracteres especiales FTS5 producen errores 500
sintácticos (DoS parcial). O peor: producen resultados inesperados silenciosamente.

---

### M5 — ProcessPoolExecutor sin shutdown: fuga de procesos

**Dónde:** §8.2 l332

**Descubrimiento:** `_WORKER_POOL: ProcessPoolExecutor | None = None` es global de módulo.
No hay `stop_worker()` ni `__del__` en ExtractionService. Si `start_worker()` se llama
múltiples veces, se crean pools duplicados (hijos huérfanos). Si el proceso principal
termina, los hijos quedan como zombies.

---

### M6 — Backfill síncrono en migración bloquea BD

**Dónde:** §5.7 p7-9

**Descubrimiento:** El backfill INSERT-SELECT desde op_lineage a op_lineage_edges y desde
op_assets/op_memory a sus tablas FTS se ejecuta dentro del BEGIN...COMMIT de la migración.
Con datasets medianos (100K filas de op_lineage), el bloqueo puede durar minutos.
El pipeline no puede operar durante la migración.

---

### M7 — Sin backpressure en cola de extracción

**Dónde:** §5.4, §8.1

**Descubrimiento:** `queue_extract()` retorna inmediatamente sin verificar el tamaño de
cola. 100K extractions encoladas llenan op_jobs sin control. El worker procesa de 1 en 1.

---

### M8 — Sin límite de RAM por worker

**Dónde:** §6 (riesgos), §8.2

**Descubrimiento:** Whisper `large-v3` consume ~4GB. Dos workers simultáneos = ~8GB.
En GX10 (128GB RAM unificada, 42GB ocupados por llama3.3:70b en GPU), quedan ~86GB pero
RAM no es infinita. Si se añaden más workers en el futuro, no hay control. El diseño
menciona `token_screen.py` como mitigación pero no especifica cómo se integra.

---

### M9 — `op_lineage_edges` sin índice compuesto

**Dónde:** §5.7 p4

**Descubrimiento:** Índices separados en `(src)` y `(dst)`. Para verificar si una arista
específica existe (`WHERE src=? AND dst=?`), SQLite puede usar un índice pero escanea
dentro del subconjunto. Con 10M filas, un índice compuesto `(src, dst)` es más eficiente.

---

### M10 — Autorecuperación asimétrica: Embedder vs VectorStore

**Dónde:** §8.3

**Descubrimiento:** El diseño propone autorecuperación en ambos backends, pero
`VectorAugmentedRetriever._vector_available()` requiere AMBOS disponibles:

```python
def _vector_available(self) -> bool:
    return (
        self._embedder is not None
        and self._embedder.available
        and self._vector_store is not None
        and self._vector_store.available
    )
```

Si solo uno se recupera (ej: Qdrant vuelve pero Ollama sigue caído), `_vector_available()`
sigue siendo False. No hay modo "degradado parcial" donde el sistema use vectores cacheados
sin poder crear nuevos. Tampoco hay modo "solo upsert" (indexar nuevos vectores aunque no
se pueda buscar).

---

## 🟢 Baja

### L1 — `CONTRACTS_FROZEN.md` no especifica qué contratos se actualizan

**Dónde:** §15 l571

Solo dice "v2.0" sin detallar: `AssetStore.search_assets()`, `VectorStore.degraded`,
`VectorAugmentedRetriever.reconcile()`.

---

### L2 — Worker polling sin backoff en idle

**Dónde:** §8.1 l324

"SLEEP 0.1s" fijo. 10 SELECTs/s en idle. Con N workers, N×10 SELECTs/s.

---

### L3 — `_WORKER_POOL` duplicable entre instancias

**Dónde:** §8.2

Variable global de módulo. Si dos ExtractionService instancian workers, puede haber
pools duplicados.

---

### L4 — Jobs 'failed' sin TTL ni política de limpieza

Acumulación de `op_jobs` con status='failed' sin límite. No hay cleanup.

---

### L5 — Tests faltantes: 8 casos límite/negativos

**Faltan en §10.1-10.2:**
- FTS5 no disponible en SQLite → fallback a LIKE
- Worker muere mientras status='running'
- Reconciliación concurrente con extracción activa
- Query FTS5 con caracteres especiales
- Query de 1 carácter (FTS5 lo ignora)
- FTS5 corrupto → fallback
- `op_assets_fts` sin backfill tras migración
- `store_lineage_event` escribe op_lineage OK pero op_lineage_edges falla

---

### L6 — FTS5 tokenizer no especificado

§5.7 no especifica tokenizer para `op_assets_fts` o `op_memory_fts`. El schema existente
de `kg_nodes_fts` usa `porter unicode61` (stemming inglés). Para un proyecto multilingüe
con queries en español, `porter` es inapropiado. `unicode61` sin stemming retendría más
términos pero sin normalización. `ascii` aún peor (pierde acentos).

---

## 10. Lo que nadie ha pedido revisar — supuestos ocultos

### S1 — "FTS5 es siempre mejor que LIKE"

**Falso para:** IDs técnicos ("ABC-123"), códigos, UUIDs, versiones semánticas ("v1.2.3"),
nombres con guiones ("pre-existing"). FTS5 tokeniza partiendo por separadores: "ABC-123"
se convierte en `MATCH "ABC" AND "123"`, perdiendo el guión y la relación entre tokens.
LIKE `%ABC-123%` lo encuentra exactamente.

**Impacto:** Assets cuyo título es un código interno (ej: "INCIDENT-2026-007") no se
encuentran con FTS5 si la búsqueda incluye el guión.

---

### S2 — "El lock-in con SQLite FTS5 es aceptable"

Toda la optimización de búsqueda (FTS5, triggers, índices JSON) es sintaxis específica
de SQLite. Si en el futuro se migra a PostgreSQL, no hay FTS5 nativo, no hay content=
external triggers. Habría que reescribir toda la capa de búsqueda.

---

### S3 — "El EventBus funciona en todos los contextos"

**Falso.** Se descubrió en B3 que el EventBus in-memory no cruza procesos. Pero hay un
supuesto más profundo: el diseño asume que EventBus es el backbone de comunicación para
Capa 11. No hay plan para hacerlo cross-process ni documentación de sus límites.

---

### S4 — "La reconciliación y el subscriber no interfieren"

No hay coordinación entre `_make_vector_index_subscriber` (disparado por MetadataExtracted
en proceso principal) y `reconcile()` (ejecutado manualmente). Ambos pueden intentar
indexar el mismo asset simultáneamente. Upsert es idempotente en Qdrant, pero no se
garantiza atomicidad en la lectura: el subscriber lee el asset justo cuando reconciliation
lo está procesando.

---

### S5 — "Solo hay dos estados: asset con vector o sin vector"

El diseño asume una reconciliación binaria. Pero un asset puede tener un vector generado
con un embedder anterior (modelo cambiado). La reconciliación no detecta vectores con
embedder obsoleto. Necesitaría comparar hashes de embedder o versiones de modelo.

---

### S6 — "No hay necesidad de versionar colecciones vectoriales"

Si se cambia el modelo de embeddings (ej: nomic-embed-text → mxbai-embed-large), la
dimensión o semántica de los vectores cambia. La reconciliación reindexa assets sin
vector, pero los vectores existentes (con modelo antiguo) conviven con los nuevos en
la misma colección Qdrant. No hay versionado de colecciones.

---

### S7 — "op_lineage_edges backfill con JSON arrays es trivial"

El backfill requiere: `json_each(input_ids)` CROSS JOIN `json_each(output_ids)` para
cada fila de op_lineage, generando N×M aristas por evento. Con input_ids=["A","B","C"]
y output_ids=["X","Y"], se generan 6 aristas: A→X, A→Y, B→X, B→Y, C→X, C→Y.
¿Es esto correcto para el modelo OpenLineage? ¿O input_ids y output_ids son independientes
y cada arista debe ser A→X (1:1)? El diseño no aclara la semántica.

---

## Resumen

| Gravedad | Cantidad | IDs |
|---|---|---|
| 🔴 Bloqueante | 5 | B1, B2, B3, B4, B5 |
| 🟠 Alta | 6 | A1, A2, A3, A4, A5, A6 |
| 🟡 Media | 10 | M1-M10 |
| 🟢 Baja | 6 | L1-L6 |
| Supuestos ocultos | 7 | S1-S7 |
| **Total** | **34** | |

## Veredicto

**No apto para congelar contratos. No apto para implementar.**

Existen 5 defectos bloqueantes que invalidan partes centrales del diseño:

1. **B1** (`op_assets.title` no existe) — invalida la migración FTS5 completa para assets.
2. **B2** (ProcessPoolExecutor sin cancelación) — la solución para S01 no funciona.
3. **B3** (EventBus in-process → background queue rompe vector indexing) — la
   funcionalidad estrella de Fase 7 (background queue) rompe la cadena de Fase 6
   (vector indexing post-extracción).
4. **B4** (GraphRetriever "sin cambios" contradice FTS5) — el FTS5 sería dead code.
5. **B5** (FTS5 content= mal especificado) — el dialecto FTS5 no está decidido, y
   cualquiera de las opciones requiere cambios de schema no documentados.

Se requiere corregir los 11 hallazgos 🔴 y 🟠 y reevaluar antes de proceder.

---

*Auditoría independiente — 2026-07-03 — Revisión adversarial del diseño de Fase 7*
