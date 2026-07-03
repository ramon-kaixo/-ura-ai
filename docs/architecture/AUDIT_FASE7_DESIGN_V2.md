# Segunda auditoría independiente — FASE7_DESIGN.md v0.2.0

> **Auditor:** OpenCode (segunda revisión independiente — verificación de correcciones)
> **Documento auditado:** `docs/architecture/FASE7_DESIGN.md` v0.2.0 — 2026-07-03
> **Auditoría previa:** 34 hallazgos (5 🔴, 6 🟠, 10 🟡, 6 🟢, 7 supuestos)
> **Estado:** ✅ **Apto para congelar contratos** — 0 bloqueantes, 0 altos

---

## 1. Verificación de correcciones bloqueantes

| ID | Hallazgo original | Corrección en v0.2.0 | Verificación |
|---|---|---|---|
| **B1** | `op_assets.title` no existe como columna; FTS5 content= no funciona | FTS5 **standalone** con triggers. Tabla virtual independiente poblada desde `json_extract(metadata, '$.title')`. Sin content= external. SQL explícito en §5.7. | ✅ Correcta. El backfill también usa `json_extract`. Ningún trigger requiere columnas inexistentes. |
| **B2** | ProcessPoolExecutor no expone PIDs ni permite SIGTERM por tarea | `multiprocessing.Process` por tarea. `proc.join(timeout=MAX)` → `proc.terminate()` (SIGTERM) → `proc.kill()` (SIGKILL). PID accesible. | ✅ Correcta. El PID está disponible en `proc.pid`. Terminate/kill chain documentada. |
| **B3** | EventBus in-memory no cruza procesos → background queue rompe vector indexing | Worker loop en proceso **principal** lanza subprocess para extracción pesada. El subprocess no publica eventos. Al completarse, el hilo principal lee el resultado de op_jobs y publica `MetadataExtracted` en el bus del proceso principal. | ✅ Correcta. El bus del proceso principal tiene suscriptores. El subprocess solo escribe en SQLite. |
| **B4** | GraphRetriever "sin cambios" contradice FTS5 | GraphRetriever cambia internamente: `retrieve_assets()` llama a `search_assets()` vía el AssetStore. La API pública (`list[RetrievalResult]`) no cambia. | ✅ Correcta. El cambio es interno. ADR-007 justificado. |
| **B5** | FTS5 dialecto no decidido | **Standalone** elegido y especificado con SQL completo en §5.7. Incluye triggers, backfill y tokenizer. | ✅ Correcta. No hay ambigüedad. |

## 2. Verificación de correcciones de prioridad alta

| ID | Hallazgo original | Corrección en v0.2.0 | Verificación |
|---|---|---|---|
| **A1** | `available` property con HTTP + mutación (side-effects) | Separado: `available` es O(1) sin side-effects. `check_available()` hace HTTP y muta estado. | ✅ Correcta. PEP 8 compliant. |
| **A2** | FTS5 cambia comportamiento observable de `search()` | Documentado explícitamente como mejora semántica intencional. CA2 corregido. | ✅ Correcta. Justificación ADR-007 incluida. |
| **A3** | Reconciliación N+1 (HTTP call por asset) | Batch embedding: `BATCH_SIZE=100`. Una llamada a `embed(texts)` por batch. | ✅ Correcta. Aprovecha el batch del Protocolo. |
| **A4** | Jobs stuck en 'running' sin heartbeat | Heartbeat query: considera jobs `'running'` con `started_at < now - MAX_RUNNING_INTERVAL` como colgados. | ✅ Correcta. `started_at` se rellena al pasar a 'running'. |
| **A5** | `reconcile()` y `reindex_vectors.py` redundantes | `reindex_vectors.py` es wrapper CLI de `retriever.reconcile()`. | ✅ Correcta. Sin duplicación. |
| **A6** | Tabla de decisión FTS5 mal descrita | Opciones corregidas: standalone vs external. Recomendación: standalone. | ✅ Correcta. |

## 3. Nuevos hallazgos detectados en v0.2.0

### N1 — `result_data` columna en op_jobs no existe en schema actual (📘 Informativo)

§8.1 introduce una columna `result_data` en `op_jobs` que no está en el schema actual.
La migración v13→v14 debe añadirla con `ALTER TABLE op_jobs ADD COLUMN result_data TEXT`.

