# Fase 7 — Optimizaciones de Producción (Diseño corregido)

> **Versión:** 0.2.0 (rediseño completo — integración B1+B5, B2, B3, B4 trazados desde cero)
> **Fecha:** 2026-07-03
> **Estado:** ✏️ Borrador — pendiente de auditoría independiente
> **Dependencias:** Fase 0–6 completadas, núcleo v0.2.0, Schema v13
> **Línea base de rendimiento:** v0.4.0-fase6 (tag git). Benchmark E2E: 1.643s, BD 208KB, 425 tests

---

## Índice

1. [Resumen](#1-resumen)
2. [Problemas arquitectónicos resueltos](#2-problemas-arquitectónicos-resueltos)
3. [B3 — Background Queue ↔ EventBus ↔ Vector Index](#3-b3--background-queue--eventbus--vector-index)
4. [B1+B5 — FTS5 sobre esquema real](#4-b1b5--fts5-sobre-esquema-real)
5. [B2 — Terminación de procesos extractores](#5-b2--terminación-de-procesos-extractores)
6. [B4 — Flujo GraphRetriever → FTS5 → ranking](#6-b4--flujo-graphretriever--fts5--ranking)
7. [Arquitectura completa post-Fase 7](#7-arquitectura-completa-post-fase-7)
8. [Contratos e interfaces](#8-contratos-e-interfaces)
9. [Migración v13 → v14](#9-migración-v13--v14)
10. [Degradación graceful](#10-degradación-graceful)
11. [Concurrencia](#11-concurrencia)
12. [Riesgos y mitigaciones](#12-riesgos-y-mitigaciones)
13. [Seguridad](#13-seguridad)
14. [Plan de pruebas](#14-plan-de-pruebas)
15. [Plan de implementación](#15-plan-de-implementación)

---

## 1. Resumen

La Fase 6 añadió un backend vectorial opcional (`OllamaEmbedder` + `QdrantVectorStore`) e integró
`MetadataExtracted` como gancho EventBus para la indexación vectorial automática. Sin embargo, cuatro
áreas quedaron con diseño insuficiente para escala de producción:

| Área | Problema real | Síntoma |
|------|--------------|---------|
| **B3** | Background queue no puede publicar EventBus desde proceso hijo | Vector indexing no dispara en extracciones background. Rotura de la cadena de Fase 6. |
| **B1+B5** | FTS5 sobre `op_assets` requiere extraer texto desde JSON blob (`metadata->title`, `metadata->text_preview`). No hay columnas `title`/`body` reales. | Diseño anterior usaba `content_sha256` (hash) como contenido textual. |
| **B2** | Extractores lentos (whisper, OCR) bloquean pipeline síncrono. Sin cancelación de tareas colgadas. | `ProcessPoolExecutor` no expone PIDs individuales. Threads zombis (S01). |
| **B4** | `GraphRetriever.retrieve_assets()` hace full table scan + filtro LIKE en Python. | `list_assets()` devuelve todos los assets ordenados por fecha, `retrieve_assets()` filtra con `query_lower in title.lower()`. Escala O(n). |

**Principios rectores del rediseño:**

1. **EventBus no cruza procesos.** El subprocess nunca llama a `get_bus().publish()`.
   Todo evento se publica desde el proceso principal, donde viven los suscriptores de Fase 6.
2. **FTS5 standalone con triggers** (no `content=` external). Consistente con `kg_nodes_fts`.
   Para `op_assets`, extraer `title`/`body` con `json_extract(metadata, '$.title')`.
   Para `op_memory`, usar columnas reales `title`/`content`.
3. **`multiprocessing.Process` por tarea**, no pool. Cada extracción tiene PID individual,
   cancelable via `terminate()` → `kill()`. Fork-safe: child abre su propia conexión SQLite y
   no toca EventBus ni HTTP clients.
4. **GraphRetriever usa `search_assets()` (FTS5)** internamente. El flujo completo:
   `consulta → retrieve_assets() → store.search_assets() → op_assets_fts MATCH → op_assets JOIN → heuristic_score → sort → top N`.

### Alcance vs. Diferimientos

| Dentro de Fase 7 | Diferido a Fase 8+ | Fuera de roadmap |
|---|---|---|
| FTS5 en `op_assets` + `op_memory` | `Reranker(Protocol)` | API REST `/assets/search` |
| `op_lineage_edges` (desnormalizada) | Múltiples embedders/stores | Exportación masiva |
| Background queue para extractores | Filtro tipado en `VectorStore` | Dashboard web |
| Reconciliación AssetStore↔VectorStore | Streaming PdfExtractor | |
| `_degraded` con autorecuperación | Cache batch `retrieve_neighbors` | |
| `reindex_vectors.py` | Fuga conexiones feedback.py/agent.py | |
| Schema v14 | | |

---

## 2. Problemas arquitectónicos resueltos

La versión anterior del diseño (v0.1.0) fue auditada externamente encontrando 5 defectos
bloqueantes. Este documento los resuelve desde cero, empezando por el más fundamental:

```
Orden de resolución:
  1. B3 (EventBus cross-process) — sin esto, no hay background queue viable
  2. B1+B5 (FTS5 real) — sin esto, no hay búsqueda textual
  3. B2 (terminación) — sin esto, no hay gestión de workers
  4. B4 (GraphRetriever) — sin esto, FTS5 no se usa

Cada sección subsiguiente se apoya en las anteriores.
```

---

## 3. B3 — Background Queue ↔ EventBus ↔ Vector Index

### 3.1 Diagnóstico

El `EventBus` es un singleton **en memoria de proceso** (`eventbus.py:_BUS`). Los suscriptores
(`MetadataExtracted` → vector_index) se registran **en el proceso principal**. Si un subprocess
llama a `get_bus().publish(MetadataExtracted(...))`, publica en el bus de su PROPIO proceso,
donde NO hay suscriptores. El vector indexing nunca se dispara.

El floso existente de Fase 6 es:

```
Proceso Principal (el bus TIENE suscriptores):
  extract(source)
    → save_asset(asset)            # SQLite write
    → get_bus().publish(MetaExtr)  # subscriber vector_index se ejecuta aquí
      → embedder.embed()
      → vector_store.upsert()
    → return
```

El flujo incorrecto del diseño anterior era:
```
Worker (hilo ppal):
  → subprocess ejecuta extracción + save_asset + publish(MetaExtr)  # NADIE ESCUCHA
  → proc.join()
```

### 3.2 Solución: Worker loop con publicación en proceso principal

```
                        PROCESO PRINCIPAL
                        ┌────────────────────────────────────┐
                        │ EventBus                            │
                        │  ┌─ subscriber: vector_index        │
                        │  │   → embedder.embed(asset)        │
                        │  │   → vector_store.upsert(vector)  │
                        │  └─ subscriber: lineage             │
                        │                                     │
                        │ Worker Loop (hilo background)        │
                        │ ┌─────────────────────────────┐     │
                        │ │ LOOP:                       │     │
                        │ │  SELECT pending job          │     │
                        │ │  UPDATE status='running'     │     │
                        │ │  proc = Process(target=extract)  │
                        │ │  proc.start()                │     │
                        │ │  proc.join(timeout=MAX)      │     │
                        │ │  if timeout: terminate/kill  │     │
                        │ │  # ← subprocess terminó      │     │
                        │ │  read result from op_jobs    │     │
                        │ │  if success:                 │     │
                        │ │    publish(MetadataExtracted)│     │
                        │ │    # ↑ subscriber vector_idx │     │
                        │ │    #   se ejecuta AQUÍ       │     │
                        │ │    UPDATE status='done'      │     │
                        │ │  if fail: UPDATE fail/error  │     │
                        │ └─────────────────────────────┘     │
                        └────────────────────────────────────┘
                                    │
                        fork()      │ proc = Process(target=...)
                                    ▼
                        PROCESO HIJO (SOLO escritura SQLite)
                        ┌────────────────────────────────┐
                        │ extractor = registry.get(id)    │
                        │ conn = open_db(db_path)         │
                        │ source = AssetSource(kind, loc) │
                        │ result = extractor.extract(src) │
                        │ if result.asset:                │
                        │   conn.save_asset(result.asset) │
                        │   conn: UPDATE op_jobs done     │
                        │ else:                           │
                        │   conn: UPDATE op_jobs fail     │
                        │ conn.close()                    │
                        │ exit(0)                         │
                        │ # NUNCA toca EventBus           │
                        └────────────────────────────────┘
```

### 3.3 Garantías

1. **El subprocess NUNCA llama a `get_bus()`.** No hay `get_bus()` importado en su alcance.
2. **El hilo worker es el ÚNICO que publica eventos** tras extracción background.
3. **El chain de Fase 6 se preserva:** el subscriber `vector_index` se ejecuta sincrónicamente
   en el hilo worker, igual que en `extract()` síncrono. No hay diferencia funcional.
4. **Concurrencia:** múltiples workers = múltiples hilos publicando eventos.
   `EventBus.publish()` es thread-safe (`_lock = threading.Lock()`).

### 3.4 Worker loop — pseudocódigo completo

```python
# ExtractionService — métodos NUEVOS (los existentes extract()/extract_path() no cambian)

class MetadataExtractionService:
    _worker_thread: threading.Thread | None = None
    _worker_stop: threading.Event = field(default_factory=threading.Event)
    _running_jobs: dict[int, multiprocessing.Process] = field(default_factory=dict)
    _jobs_lock: threading.Lock = field(default_factory=threading.Lock)
    _max_workers: int = 1  # fijo en 1 para MVP (evitar race conditions multi-worker)

    def queue_extract(self, source: AssetSource) -> str:
        """Encola extracción. Retorna job_id (str) para seguimiento."""
        dedup = hashlib.sha256(source.location.encode()).hexdigest()
        with open_db(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO op_jobs "
                "(job_type, priority, status, payload, dedup_key, created_at) "
                "VALUES ('extraction', 0, 'pending', ?, ?, datetime('now'))",
                (json.dumps({"kind": source.kind, "location": source.location}), dedup),
            )
            conn.commit()
            return str(cur.lastrowid)

    def get_queue_status(self, job_id: str) -> dict[str, Any]:
        with open_db(self._db_path) as conn:
            row = conn.execute(
                "SELECT status, error, result_data, started_at, completed_at "
                "FROM op_jobs WHERE id = ?", (int(job_id),)
            ).fetchone()
        if not row:
            return {"status": "not_found"}
        return dict(row)

    def start_worker(self):
        """Inicia el worker loop en un hilo background."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._worker_stop.clear()
        self._worker_thread = threading.Thread(
            target=_worker_loop,
            args=(self._db_path, self._registry, self._store, self._worker_stop,
                  self._running_jobs, self._jobs_lock, self._max_workers),
            daemon=True,
        )
        self._worker_thread.start()

    def stop_worker(self, timeout: float = 30.0):
        """Detiene el worker loop y termina procesos en ejecución."""
        self._worker_stop.set()
        with self._jobs_lock:
            for job_id, proc in list(self._running_jobs.items()):
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
                    if proc.is_alive():
                        proc.kill()
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)

# Worker loop como función module-level (pickleable)
def _worker_loop(db_path: Path, registry: ExtractorRegistry, store: SQLiteAssetStore,
                 stop: threading.Event, running_jobs: dict, jobs_lock: threading.Lock,
                 max_workers: int = 1):
    """Loop principal del worker. Se ejecuta en un hilo DAEMON del proceso principal.

    NOTA: max_workers=1 fijo para el MVP. El loop toma 1 job a la vez.
    Para multi-worker (Fase 8+), reemplazar por contador de running_jobs activos.
    """
    MAX_EXTRACTION_TIME = 300  # segundos (5 min)
    MAX_RUNNING_INTERVAL = "-900"  # 15 min en formato SQL
    POLL_INTERVAL = 0.5  # segundos entre polls

    while not stop.is_set():
        conn = None
        try:
            conn = open_db(db_path)
            begin_immediate(conn, timeout=1.0)

            # Tomar trabajo: pending o jobs colgados (running > MAX_RUNNING_TIME).
            # Usa UPDATE ... RETURNING (SQLite ≥ 3.35.0) para atomicidad:
            # la subquery encuentra el job, el UPDATE lo marca running, y RETURNING
            # devuelve los datos en una sola instrucción. Sin TOCTOU race.
            # Si SQLite < 3.35.0, usar Opción B: SELECT + UPDATE separados
            # dentro de BEGIN IMMEDIATE (serializa escritores).
            try:
                row = conn.execute("""
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
                    RETURNING id, payload
                """, (MAX_RUNNING_INTERVAL,)).fetchone()
            except sqlite3.OperationalError:
                # Fallback: SQLite < 3.35.0 sin RETURNING
                conn.rollback()
                conn.close()
                conn = open_db(db_path)
                begin_immediate(conn, timeout=1.0)
                c = conn.execute("""
                    SELECT id, payload FROM op_jobs
                    WHERE job_type = 'extraction'
                      AND (status = 'pending'
                           OR (status = 'running' AND started_at IS NOT NULL
                               AND started_at < datetime('now', ?)))
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """, (MAX_RUNNING_INTERVAL,))
                sel = c.fetchone()
                if not sel:
                    conn.rollback()
                    conn.close()
                    conn = None
                    stop.wait(POLL_INTERVAL)
                    continue
                conn.execute(
                    "UPDATE op_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?",
                    (sel["id"],),
                )
                row = sel

            if not row:
                conn.rollback()
                conn.close()
                conn = None
                stop.wait(POLL_INTERVAL)
                continue

            job_id = row["id"]
            payload = json.loads(row["payload"] or "{}")
            source = AssetSource(payload.get("kind", "unknown"), payload.get("location", ""))

            conn.commit()
            conn.close()
            conn = None

            # Determinar extractor
            mime = MetadataExtractionService._guess_mime(source.location)
            extractors = registry.get_for_mime(mime)
            if not extractors:
                _mark_job_failed(db_path, job_id, f"No extractor for {mime}")
                continue

            # Lanzar subprocess
            extractor_id = extractors[0].id
            proc = multiprocessing.Process(
                target=_extract_in_worker,
                args=(db_path, job_id, source.location, source.kind, extractor_id),
            )
            with jobs_lock:
                running_jobs[job_id] = proc
            proc.start()
            proc.join(timeout=MAX_EXTRACTION_TIME)

            # Verificar timeout
            if proc.is_alive():
                proc.terminate()   # SIGTERM
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()    # SIGKILL
                _mark_job_failed(db_path, job_id, "timeout after 300s")
                with jobs_lock:
                    running_jobs.pop(job_id, None)
                continue

            # El subprocess ya escribió el resultado en op_jobs
            result = _read_job_result(db_path, job_id)
            if not result or result.get("status") == "failed":
                with jobs_lock:
                    running_jobs.pop(job_id, None)
                continue

            # Publicar evento en el proceso principal (el bus SÍ tiene suscriptores)
            try:
                get_bus().publish(MetadataExtracted(
                    asset_id=result["asset_id"],
                    asset_type=AssetType(result["asset_type"]),
                    extractor=extractor_id,
                    success=True,
                    duration_ms=result["duration_ms"],
                ))
            except Exception as exc:
                log.warning("Failed to publish MetadataExtracted for job %s: %s", job_id, exc)

            with jobs_lock:
                running_jobs.pop(job_id, None)

        except Exception as exc:
            log.error("Worker loop error: %s", exc, exc_info=True)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def _extract_in_worker(db_path: Path, job_id: int, location: str, kind: str, extractor_id: str):
    """Se ejecuta en PROCESO HIJO (fork).

    REGLAS:
      - NO importar EventBus (no hay suscriptores aquí)
      - NO tocar HTTP clients del padre (fork unsafe)
      - NO usar singletons del padre
      - Abrir conexión SQLite FRESCA
      - Cerrar todo antes de salir
    """
    import os
    import sys

    # Reabrir logging en el hijo (fork hereda el logger pero los handlers pueden fallar)
    logging.basicConfig(level=logging.WARNING, force=True)

    conn = None
    try:
        from knowledge.engine.asset_store import SQLiteAssetStore
        from knowledge.engine.connection import begin_immediate, open_db
        from knowledge.engine.extractors.base import get_registry
        from knowledge.engine.ontology.internal import AssetSource

        conn = open_db(db_path)
        store = SQLiteAssetStore(db_path)

        # El registry se hereda por fork (COW), no necesita reinicialización
        registry = get_registry()
        extractor = registry.get(extractor_id)
        if extractor is None:
            _write_job_fail(conn, job_id, f"Extractor {extractor_id} not found")
            return

        source = AssetSource(kind, location)
        result = extractor.extract(source)

        if result.asset and not result.errors:
            saved = store.save_asset(result.asset)
            if saved:
                _write_job_done(conn, job_id, result.asset.asset_id,
                                result.asset.asset_type.value, result.duration_ms)
            else:
                _write_job_fail(conn, job_id, "AssetStore.save_asset() returned False")
        else:
            error_msg = result.errors[0] if result.errors else "unknown error"
            _write_job_fail(conn, job_id, error_msg)

    except Exception as exc:
        if conn is not None:
            try:
                _write_job_fail(conn, job_id, str(exc))
            except Exception:
                pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _write_job_done(conn, job_id, asset_id, asset_type, duration_ms):
    begin_immediate(conn)
    conn.execute(
        "UPDATE op_jobs SET status = 'done', completed_at = datetime('now'), "
        "result_data = ? WHERE id = ?",
        (json.dumps({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "duration_ms": duration_ms,
        }), job_id),
    )
    conn.commit()


def _write_job_fail(conn, job_id, error):
    begin_immediate(conn)
    conn.execute(
        "UPDATE op_jobs SET status = 'failed', completed_at = datetime('now'), error = ? WHERE id = ?",
        (error, job_id),
    )
    conn.commit()


def _mark_job_failed(db_path, job_id, error):
    conn = open_db(db_path)
    try:
        begin_immediate(conn)
        conn.execute(
            "UPDATE op_jobs SET status = 'failed', completed_at = datetime('now'), error = ? WHERE id = ?",
            (error, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def _read_job_result(db_path, job_id):
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT status, result_data, error FROM op_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            return None
        result = {"status": row["status"]}
        if row["result_data"]:
            result.update(json.loads(row["result_data"]))
        if row["error"]:
            result["error"] = row["error"]
        return result
    finally:
        conn.close()
```

### 3.5 Trazabilidad del chain de Fase 6

```
Estado actual (Fase 6, síncrono):
  extract() → save_asset() → publish() → sub: embed → sub: upsert
                                          ↓
                              [misma pila de llamadas, sincrónico]

Estado nuevo (Fase 7, background — EQUIVALENTE FUNCIONAL):
  queue_extract() → INSERT op_jobs → return early
  [worker loop, otro hilo del MISMO proceso]:
    → subprocess: extract() → save_asset() → write result → exit
    → proc.join()
    → read result from op_jobs
    → publish() → sub: embed → sub: upsert
                  ↓
      [misma pila de llamadas, mismo proceso, mismos suscriptores]
```

No hay pérdida de funcionalidad. El worker loop replica exactamente el comportamiento
del `extract()` síncrono, solo que en un hilo background.

---

## 4. B1+B5 — FTS5 sobre esquema real

### 4.1 Diagnóstico del schema actual

```sql
-- op_assets: NO tiene columna `title` ni `body`
-- Los datos textuales viven dentro de metadata (JSON)
CREATE TABLE op_assets (
    id              TEXT PRIMARY KEY,
    asset_type      TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- contiene title, text_preview, ...
    source          TEXT NOT NULL DEFAULT '{}',
    relationships   TEXT NOT NULL DEFAULT '[]',
    quality         REAL NOT NULL DEFAULT 0.0,
    content_sha256  TEXT,   -- ← es un HASH, no contenido textual
    wraps           TEXT,
    created_at      TEXT,
    updated_at      TEXT
);

-- op_memory: SÍ tiene title y content como columnas reales
CREATE TABLE op_memory (
    rowid           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id       TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL,
    title           TEXT NOT NULL,      -- ← columna real
    content         TEXT NOT NULL DEFAULT '',  -- ← columna real
    related_assets  TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT,
    updated_at      TEXT
);

-- op_jobs: necesita columna result_data para comunicación subprocess→worker
CREATE TABLE op_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type     TEXT NOT NULL,
    priority     INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    payload      TEXT,
    dedup_key    TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT
    -- NO tiene result_data
);
```

### 4.2 Decisión: FTS5 standalone con triggers

| Opción | Pros | Contras | Decisión |
|--------|------|---------|----------|
| `content=` external | Sincronización automática al leer. Sin triggers. | Requiere columnas REALES en op_assets. No puede usar `json_extract`. | ❌ |
| **Standalone + triggers** | No requiere modificar op_assets. `json_extract` funciona en triggers. Mismo patrón que `kg_nodes_fts` (v6). Backfill con INSERT SELECT. | Triggers añaden overhead en writes. | ✅ |

El patrón standalone ya está probado en producción: `kg_nodes_fts` se creó en v6 (v6_to_v7.sql)
usando standalone. La diferencia es que `kg_nodes_fts` usa **rebuild completo** (DELETE + INSERT SELECT),
mientras que para `op_assets` y `op_memory` usaremos **triggers** (incremental).

### 4.3 Esquema FTS5 detallado

```sql
-- ============================================================
-- op_assets_fts: standalone FTS5 sobre op_assets
-- Extrae title/text_preview desde metadata JSON mediante json_extract
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS op_assets_fts USING fts5(
    id UNINDEXED,
    title,
    body,
    tokenize = 'unicode61'
);

-- AFTER INSERT
CREATE TRIGGER IF NOT EXISTS op_assets_fts_ai AFTER INSERT ON op_assets BEGIN
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (
        new.rowid,
        new.id,
        json_extract(new.metadata, '$.title'),
        COALESCE(json_extract(new.metadata, '$.text_preview'), '')
    );
END;

-- AFTER DELETE
CREATE TRIGGER IF NOT EXISTS op_assets_fts_ad AFTER DELETE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
END;

-- AFTER UPDATE
CREATE TRIGGER IF NOT EXISTS op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (
        new.rowid,
        new.id,
        json_extract(new.metadata, '$.title'),
        COALESCE(json_extract(new.metadata, '$.text_preview'), '')
    );
END;
```

**Notas sobre `op_assets_fts.body`:**
- El valor proviene de `metadata->text_preview`. Si no existe, se usa `''`.
- `$.content_sha256` es un hash hexadecimal y **no es contenido textual**.
- Si un extractor no proporciona `text_preview`, el asset solo es searchable por `title`.
- En el futuro, si `op_assets` adquiere una columna `body` real, se puede migrar a `content=` external.

```sql
-- ============================================================
-- op_memory_fts: standalone FTS5 sobre op_memory
-- Usa columnas reales title/content (no json_extract)
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(
    id UNINDEXED,
    title,
    content,
    tokenize = 'unicode61'
);

-- AFTER INSERT
CREATE TRIGGER IF NOT EXISTS op_memory_fts_ai AFTER INSERT ON op_memory BEGIN
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

-- AFTER DELETE
CREATE TRIGGER IF NOT EXISTS op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
END;

-- AFTER UPDATE
CREATE TRIGGER IF NOT EXISTS op_memory_fts_au AFTER UPDATE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;
```

### 4.4 Backfill de datos existentes

```sql
-- op_assets: backfill desde datos existentes
INSERT INTO op_assets_fts(rowid, id, title, body)
SELECT rowid, id,
       json_extract(metadata, '$.title'),
       COALESCE(json_extract(metadata, '$.text_preview'), '')
FROM op_assets;

-- op_memory: backfill desde datos existentes
INSERT INTO op_memory_fts(rowid, id, title, content)
SELECT rowid, memory_id, title, content
FROM op_memory;
```

### 4.5 Sincronización (estrategia)

| Operación | Mecanismo | Costo |
|-----------|-----------|-------|
| INSERT en op_assets | Trigger `op_assets_fts_ai` | O(1) — 1 fila FTS |
| UPDATE en op_assets | Trigger `op_assets_fts_au`: delete + insert | O(2) — 2 filas FTS |
| DELETE en op_assets | Trigger `op_assets_fts_ad`: delete command | O(1) — 1 comando |
| INSERT en op_memory | Trigger `op_memory_fts_ai` | O(1) |
| Rebuild completo | Backfill manual (nunca necesario con triggers) | — |
| Recuperación por corrupción | `ALTER TABLE op_assets_fts ...` no es posible. `DROP + CREATE + backfill` | O(n) |

**Nota sobre rebuild:** A diferencia de `kg_nodes_fts` (que se reconstruye en cada compilación
via `SyncPolicy.sync_full()`), `op_assets_fts` y `op_memory_fts` se mantienen mediante triggers.
Si se necesita un rebuild (corrupción de índice), se ejecuta:
```sql
DROP TABLE IF EXISTS op_assets_fts;
DROP TRIGGER IF EXISTS op_assets_fts_ai;
DROP TRIGGER IF EXISTS op_assets_fts_ad;
DROP TRIGGER IF EXISTS op_assets_fts_au;
-- luego CREATE + backfill (repetir las sentencias de §4.3 y §4.4)
```

### 4.6 Búsqueda (search implementation)

```python
class SQLiteAssetStore:
    def search_assets(self, query: str, limit: int = 10,
                      asset_type: AssetType | None = None) -> list[KnowledgeAsset]:
        """Búsqueda FTS5 sobre assets. Fallback a LIKE si FTS5 no disponible.

        La query se sanitiza término a término para prevenir FTS5 syntax injection.
        Cada término se escapa y se une con OR.
        """
        if not query or not query.strip():
            return []

        try:
            safe = _sanitize_fts5(query)
            conn = open_db(self._db_path)
            sql = """
                SELECT a.* FROM op_assets a
                JOIN op_assets_fts fts ON a.rowid = fts.rowid
                WHERE op_assets_fts MATCH ?
            """
            params: list = [safe]
            if asset_type:
                sql += " AND a.asset_type = ?"
                params.append(asset_type.value)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [self._row_to_asset(r) for r in rows]

        except sqlite3.OperationalError:
            # FTS5 no disponible → fallback LIKE
            return self._search_assets_like(query, limit, asset_type)

    def _search_assets_like(self, query: str, limit: int = 10,
                            asset_type: AssetType | None = None) -> list[KnowledgeAsset]:
        """Fallback LIKE: busca substring en metadata->title."""
        conn = open_db(self._db_path)
        pattern = f"%{query}%"
        sql = """
            SELECT id, asset_type, metadata, source, quality, created_at, updated_at, relationships
            FROM op_assets
            WHERE json_extract(metadata, '$.title') LIKE ?
        """
        params = [pattern]
        if asset_type:
            sql += " AND asset_type = ?"
            params.append(asset_type.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [self._row_to_asset(r) for r in rows]


class SQLiteMemoryStore:
    def search(self, query: str, kind: str | None = None,
               limit: int = 10) -> list[MemoryRecord]:
        """Búsqueda FTS5 sobre memorias. Fallback a LIKE."""
        if not query or not query.strip():
            return []

        try:
            safe = _sanitize_fts5(query)
            conn = open_db(self._db_path)
            sql = """
                SELECT m.* FROM op_memory m
                JOIN op_memory_fts fts ON m.rowid = fts.rowid
                WHERE op_memory_fts MATCH ?
            """
            params: list = [safe]
            if kind:
                sql += " AND m.kind = ?"
                params.append(kind)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [self._row_to_record(r) for r in rows]

        except sqlite3.OperationalError:
            return self._search_like(query, kind, limit)

    def _search_like(self, query: str, kind: str | None = None,
                     limit: int = 10) -> list[MemoryRecord]:
        """Fallback LIKE original."""
        conn = open_db(self._db_path)
        pattern = f"%{query}%"
        if kind:
            rows = conn.execute(
                "SELECT * FROM op_memory WHERE kind = ? AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY created_at DESC LIMIT ?",
                (kind, pattern, pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM op_memory WHERE title LIKE ? OR content LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()
        conn.close()
        return [self._row_to_record(r) for r in rows]


def _sanitize_fts5(raw: str) -> str:
    """Convierte una query user en una query FTS5 segura.

    - Cada término se escapa con comillas dobles
    - Se separan por espacio (AND implícito en FTS5)
    - Esto previene FTS5 syntax injection (no se pueden inyectar operadores)
    - "machine learning" busca docs que contengan AMBOS términos
    """
    terms = raw.strip().split()
    if not terms:
        return ""
    # Escapar comillas dobles dentro de cada término
    escaped = ['"' + t.replace('"', '""') + '"' for t in terms]
    return " ".join(escaped)  # espacio = AND implícito en FTS5
```

### 4.7 Cambio de comportamiento observable

| Store | Antes (v13) | Después (v14) | Diferencia |
|-------|-------------|---------------|------------|
| `SQLiteAssetStore` | No tenía `search_assets()` | `search_assets()` usa FTS5 | **Nuevo método** (no rompe nada) |
| `SQLiteMemoryStore.search()` | `LIKE '%query%'` (substring exacta) | FTS5 MATCH (tokenización + case-folding) | **Superconjunto** de resultados anteriores. `search("testing")` → "test", "testing", "tested" |
| `SQLiteLineageStore.get_upstream/downstream` | `LIKE '%asset_id%'` sobre JSON arrays | Índices directos en `op_lineage_edges` | **Sin falsos positivos.** `get_upstream("abc")` NO retorna "abc123" |
| `SQLiteLineageStore.get_lineage()` | `LIKE '%asset_id%'` sobre JSON arrays | `LIKE '%asset_id%'` como fallback, edges como primario | Misma semántica |

El cambio en `MemoryStore.search()` es una mejora semántica intencional bajo ADR-007:
- Firma idéntica: `search(query, kind=None, limit=10) -> list[MemoryRecord]`
- Mismo tipo de retorno
- Comportamiento observable: **superset** de resultados anteriores (no pérdida)
- Justificación: mejora la recuperación de información

---

## 5. B2 — Terminación de procesos extractores

### 5.1 Diagnóstico

`ProcessPoolExecutor` no es viable porque:
1. No expone PIDs individuales → no se puede enviar SIGTERM a una tarea específica
2. `Executor.shutdown(wait=True, cancel_futures=True)` cancela futuros pero no mata
   procesos en ejecución
3. Las tareas colgadas (whisper, OCR, git clone) mantienen el proceso ocupado
   indefinidamente

### 5.2 Solución: multiprocessing.Process por tarea

Cada extracción se ejecuta en su PROPIO `multiprocessing.Process`. Esto proporciona:

- **PID individual** vía `proc.pid` → SIGTERM/SIGKILL por tarea
- **Timeout por tarea**: `proc.join(timeout=MAX_EXTRACTION_TIME)` (independiente por proceso)
- **Aislamiento**: un proceso colgado no afecta a otros workers
- **Cleanup simple**: en `shutdown()`, iterar `_running_jobs` y terminar cada proceso

### 5.3 Chain de terminación

```
proc.join(timeout=300)  # espera 5 min
  ├─ proc termina solo → normal (dentro del timeout)
  ├─ timeout expira → proc.terminate() envía SIGTERM
  │                    └─ proc.join(timeout=5) da 5s para graceful shutdown
  │                       ├─ termina → ok
  │                       └─ timeout (5s) → proc.kill() envía SIGKILL
  └─ excepción → proc.kill() + error log
```

### 5.4 Fork safety

El subprocess se crea con `multiprocessing.Process` (fork start method en Linux).
Los siguientes puntos garantizan seguridad:

| Riesgo | Mitigación |
|--------|-----------|
| Fork en medio de un lock | El worker loop solo forkca entre jobs, sin locks retenidos (ver §3.4). El `_jobs_lock` se adquiere después de `proc.start()`, no antes. |
| Conexión SQLite heredada | `_extract_in_worker()` abre su PROPIA conexión. No usa la del padre. La conexión se cierra al terminar. |
| HTTP clients heredados | `_extract_in_worker()` no hace HTTP. Los clients del padre (httpx en OllamaEmbedder/QdrantVectorStore) se heredan por COW pero no se usan. |
| EventBus heredado | `_extract_in_worker()` no importa `get_bus()`. El singleton EventBus se hereda por COW pero no se toca. |
| Registry heredado | `get_registry()` retorna el mismo singleton (COW). Los extractores se leen, no se modifican. Seguro. |
| Logger heredado | Se reconfigura con `force=True` en el hijo para evitar shared file descriptors. |
| Extractores no pickleables | No se pasan por argumento. Se pasa `extractor_id` (str) y se re-obtienen del registry. |

### 5.5 Zombie prevention

```python
# En worker loop, después de cada proc.join():
proc.close()  # libera recursos del proceso (Python 3.9+)

# En stop_worker():
for job_id, proc in list(self._running_jobs.items()):
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
    proc.close()  # limpia zombie
```

`proc.close()` es esencial (Python 3.9+). Sin `close()`, los procesos terminados
quedan como zombies hasta que el padre los `join()` explícitamente o muere.

### 5.6 Semáforos por extractor

```python
_EXTRACTION_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}
_MAX_CONCURRENT_PER_EXTRACTOR = 1  # evitar OOM (whisper, etc.)

def _get_semaphore(extractor_id: str) -> threading.BoundedSemaphore:
    if extractor_id not in _EXTRACTION_SEMAPHORES:
        _EXTRACTION_SEMAPHORES[extractor_id] = \
            threading.BoundedSemaphore(_MAX_CONCURRENT_PER_EXTRACTOR)
    return _EXTRACTION_SEMAPHORES[extractor_id]
```

---

## 6. B4 — Flujo GraphRetriever → FTS5 → ranking

### 6.1 Diagnóstico del flujo actual

```
GraphRetriever.retrieve_assets("machine learning", limit=10)
  ↓
SQLiteAssetStore.list_assets(limit=30)  ← ordenado por created_at DESC
  ↓  [30 KnowledgeAsset]
Filtro Python: query_lower in title.lower() for each asset
  ↓  [~5 assets que matchean título]
_compute_score() para cada uno
  ↓  [~5 RetrievalResult con score]
sort por score DESC → top 10
```

Problemas:
1. `list_assets()` no tiene filtro textual → devuelve los 30 PRIMEROS por fecha
2. Si el asset más relevante es el #31 por fecha, **no se encuentra**
3. Filtro solo por título (substring exacta), no por contenido
4. FTS5 no se usa en este flujo

### 6.2 Flujo rediseñado

```
GraphRetriever.retrieve_assets("machine learning", limit=10)
  ↓
SQLiteAssetStore.search_assets("machine learning", limit=30)
  ↓
── FTS5 PATH (try) ────────────────────────────────
  op_assets_fts MATCH ? → BM25 rank
    ↓ JOIN op_assets
    ↓ [30 KnowledgeAsset ordenados por BM25 relevance]
── FALLBACK PATH (except OperationalError) ────────
  LIKE sobre json_extract(metadata, '$.title')
    ↓ [30 KnowledgeAsset ordenados por created_at DESC]
───────────────────────────────────────────────────
  ↓
_compute_score() para cada asset (mismo algoritmo que hoy)
  Si el asset no tiene title_match → score bajo pero NO se descarta
  (a diferencia del flujo actual que descarta sin title_match)
  ↓
sort por score DESC → top 10
  ↓ [10 RetrievalResult con heuristic_score]
```

### 6.3 Cambios en GraphRetriever

```python
class SQLiteGraphRetriever:
    def retrieve_assets(self, query: str, limit: int = 10,
                        asset_type: AssetType | None = None) -> list[RetrievalResult]:
        store = self._get_asset_store()
        # ← CAMBIO: usar search_assets() en vez de list_assets()
        assets = store.search_assets(query=query, limit=limit * 3,
                                     asset_type=asset_type)

        results: list[RetrievalResult] = []
        for a in assets:
            score = _compute_score(query, asset=a)
            title = a.metadata.get("title", "")
            results.append(RetrievalResult(
                asset_id=a.asset_id,
                score=score,
                title=title,
                kind=a.asset_type.value,
                snippet=a.metadata.get("content_sha256", "")[:64],
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
```

**Cambios semánticos (justificados):**
1. Antes: solo assets con `query_lower in title.lower()` pasaban el filtro
2. Ahora: FTS5 decide qué assets son relevantes (por title Y body), luego se re-rank
3. El scoring heurístico sigue siendo el mismo (`_compute_score`)
4. FTS5 encuentra assets que LIKE no encontraría (stemming, case-folding, body search)

### 6.4 Flujo completo de búsqueda (sin código muerto)

```
Usuario/Agente
  │
  ▼
GraphRetriever.retrieve_assets(query, limit, asset_type)  ← entry point
  │
  ├──► SQLiteAssetStore.search_assets(query, limit*3, asset_type)
  │     │
  │     ├── FTS5: op_assets_fts MATCH safe_query
  │     │     → rank (BM25) → JOIN op_assets → RETURN [KnowledgeAsset]
  │     │
  │     └── Fallback: _search_assets_like()
  │           → json_extract(metadata, '$.title') LIKE '%query%' → RETURN [...]
  │
  ├──► _compute_score(query, asset)  ← heuristic scoring (sin AI)
  │     • title_match (0.4):   ¿query en title?
  │     • recency (0.15):      ¿actualizado en últimos 365 días?
  │     • quality (0.15):      quality del asset (0.0-1.0)
  │     + tag_match(0.2) + depth(0.1) [para memories]
  │
  ├──► sort by score DESC
  │
  └──► top limit → [RetrievalResult]
        │
        ▼
GraphRetriever.build_context(query, ...)
  ├── retrieve_assets(query, max_assets=10)
  ├── retrieve_memory(query, max_memories=5)
  ├── retrieve_lineage(top_asset_ids)
  ├── retrieve_governance(top_asset_ids)
  └── retrieve_neighbors(top_asset_ids, depth)
        │
        ▼
      ContextBundle (determinista, sin IA)
```

Cada componente tiene un calling path claro:
- `search_assets()` → llamado desde `retrieve_assets()` y `retrieve_neighbors()` (vía lineage)
- `_search_assets_like()` → llamado SOLO como fallback de FTS5 (nunca como ruta primaria)
- `retrieve_assets()` → llamado desde `build_context()`
- `build_context()` → llamado desde `VectorAugmentedRetriever.retrieve_assets()`
  (si `use_vector=False`) o desde agentes que usan GraphRAG

### 6.5 op_lineage_edges: mismo patrón

```sql
CREATE TABLE IF NOT EXISTS op_lineage_edges (
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    relation    TEXT NOT NULL,
    event_id    INTEGER REFERENCES op_lineage(id),
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_src ON op_lineage_edges(src);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_dst ON op_lineage_edges(dst);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_pair ON op_lineage_edges(src, dst);
```

**Backfill desde op_lineage existente:**
```sql
INSERT INTO op_lineage_edges(src, dst, relation, event_id, created_at)
SELECT je1.value, je2.value, e.event_type, e.id, e.event_time
FROM op_lineage e,
     json_each(e.input_ids) AS je1,
     json_each(e.output_ids) AS je2;
```

**Uso en SQLiteLineageStore:**
```python
def get_upstream(self, asset_id: str) -> list[str]:
    # Ruta primaria: op_lineage_edges (indexado, sin LIKE)
    conn = open_db(self._db_path)
    rows = conn.execute(
        "SELECT DISTINCT src FROM op_lineage_edges WHERE dst = ?", (asset_id,)
    ).fetchall()
    conn.close()
    return [r["src"] for r in rows]

def get_downstream(self, asset_id: str) -> list[str]:
    conn = open_db(self._db_path)
    rows = conn.execute(
        "SELECT DISTINCT dst FROM op_lineage_edges WHERE src = ?", (asset_id,)
    ).fetchall()
    conn.close()
    return [r["dst"] for r in rows]
```

---

## 7. Arquitectura completa post-Fase 7

```
                              CAPA 11 (Metadatos Activos)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌────────────┐  ┌────────────┐  ┌──────────────┐
            │ AssetStore │  │ MemoryStore│  │ LineageStore │
            │ (SQLite)   │  │ (SQLite)   │  │ (SQLite)     │
            │            │  │            │  │              │
            │ +op_assets │  │ +op_memory │  │ +op_lineage  │
            │   _fts     │  │   _fts     │  │   _edges     │
            │   triggers │  │   triggers │  │   index      │
            └──────┬─────┘  └──────┬─────┘  └──────┬───────┘
                   │               │               │
                   ▼               ▼               ▼
              ┌─────────────────────────────────────────┐
              │         GraphRetriever (SQLite)          │
              │  retrieve_assets() → search_assets(FTS5)│
              │  retrieve_memory() → search(FTS5)       │
              │  retrieve_lineage() → edges directos    │
              │  retrieve_neighbors() → edges BFS       │
              └──────────────────┬──────────────────────┘
                                 │
             ┌───────────────────▼───────────────────────┐
             │    VectorAugmentedRetriever (extensión)    │
             │  + autorecuperación de _degraded           │
             │  + reconciliation AssetStore↔VectorStore   │
             └───────────────────┬───────────────────────┘
                                 │
                                 ▼
             ┌───────────────────────────────────────────┐
             │    ExtractionService + Background Queue    │
             │  → queue_extract() → op_jobs              │
             │  → Worker loop (thread ppal)              │
             │  → multiprocessing.Process por tarea      │
             │  → EventBus publish desde proceso ppal    │
             │  → Semáforos por extractor                │
             └───────────────────────────────────────────┘
```

---

## 8. Contratos e interfaces

### 8.1 AssetStore (extensión backward-compatible)

```python
class AssetStore(Protocol):
    # ... métodos existentes SIN CAMBIOS ...
    def save_asset(self, asset: KnowledgeAsset) -> bool: ...
    def get_asset(self, asset_id: str) -> KnowledgeAsset | None: ...
    def asset_exists(self, asset_id: str) -> bool: ...
    def delete_asset(self, asset_id: str) -> bool: ...
    def list_assets(self, asset_type=None, limit=100, offset=0) -> list[KnowledgeAsset]: ...
    def count(self, asset_type=None) -> int: ...

    # NUEVO método (default no-op para compatibilidad)
    def search_assets(self, query: str, limit: int = 10,
                      asset_type: AssetType | None = None) -> list[KnowledgeAsset]: ...
```

### 8.2 LineageStore (migración interna)

`LineageStore(Protocol)` no cambia. `get_upstream()` y `get_downstream()` migran
internamente a usar la tabla `op_lineage_edges` en `SQLiteLineageStore`.

### 8.3 MemoryStore (migración interna)

`search()` mantiene la misma firma. La implementación SQLite migra de LIKE a FTS5.

### 8.4 ExtractionService (extensión)

```python
class MetadataExtractionService:
    # Métodos existentes SIN CAMBIOS
    def extract(self, source: AssetSource) -> dict: ...

    # NUEVOS métodos
    def queue_extract(self, source: AssetSource) -> str: ...
    def get_queue_status(self, job_id: str) -> dict: ...
    def start_worker(self) -> None: ...
    def stop_worker(self, timeout: float = 30.0) -> None: ...
```

### 8.5 VectorStore (mejora interna)

```python
class VectorStore(Protocol):
    @property
    def available(self) -> bool:
        """O(1), sin side-effects. Refleja último estado conocido."""

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real. HTTP + mutación de estado."""
```

### 8.6 VectorAugmentedRetriever (extensión)

```python
class VectorAugmentedRetriever:
    def reconcile(self, dry_run: bool = True,
                  batch_size: int = 100) -> dict[str, int]:
        """Reconcilia AssetStore con VectorStore en batches."""
```

---

## 9. Migración v13 → v14

### 9.1 Archivo de migración: v13_to_v14.sql

```sql
-- Migration v13 → v14: FTS5 + op_lineage_edges + op_jobs.result_data

-- ============================================================
-- PASO 1: op_assets_fts (standalone, sin content= external)
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS op_assets_fts USING fts5(
    id UNINDEXED, title, body,
    tokenize = 'unicode61'
);

-- Triggers
CREATE TRIGGER IF NOT EXISTS op_assets_fts_ai AFTER INSERT ON op_assets BEGIN
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;

CREATE TRIGGER IF NOT EXISTS op_assets_fts_ad AFTER DELETE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
END;

CREATE TRIGGER IF NOT EXISTS op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;

-- Backfill
INSERT INTO op_assets_fts(rowid, id, title, body)
SELECT rowid, id,
       json_extract(metadata, '$.title'),
       COALESCE(json_extract(metadata, '$.text_preview'), '')
FROM op_assets;

-- ============================================================
-- PASO 2: op_memory_fts (standalone)
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(
    id UNINDEXED, title, content,
    tokenize = 'unicode61'
);

-- Triggers
CREATE TRIGGER IF NOT EXISTS op_memory_fts_ai AFTER INSERT ON op_memory BEGIN
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
END;

CREATE TRIGGER IF NOT EXISTS op_memory_fts_au AFTER UPDATE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

-- Backfill
INSERT INTO op_memory_fts(rowid, id, title, content)
SELECT rowid, memory_id, title, content
FROM op_memory;

-- ============================================================
-- PASO 3: op_lineage_edges (desnormalizada)
-- ============================================================
CREATE TABLE IF NOT EXISTS op_lineage_edges (
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    relation    TEXT NOT NULL,
    event_id    INTEGER REFERENCES op_lineage(id),
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_src ON op_lineage_edges(src);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_dst ON op_lineage_edges(dst);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_pair ON op_lineage_edges(src, dst);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_event ON op_lineage_edges(event_id);

-- Backfill desde op_lineage
-- NOTA: json_each(input_ids) x json_each(output_ids) = producto cartesiano.
-- Si un evento tiene 100 inputs y 100 outputs, genera 10,000 edges.
-- Actualmente hay 0 eventos de lineage, por lo que el backfill es trivial.
-- Si en el futuro hay miles de eventos con arrays grandes, usar:
--   INSERT INTO op_lineage_edges ... LIMIT 10000;
--   (repetir hasta que INSERT afecte 0 filas)
INSERT INTO op_lineage_edges(src, dst, relation, event_id, created_at)
SELECT je1.value, je2.value, e.event_type, e.id, e.event_time
FROM op_lineage e,
     json_each(e.input_ids) AS je1,
     json_each(e.output_ids) AS je2;

-- ============================================================
-- PASO 4: op_jobs.result_data (para comunicación subprocess→worker)
-- ============================================================
ALTER TABLE op_jobs ADD COLUMN result_data TEXT;

-- ============================================================
-- PASO 5: Notificar a migrations.py
-- ============================================================
-- En knowledge/engine/migrations.py:
--   SCHEMA_VERSION = 14
--   ENGINE_VERSION = "0.3.0"
--   MIGRATIONS[14] = Migration(14, "FTS5 op_assets + op_memory + op_lineage_edges", "v13_to_v14.sql")
```

### 9.2 Rollback plan

No hay rollback trivial una vez que los triggers están activos (no se puede deshacer
`ALTER TABLE`). Estrategias:

| Escenario | Acción |
|-----------|--------|
| FTS5 corrupto | DROP + CREATE + backfill (no hay pérdida de datos, solo de índice) |
| op_lineage_edges corrupto | DROP + backfill |
| op_jobs.result_data | `ALTER TABLE op_jobs DROP COLUMN result_data` (SQLite 3.35.0+) |
| FTS5 demasiado lento | Desactivar triggers: `DROP TRIGGER op_assets_fts_ai; ...` + `DROP TABLE op_assets_fts`. Volver a LIKE. |
| Migración completa deshacer | Restaurar backup de la BD antes de migrar |

---

## 10. Degradación graceful

| Componente | Degradado = ? | Comportamiento |
|---|---|---|
| `AssetStore.search_assets()` | FTS5 no disponible (`OperationalError`) | `_search_assets_like()`: `json_extract(metadata, '$.title') LIKE '%query%'` |
| `MemoryStore.search()` | FTS5 no disponible | `_search_like()`: `title LIKE ? OR content LIKE ?` (mismo que hoy) |
| `LineageStore.get_upstream/downstream` | `op_lineage_edges` no existe | LIKE sobre `op_lineage.input_ids/output_ids` (mismo que hoy) |
| `VectorStore.search()` | `_degraded = True` | Retorna lista vacía. `VectorAugmentedRetriever` solo usa búsqueda heurística |
| `ExtractionService.queue_extract()` | Worker no disponible | Ejecuta síncrono (llama a `extract()` internamente) |
| Worker loop | Fallo en el hilo | Se reinicia en la próxima llamada a `start_worker()`. Jobs pendientes siguen en op_jobs. |
| Subprocess | Timeout/fallo | `_mark_job_failed()`. Job re-intentable. |
| `reindex_vectors.py` | Embedder/VectorStore caído | Reporta error, no modifica nada |

**Todas las degradaciones son transparentes para el llamante.** Ninguna función de Fase 7
lanza excepción por falta de FTS5, tabla de edges, worker, o backend vectorial.

---

## 11. Concurrencia

### 11.1 Background Queue (resumen)

| Componente | Tecnología | Concurrencia |
|---|---|---|
| Worker loop | `threading.Thread` (daemon) | 1 hilo |
| Extracción | `multiprocessing.Process` por job | Configurable: `MAX_BACKGROUND_WORKERS` (default 2) |
| Semáforo por extractor | `threading.BoundedSemaphore` | `_MAX_CONCURRENT_PER_EXTRACTOR = 1` |
| EventBus publish | Sincrónico, thread-safe | Se ejecuta en el hilo worker |
| SQLite acceso | Cada proceso abre su propia conexión | WAL mode permite lectores concurrentes |

### 11.2 Worker pool limit

**Decisión: 1 worker fijo para el MVP.** El worker loop procesa un job a la vez.
Un solo worker evita race conditions de acceso a SQLite entre múltiples subprocesos,
OOM por carga simultánea de modelos (whisper, OCR), y simplifica la gestión de zombies.

```python
_MAX_BACKGROUND_WORKERS = 1  # fijo para MVP. Multi-worker en Fase 8+
```

Para escalar a multi-worker en el futuro:
- Usar contador de `len(_running_jobs)` antes de lanzar nuevo subprocess
- Usar `threading.Semaphore(max_workers)` en el worker loop
- Cada worker necesita su propio ciclo SELECT+UPDATE (no compartir el mismo hilo loop)

### 11.3 Heartbeat para jobs colgados

La query de selección de trabajo incluye jobs que están en estado `'running'`
pero cuyo `started_at` es anterior a `MAX_RUNNING_INTERVAL` (15 min):

```sql
WHERE (status = 'pending'
       OR (status = 'running'
           AND started_at IS NOT NULL
           AND started_at < datetime('now', '-900 seconds')))
```

Esto evita que un job quede permanentemente en `'running'` si el worker muere.

### 11.4 Autorecuperación VectorStore

```python
class QdrantVectorStore:
    _degraded: bool = False
    _last_check: float = 0.0
    _backoff: float = 1.0  # segundos, duplica hasta 60s

    @property
    def available(self) -> bool:
        """O(1), sin side-effects."""
        return not self._degraded

    def check_available(self) -> bool:
        """Health check HTTP. Side-effects: muta _degraded y _backoff.

        4xx: mantiene _degraded=True (no recuperable)
        5xx/timeout: _backoff *= 2 (hasta 60s)
        Éxito: _degraded=False, _backoff=1.0
        """
        if not self._degraded:
            return True
        now = time.monotonic()
        if now - self._last_check < self._backoff:
            return False
        self._last_check = now
        try:
            self._client.get(f"/collections/{self._collection}")
            self._degraded = False
            self._backoff = 1.0
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                self._degraded = True  # 4xx
            else:
                self._backoff = min(self._backoff * 2, 60.0)
            return False
        except Exception:
            self._backoff = min(self._backoff * 2, 60.0)
            return False
```

Mismo patrón en `OllamaEmbedder`.

---

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Probab. | Mitigación |
|--------|---------|---------|------------|
| Trigger FTS5 ralentiza writes en op_assets | Latencia extra en INSERT/UPDATE | Baja | Trigger escribe 1 fila FTS, no bloquea. Benchmarks comparativos. |
| op_lineage_edges backfill genera millones de filas | DB llena o migración lenta | Baja | `op_lineage` actual tiene 0 eventos. Si crece, backfill con LIMIT+OFFSET. |
| Worker multiprocessing consume RAM (whisper, OCR) | OOM en GX10 | Media | `MAX_BACKGROUND_WORKERS=1`. Semáforo por extractor. `token_screen.py` verifica RAM antes de lanzar worker. |
| Subprocess fork hereda fd de SQLite/HTP | Corrupción de datos | Media | `_extract_in_worker()` abre conexión FRESCA. No usa la del padre. El padre cierra su conexión antes de fork. |
| Reconciliación elimina vectores falsos positivos | Assets sin vector real | Baja | `dry_run=True` por defecto. `--execute` requiere flag explícito. |
| Backoff en autorecuperación mascara fallos reales | Backend reporta available intermitentemente | Baja | Log warning en cada auto-reversión. Métrica `vector_recovery_count`. |
| FTS5 `unicode61` no maneja bien queries con guiones (ej: "ABC-123") | Falso negativo | Baja | `unicode61` tokeniza por palabras. "ABC-123" → tokens "ABC", "123". |
| Worker muere mientras status='running' | Jobs zombie | Media | Heartbeat query (§11.3) re-asigna jobs colgados después de 15 min. |

---

## 13. Seguridad

| Aspecto | Medida |
|---------|--------|
| FTS5 injection | `_sanitize_fts5()` escapa cada término con comillas. No se usa concatenación en MATCH. |
| Worker isolation | `multiprocessing.Process` por tarea con timeout. `terminate()` (SIGTERM) → `kill()` (SIGKILL). |
| op_jobs extraction queue | Solo almacena `kind` y `location` del source. No datos sensibles. |
| Reconciliación | Solo opera sobre vectores. No accede a `kg_*` ni `op_audit`. |
| Fork safety | Child abre conexión SQLite nueva. No hereda HTTP clients. No llama a EventBus. |

---

## 14. Plan de pruebas

### 14.1 Tests unitarios (nuevos)

| Test | Componente | Verifica |
|------|-----------|----------|
| `test_asset_store_search_fts5` | SQLiteAssetStore | `search_assets()` con FTS5 retorna assets correctos |
| `test_asset_store_search_fallback_like` | SQLiteAssetStore | Sin FTS5, fallback LIKE funciona |
| `test_asset_store_search_empty` | SQLiteAssetStore | Query vacía retorna [] |
| `test_asset_store_search_injection` | SQLiteAssetStore | Query maliciosa no inyecta FTS5 |
| `test_memory_store_search_fts5` | SQLiteMemoryStore | `search()` con FTS5 retorna superset de LIKE |
| `test_memory_store_search_fallback` | SQLiteMemoryStore | Fallback LIKE igual que hoy |
| `test_lineage_edges_get_upstream` | SQLiteLineageStore | `get_upstream()` desde edges correcto |
| `test_lineage_edges_no_false_pos` | SQLiteLineageStore | "abc" no matchea "abc123" |
| `test_lineage_edges_backfill` | migrations v14 | Backfill produce edges correctos |
| `test_extraction_queue_enqueue` | ExtractionService | `queue_extract()` crea op_jobs row |
| `test_extraction_queue_status` | ExtractionService | `get_queue_status()` refleja estado |
| `test_extraction_queue_worker_eventbus` | ExtractionService | Worker publica MetadataExtracted en proceso ppal |
| `test_worker_process_timeout` | ExtractionService | Subprocess que excede timeout es terminado |
| `test_worker_process_zombie` | ExtractionService | proc.close() previene zombies |
| `test_worker_job_heartbeat` | ExtractionService | Job stuck en 'running' es re-asignado |
| `test_worker_fork_safety` | ExtractionService | Subprocess no arrastra fd del padre |
| `test_fts5_triggers_insert` | migrations v14 | Trigger after insert funciona |
| `test_fts5_triggers_delete` | migrations v14 | Trigger after delete funciona |
| `test_fts5_triggers_update` | migrations v14 | Trigger after update funciona |
| `test_fts5_backfill` | migrations v14 | Backfill produce índices correctos |
| `test_graph_retriever_retrieve_assets_fts5` | SQLiteGraphRetriever | `retrieve_assets()` usa `search_assets()` |
| `test_graph_retriever_retrieve_memory_fts5` | SQLiteGraphRetriever | `retrieve_memory()` usa FTS5 |
| `test_qdrant_auto_recovery` | QdrantVectorStore | `_degraded` se auto-revierte |
| `test_qdrant_4xx_no_recovery` | QdrantVectorStore | Error 400 no reactiva |
| `test_ollama_auto_recovery` | OllamaEmbedder | Mismo patrón |
| `test_reconcile_dry_run` | VectorAugmentedRetriever | Dry-run no modifica vectores |
| `test_reconcile_batch` | VectorAugmentedRetriever | `BATCH_SIZE=100`, 1 embed call por batch |
| `test_reindex_vectors` | reindex_vectors.py | Script wrapper llama a reconcile() |

### 14.2 Tests de integración

| Test | Verifica |
|------|---------|
| `test_e2e_fts5_search` | Pipeline completo → asset en BD → FTS5 retorna asset |
| `test_e2e_background_extraction` | queue_extract → worker → subprocess → asset → vector_index |
| `test_e2e_degraded_recovery` | Tirar backend → degradado → autorecuperación → funciona |
| `test_e2e_lineage_edges` | lineage event → edges consultable sin LIKE |
| `test_e2e_reconciliation` | Asset eliminado → reconcil limpia vector huérfano |

### 14.3 Benchmarks

| Operación | v0.4.0 (baseline) | Target Fase 7 |
|---|---|---|
| Búsqueda heurística (1 asset) | 0.024s (30 assets LIKE) | <10ms (FTS5 indexado) |
| Búsqueda heurística (1000 assets) | N/A (solo 2 docs) | <50ms (FTS5 + BM25) |
| Búsqueda memory (10 records) | 0.000s (0 registros) | <10ms (FTS5) |
| Lineage con 10 assets | 0.000s (0 eventos) | <5ms (edges indexados) |
| Migración v13→v14 | N/A | <0.100s |
| Total E2E (2 docs) | 1.643s | <2.0s (no empeorar) |

### 14.4 Criterios de aceptación

| ID | Criterio | Verificación |
|----|----------|-------------|
| CA1 | FTS5 en `op_assets` y `op_memory` funciona con triggers | pytest + benchmark |
| CA2 | `search_assets()` retorna los mismos assets que LIKE más los que FTS5 encuentra por stemming | pytest comparativo |
| CA3 | `MemoryStore.search()` retorna superset de resultados LIKE | pytest |
| CA4 | `get_upstream("abc")` con edges no retorna "abc123" | pytest |
| CA5 | Migración v13→v14 backfillea correctamente | pytest |
| CA6 | `queue_extract()` sin worker fallback a síncrono | pytest |
| CA7 | Worker ejecuta extractor en subprocess separado | pytest |
| CA8 | MetadataExtracted se publica desde proceso ppal (no hijo) | test_worker_eventbus |
| CA9 | Vector indexing se ejecuta tras publicación de worker | test_e2e_background |
| CA10 | proc.kill() termina proceso colgado | pytest con mock |
| CA11 | `_degraded` se auto-revierte en Qdrant y Ollama | pytest |
| CA12 | `reconcile(dry_run=True)` no modifica nada | pytest |
| CA13 | Sin FTS5, sin edges, sin worker: TODO funciona como hoy | pytest |
| CA14 | `retrieve_assets()` usa `search_assets()` internamente | pytest |
| CA15 | Benchmark E2E no duplica latencia vs v0.4.0 | benchmark manual |
| CA16 | 0 nuevos fallos (nuevos tests) | pytest --collect-only |
| CA17 | Ruff clean en todos los archivos nuevos/modificados | ruff check |
| CA18 | Sin cambios en `core/`, sin renombrar símbolos | revisión manual |

---

## 15. Plan de implementación

| Paso | Componente | Depende de | Esfuerzo |
|------|-----------|------------|----------|
| 1 | Schema v14: migrations.py + v13_to_v14.sql | — | 1h |
| 2 | AssetStore.search_assets() + _search_assets_like() + _sanitize_fts5() | Paso 1 | 2h |
| 3 | MemoryStore.search() migra a FTS5 + fallback | Paso 1 | 1h |
| 4 | op_lineage_edges: escritura + lectura en LineageStore | Paso 1 | 2h |
| 5 | ExtractionService.queue_extract() + get_queue_status() | — | 1h |
| 6 | Worker loop + _extract_in_worker + subprocess management | Paso 5 | 4h |
| 7 | Semáforos + MAX_BACKGROUND_WORKERS + heartbeat | Paso 6 | 1h |
| 8 | GraphRetriever.retrieve_assets() migra a search_assets() | Paso 2 | 1h |
| 9 | Autorecuperación QdrantVectorStore | — | 2h |
| 10 | Autorecuperación OllamaEmbedder | Paso 9 | 1h |
| 11 | VectorAugmentedRetriever.reconcile() | Pasos 9-10 | 2h |
| 12 | reindex_vectors.py (wrapper CLI) | Paso 11 | 1h |
| 13 | Tests unitarios (20+) | Pasos 1-12 | 6h |
| 14 | Tests integración (5) | Pasos 1-12 | 3h |
| 15 | Benchmark comparativo | Pasos 13-14 | 2h |
| **Total** | | | **~30h** |

---

*Documento de diseño — Fase 7 Optimizaciones de Producción v0.2.0 — Knowledge Engine — 2026-07-03*