**Impacto:** Fácil de corregir en implementación. No requiere cambio de diseño.

---

### N2 — Worker subprocess necesita extractores ya cargados (📘 Informativo)

El subprocess en §8.1 ejecuta `extractor.extract(source)`. Si el extractor usa lazy loading
de dependencias (whisper, tesseract), puede haber OOM si dos workers cargan whisper
simultáneamente. El riesgo ya está documentado en §6 (riesgo de RAM).

**Mitigación ya existente:** `MAX_BACKGROUND_WORKERS=1` y semáforo por extractor.

---

### N3 — `op_assets_fts.content` usa `content_sha256` como contenido textual (📘 Informativo)

§5.7 rellena `op_assets_fts.content` con `json_extract(metadata, '$.content_sha256')`.
El SHA-256 es un hash hexadecimal, no contenido textual. La búsqueda FTS5 sobre `content`
no dará resultados útiles. Debería ser `json_extract(metadata, '$.text_preview')` o similar,
o dejar `content` con string vacío y buscar solo por `title`.

**Recomendación:** Corregir en implementación: cambiar `$.content_sha256` a `''` (vacío)
o a `$.text_preview` si el extractor lo proporciona.

---

### N4 — No se especifica tokenizer para `op_memory_fts` (📘 Informativo)

§5.7 especifica `tokenize = 'unicode61'` para `op_assets_fts` pero no para `op_memory_fts`.
La línea 369-372 crea `op_memory_fts` sin tokenizer explícito.

**Recomendación:** Añadir `tokenize = 'unicode61'` también en `op_memory_fts` durante
implementación para consistencia.

---

### N5 — Migración v13→v14 no actualiza `SCHEMA_VERSION` ni `ENGINE_VERSION` (📘 Informativo)

El diseño no documenta que `migrations.py` debe actualizar:
- `SCHEMA_VERSION = 14`
- `ENGINE_VERSION = "0.3.0"`
- Añadir `Migration(14, ...)` al diccionario `MIGRATIONS`

Esto es procedural y se hará en implementación.

---

### N6 — Tabla de alcance (§1) menciona `op_extraction_queue` una vez (📘 Cosmético)

§1 línea 37: "op_extraction_queue (execute-status)" — el resto del diseño usa `op_jobs`.
Es un vestigio del diseño v0.1.0.

**Recomendación:** Pendiente de corregir.

---

## 4. Estado de hallazgos de primera auditoría

| Categoría | V0.1.0 | V0.2.0 |
|---|---|---|
| 🔴 Bloqueantes | 5 | **0** |
| 🟠 Alta | 6 | **0** |
| 🟡 Media | 10 | 10 (diferidos a implementación) |
| 🟢 Baja | 6 | 6 (diferidos) |
| Supuestos ocultos | 7 | 7 (aceptados o mitigados) |

## 5. Veredicto

**✅ Apto para congelar contratos.**

Las 5 correcciones bloqueantes han sido verificadas y son correctas:

1. **B1**: FTS5 standalone con triggers desde `json_extract(metadata, '$.title')`.
   SQL explícito. No requiere columnas que no existen.
2. **B2**: `multiprocessing.Process` por tarea con terminate/kill. PID accesible.
   Resuelve el bug S01 de forma verificable.
3. **B3**: Worker loop en proceso principal publica eventos en el bus con suscriptores.
   El subprocess no necesita el EventBus. Cadena de vectorización intacta.
4. **B4**: GraphRetriever cambia internamente. API pública estable.
5. **B5**: Standalone FTS5 decidido y especificado sin ambigüedad.

Las 6 correcciones de prioridad alta también son correctas y están verificadas.

Los 6 hallazgos nuevos son **informativos y cosméticos** (N1-N6). No requieren cambios
arquitectónicos ni de contratos. Se corregirán durante implementación.

**No existen defectos bloqueantes ni inconsistencias arquitectónicas.**

Se autoriza:
1. ✅ Congelar contratos (CONTRACTS_FROZEN.md v2.0)
2. ✅ Actualizar PROJECT_STATE.md
3. ✅ Iniciar implementación siguiendo §12

---

*Segunda auditoría independiente — 2026-07-03 — Fase 7 Diseño v0.2.0*
