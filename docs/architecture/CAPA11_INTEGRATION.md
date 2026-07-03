# CAPA 11 — Integración con Knowledge Engine existente

**Versión:** 0.2.0  
**Fecha:** 2026-07-02  
**Estado:** Fase 0–4 implementadas y cerradas. Fase 5 en diseño (aprobado con observaciones)

---

## 1. Inventario reutilizable

### Leyenda
| Símbolo | Significado |
|---|---|
| ✅ Reutilización directa | Se usa tal cual, sin cambios |
| 🔧 Extensión | Añadir funcionalidad sin modificar lo existente |
| 🔄 Sustitución | Reemplazar implementación (manteniendo interfaz) |
| ❌ No utilizar | No aplica a Capa 11 |

### Por componente

| Componente | Uso en Capa 11 | Detalle |
|---|---|---|
| `compiler.py` | ✅ Directa | Emite `CompileCompleted` vía `EventBus` (ya lo hace). No se toca. |
| `scanner.py` | 🔧 Extensión | Añadir `ScanCompleted` event al EventBus. No se modifica lógica interna. |
| `parser.py` | ✅ Directa | Se usa para contenido Markdown. No se toca. |
| `sqlite_writer.py` | ❌ No utilizar | Capa 11 escribe en `op_assets`, `op_lineage`, `op_memory` (nuevas tablas). Usa `connection.open_db()` como toda escritura. |
| `reader.py` | ✅ Directa | Se usa para consultar el grafo existente. No se toca. |
| `repository.py` | ✅ Directa | `SQLiteKnowledgeRepository` se reutiliza para consultas de assets. |
| `eventbus.py` | ✅ Directa | Es el backbone de Capa 11. Todos los eventos viajan por EventBus. |
| `subscribers.py` | 🔧 Extensión | Añadir `AssetIndexSubscriber`, `OpenLineageSubscriber`, `MetadataChangeSubscriber`. |
| `pipeline.py` | 🔧 Extensión | Pipeline actual (snapshot→compile→verify→archive→qdrant→rules). Se añade stage opcional `metadata_extract`. |
| `api.py` | 🔧 Extensión | Nuevos endpoints: `/metadata/assets`, `/metadata/lineage/{id}`, `/metadata/memory`. Sin modificar existentes. |
| `feedback.py` | ✅ Directa | `op_feedback_agg` alimenta el `MemoryStore`. |
| `rules.py` | ✅ Directa | `RuleEvaluator` genera metadata derivada (quality, confidence). |
| `deduction.py` | 🔧 Extensión | `StateDeductor` puede alimentar el `AssetStore` con relaciones inferidas. |
| `recommendation.py` | ❌ No utilizar | Las recomendaciones pertenecen a Fase E. Capa 11 usa GraphRAG en su lugar. |
| `knowledge_base.py` | 🔧 Extensión | La KB existente se enriquece con Schema.org JSON-LD embebido. |
| `notify.py` | 🔧 Extensión | Nuevo notificador: `WebhookMetadataChange` para propagar cambios a downstreams. |
| `rollback.py` | ✅ Directa | `CompileRollback` protege escrituras en `op_assets`. |
| `snapshot_store.py` | ✅ Directa | Snapshot existente usado para detección incremental de cambios en assets. |
| `connection_pool.py` | ✅ Directa | Los Stores de Capa 11 usarán el pool de lectura. |
| `connection.py` | ✅ Directa | Todos los Stores usan `open_db()` y `begin_immediate()`. |
| `determinism.py` | ✅ Directa | El hash de assets NO afecta al determinism hash del grafo. Son independientes. |
| `archiver.py` | ✅ Directa | Los archives existentes también se indexan como `KnowledgeAsset`. |
| `metrics.py` | 🔧 Extensión | Nuevas métricas: `asset_extractions_total`, `asset_extraction_duration_seconds`, `lineage_events_total`. |

---

## 2. Modelo de activos

### Diagrama UML

```
┌─────────────────────────────────────────────┐
│               KnowledgeAsset                 │
│  (frozen dataclass)                          │
├─────────────────────────────────────────────┤
│  asset_id: str                               │
│  asset_type: AssetType                       │
│  content_sha256: str                         │
│  metadata: AssetMetadata                     │
│  source: AssetSource                         │
│  relationships: tuple[AssetRelationship]      │
│  quality: float                              │
│  created_at: str                             │
│  updated_at: str                             │
└──────────────────────┬──────────────────────┘
                       │ wraps
          ┌────────────┼────────────┬──────────────┐
          ▼            ▼            ▼              ▼
     Document     SourceObject   CompileResult   AuditEvent
    (models.py)   (models.py)    (models.py)     (models.py)
```

**Ninguno de los 4 modelos existentes se modifica.** `KnowledgeAsset` los envuelve mediante `metadata["wraps"] = "document:doc_id_123"`.

### Relaciones

| Modelo existente | KnowledgeAsset.metadata["wraps"] |
|---|---|
| `Document` | `"document:{doc_id}"` |
| `SourceObject` | `"source:{path}"` |
| `CompileResult` | `"compile:{run_id}"` |
| `AuditEvent` | `"audit:{audit_id}"` |

### AssetType (enum, en ontology/internal.py)

```python
class AssetType(StrEnum):
    MARKDOWN = "markdown"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    PDF = "pdf"
    OFFICE_DOC = "office_doc"
    OFFICE_SHEET = "office_sheet"
    OFFICE_SLIDE = "office_slide"
    CONVERSATION = "conversation"
    GIT_REPO = "git_repo"
    API_REFERENCE = "api_reference"
    DECISION = "decision"
    INCIDENT = "incident"
    DATASET = "dataset"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"
```

---

## 3. Extractores

### Extractor(Protocol)

```python
class Extractor(Protocol):
    asset_type: AssetType
    mime_types: list[str]         # ["text/markdown", "video/mp4", …]
    cost: Literal["O(1)", "O(n)", "O(n²)"]  # coste estimado por asset
    dependencies: list[str]        # ["opencv-python", "pytesseract", …]
    modifies_content: bool         # True si transforma el asset (OCR, thumbnail)

    def can_handle(self, source: AssetSource) -> bool: ...
    def extract(self, source: AssetSource) -> ExtractionResult: ...
    def get_metadata_keys(self) -> list[str]: ...  # qué metadatos produce
```

### Extractores específicos

| Extractor | MIME | Metadatos obtenidos | Coste | Dependencias | ¿Modifica? |
|---|---|---|---|---|---|
| `MarkdownExtractor` | `text/markdown` | title, tags, relations, quality, confidence | O(1) | yaml (built-in) | No |
| `PdfExtractor` | `application/pdf` | text, pages, author, title, creation_date, OCR | O(n) | PyMuPDF, pytesseract | No (solo metadata) |
| `ImageExtractor` | `image/jpeg`, `image/png`, `image/webp` | EXIF, GPS, device, date, OCR, objects?, faces? | O(n) | Pillow, pytesseract | Sí (thumbnail, embeddings) |
| `VideoExtractor` | `video/mp4`, `video/webm`, `video/avi` | duration, resolution, fps, bitrate, codec, audio, language, scenes, OCR, thumbnails, transcript | O(n²) | ffmpeg, ffprobe, opencv-python, whisper | Sí (thumbnails, transcript) |
| `AudioExtractor` | `audio/mp3`, `audio/wav`, `audio/flac` | duration, bitrate, codec, sample_rate, channels, language, transcript | O(n) | ffprobe, whisper | Sí (transcript) |
| `OfficeExtractor` | `application/vnd.openxmlformats-officedocument.*` | text, tables, images, author, title, created, modified | O(n) | python-docx, openpyxl, pptx | No |
| `GitExtractor` | N/A (clona repo) | commits, authors, branches, tags, release_notes, changelog | O(n²) | git (built-in) | Sí (clona) |
| `WebExtractor` | `text/html` | title, description, text, images, links, publication_date | O(n) | httpx, beautifulsoup4 | No |
| `CompileExtractor` | N/A (evento) | documents_changed, errors, duration, graph_version | O(1) | Ninguna | No |
| `AuditExtractor` | N/A (op_audit) | action, actor, result, correlation_id | O(n) | Ninguna | No |

---

## 4. Metadatos por tipo

### Video (metadatos técnicos)

| Campo | Tipo | Obligatorio | Fuente |
|---|---|---|---|
| `hash` | `sha256` | ✅ | ffprobe + contenido binario |
| `duration` | `float` (segundos) | ✅ | ffprobe |
| `width` | `int` (px) | ✅ | ffprobe |
| `height` | `int` (px) | ✅ | ffprobe |
| `fps` | `float` | ✅ | ffprobe |
| `bitrate` | `int` (bps) | ✅ | ffprobe |
| `video_codec` | `str` | ✅ | ffprobe |
| `audio_codec` | `str` | ✅ | ffprobe |
| `audio_sample_rate` | `int` | ✅ | ffprobe |
| `audio_channels` | `int` | ✅ | ffprobe |
| `language` | `str` (ISO 639-1) | ⬜ Opcional | whisper (transcripción) |
| `has_ocr` | `bool` | ⬜ Opcional | OCR pipeline |
| `ocr_text` | `str` | ⬜ Opcional | OCR pipeline |
| `transcript` | `str` | ⬜ Opcional | whisper |
| `scene_count` | `int` | ⬜ Opcional | scene detection (opencv) |
| `scenes` | `list[dict]` | ⬜ Opcional | scene detection |
| `thumbnails` | `list[str]` (paths) | ⬜ Opcional | ffmpeg |
| `embeddings` | `list[float]` | ⬜ Opcional | embedding model |
| `exif` | `dict` | ⬜ Opcional | si el contenedor lo soporta |
| `gps_lat` | `float` | ⬜ Opcional | si el dispositivo lo graba |
| `gps_lon` | `float` | ⬜ Opcional | si el dispositivo lo graba |
| `device_make` | `str` | ⬜ Opcional | metadata del contenedor |
| `device_model` | `str` | ⬜ Opcional | metadata del contenedor |
| `recorded_at` | `str` (ISO 8601) | ⬜ Opcional | metadata del contenedor |
| `author` | `str` | ⬜ Opcional | metadata del contenedor |
| `license` | `str` (SPDX) | ⬜ Opcional | input del usuario |
| `checksum` | `sha256` | ✅ | mismo que `hash` |
| `signature` | `str` | ⬜ Opcional | verificación futura |

### Imagen

| Campo | Obligatorio | Fuente |
|---|---|---|
| hash, width, height, format | ✅ | Pillow |
| exif, gps, device_make, device_model, date_taken | ⬜ | EXIF |
| ocr_text, detected_objects, detected_faces | ⬜ | pytesseract + modelos CV |
| thumbnail | ⬜ | Pillow resize |
| embeddings | ⬜ | embedding model |
| license, author | ⬜ | input usuario |

### PDF

| Campo | Obligatorio | Fuente |
|---|---|---|
| hash, pages, title, author, creation_date | ✅ | PyMuPDF |
| text (full), has_ocr, ocr_text | ⬜ | PyMuPDF + pytesseract |
| table_count, has_images, image_count | ⬜ | PyMuPDF |
| embeddings (de chunks) | ⬜ | embedding model |

### Office

| Campo | Obligatorio | Fuente |
|---|---|---|
| hash, title, author, created_at, modified_at | ✅ | python-docx / openpyxl / pptx |
| paragraph_count, table_count, sheet_count, slide_count | ✅ | librería específica |
| full_text | ⬜ | extracción de contenido |
| has_embeddings | ⬜ | embedding model |

---

## 5. Almacenamiento (SQLite first)

### AssetStore(Protocol)

```python
class AssetStore(Protocol):
    def store(self, asset: KnowledgeAsset) -> None: ...
    def get(self, asset_id: str) -> KnowledgeAsset | None: ...
    def search(self, query: str, asset_type: AssetType | None = None, limit: int = 10) -> list[KnowledgeAsset]: ...
    def delete(self, asset_id: str) -> bool: ...
    def count(self, asset_type: AssetType | None = None) -> int: ...
```

**Tabla SQLite:** `op_assets`
```sql
CREATE TABLE IF NOT EXISTS op_assets (
    id              TEXT PRIMARY KEY,
    asset_type      TEXT NOT NULL,
    content_sha256  TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    source          TEXT NOT NULL DEFAULT '{}',  -- JSON
    quality         REAL NOT NULL DEFAULT 0.0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    wraps           TEXT  -- "document:doc_id_123" | "source:path" | ""
);
CREATE INDEX IF NOT EXISTS idx_op_assets_type ON op_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_op_assets_sha ON op_assets(content_sha256);
```

### LineageStore(Protocol)

```python
class LineageStore(Protocol):
    def store_event(self, event: dict) -> None: ...       # OpenLineage event
    def get_lineage(self, asset_id: str) -> list[dict]: ... # inputs/outputs
    def get_downstream(self, asset_id: str) -> list[str]: ...
    def get_upstream(self, asset_id: str) -> list[str]: ...
```

**Tabla SQLite:** `op_lineage`
```sql
CREATE TABLE IF NOT EXISTS op_lineage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT NOT NULL,          -- "COMPLETE" | "START" | "FAIL"
    event_time   TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    job_name     TEXT NOT NULL,
    namespace    TEXT NOT NULL,
    input_ids    TEXT NOT NULL DEFAULT '[]',  -- JSON array
    output_ids   TEXT NOT NULL DEFAULT '[]',  -- JSON array
    metadata     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_op_lineage_run ON op_lineage(run_id);
CREATE INDEX IF NOT EXISTS idx_op_lineage_input ON op_lineage(input_ids);
```

### MemoryStore(Protocol)

```python
class MemoryStore(Protocol):
    def store_conversation(self, conversation: dict) -> None: ...
    def store_incident(self, incident: dict) -> None: ...
    def search(self, query: str, limit: int = 10) -> list[dict]: ...
    def get_by_asset(self, asset_id: str) -> list[dict]: ...
```

**Tabla SQLite:** `op_memory`
```sql
CREATE TABLE IF NOT EXISTS op_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,          -- "conversation" | "incident" | "decision" | "learning"
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    asset_ids   TEXT NOT NULL DEFAULT '[]',  -- JSON array of linked asset IDs
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_op_memory_kind ON op_memory(kind);
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(title, body, tokenize='porter unicode61');
```

### GovernanceStore(Protocol)

```python
class GovernanceStore(Protocol):
    def set_policy(self, policy: dict) -> None: ...
    def check(self, asset_id: str, action: str, actor: str) -> bool: ...
    def get_policies(self, asset_id: str) -> list[dict]: ...
```

**Tabla SQLite:** `op_governance`
```sql
CREATE TABLE IF NOT EXISTS op_governance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT NOT NULL,
    policy      TEXT NOT NULL,    -- JSON: {"action": "compile", "role": "admin"}
    created_at  TEXT NOT NULL,
    actor       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_op_gov_asset ON op_governance(asset_id);
```

---

## 6. EventBus — Mapa completo de eventos

```
compile_source()
  ↓
EventBus.publish(CompileCompleted)
  ├── ArchiveSubscriber      → enqueue_archive_job (existente)
  ├── AuditSubscriber        → get_audit().log_compile (existente)
  ├── MetricsSubscriber      → record_compile (existente)
  ├── AssetIndexSubscriber   → NUEVO: extrae metadatos, indexa en op_assets
  └── OpenLineageSubscriber  → NUEVO: genera evento OpenLineage, persiste en op_lineage

scan_source()
  ↓
EventBus.publish(ScanCompleted)  ← NUEVO evento
  └── AssetIndexSubscriber   → indexa SourceObjects como KnowledgeAssets

search(query)
  ↓
EventBus.publish(SearchPerformed)
  ├── AuditSubscriber (existente)
  └── MetricsSubscriber (existente)

record_feedback()
  ↓
EventBus.publish(FeedbackReceived)  ← NUEVO evento
  └── MemorySubscriber       → NUEVO: registra decisión/learning

archive_source()
  ↓
EventBus.publish(ArchiveCompleted)
  ├── MetricsSubscriber (existente)
  └── AssetIndexSubscriber   → indexa el archive como KnowledgeAsset

notify.send()
  ↓
EventBus.publish(NotificationSent)  ← NUEVO evento
  └── MetricsSubscriber      → registra métricas de notificación

Metadata change detected (extractor)
  ↓
EventBus.publish(MetadataChanged)  ← NUEVO evento
  ├── LineageSubscriber      → actualiza op_lineage
  ├── GovernanceSubscriber   → verifica políticas
  └── NotifySubscriber       → notifica a downstreams
```

**Nuevos eventos a añadir en eventbus.py:**
- `ScanCompleted`
- `FeedbackReceived`
- `NotificationSent`
- `MetadataChanged`

---

## 7. Pipeline rediseñado

### Etapas actuales (sin cambios)

```
snapshot → compile → verify → archive → qdrant → rule_eval
```

### Etapas con Capa 11 (nueva etapa opcional)

```
snapshot → compile → verify → archive → qdrant → rule_eval → metadata_extract
                                                              │
                                                              ↓
                                                       extractores en paralelo
                                                       (ThreadPoolExecutor)
                                                              │
                                              ┌───────────────┼───────────────┐
                                              ▼               ▼               ▼
                                        MarkdownExtr.   GitExtractor     AuditExtractor
                                        (O(1), 0.1s)    (O(n²), 5-30s)  (O(n), 0.5s)
                                              │               │               │
                                              └───────────────┼───────────────┘
                                                              │
                                                              ↓
                                                        EventBus.publish
                                                    (MetadataExtracted)
                                                              │
                                                              ↓
                                                      AssetStore.store()
                                                      LineageStore.store()
```

### Tiempos estimados (por asset)

| Extractor | Tiempo estimado | ¿Bloqueante? |
|---|---|---|
| MarkdownExtractor | <10ms | No (best-effort) |
| CompileExtractor | <5ms | No (best-effort) |
| AuditExtractor | <50ms/doc | No |
| ImageExtractor (sin OCR) | <100ms | No |
| ImageExtractor (con OCR) | 1-5s | No |
| PdfExtractor | 0.5-5s | No |
| OfficeExtractor | 0.1-2s | No |
| AudioExtractor (sin transcript) | <1s | No |
| AudioExtractor (con whisper) | 10-300s | No |
| VideoExtractor (sin transcript) | 1-10s | No |
| VideoExtractor (con whisper) | 30-600s | No |
| GitExtractor (clone shallow) | 5-60s | No |
| GitExtractor (fetch existente) | 1-10s | No |

**Pipeline completo con metadata:** snapshot(0.1s) → compile(1-10s) → verify(0.1s) → archive(0.5s) → qdrant(1-5s) → rules(0.1s) → metadata_extract(0.01-600s dependiendo del asset)

Los extractores lentos (vídeo, audio, Git) se ejecutan en segundo plano y publican eventos cuando terminan. El pipeline principal NO espera por ellos.

---

## 8. Incremental — detección de cambios

```
┌────────────────────────────────────────────────────┐
│                 AssetSource                        │
│  (filesystem path, URL, GitHub API, …)             │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────┐
        │  ¿Ya existe en op_assets?    │
        │  Buscar por content_sha256   │
        └──────────┬──────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
     SHA-256 match       SHA-256 mismatch
     (sin cambios)        (cambiado o nuevo)
        │                     │
        ▼                     ▼
   Saltar (0ms)        ¿mtime + size match?
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
               mtime OK          mtime mismatch
               (mismo hash)      (reprocesar)
                    │                 │
                    ▼                 ▼
               Saltar            Extraer metadatos
                                 │
                                 ▼
                          Almacenar en op_assets
                          Publicar MetadataChanged
```

### Claves de detección

| Método | Coste | Confianza | Uso |
|---|---|---|---|
| SHA-256 del contenido | O(n) lectura completa | 100% | Primer filtro |
| mtime + size | O(1) stat | 99% | Segundo filtro (rápido) |
| fingerprint (hash parcial) | O(1) primeros 4KB | 99.9% | Para archivos remotos |
| Cache de extracciones | O(1) lookup en op_assets | 100% | Evita re-extraer |

---

## 9. Pipeline específico — Vídeo

```
Source: video.mp4 (path, URL, upload)
  │
  ▼
ffprobe (O(1), <1s)
  ├── duration, width, height, fps, bitrate
  ├── video_codec, audio_codec, audio_sample_rate
  └── metadata container (device, date, GPS)
  │
  ▼
ffmpeg thumbnails (O(1), 2-5s)
  ├── thumbnail_1.jpg (10s)
  ├── thumbnail_2.jpg (50%)
  └── thumbnail_3.jpg (90%)
  │
  ▼
Scene detection (O(n), 5-30s)
  └── scene_timestamps, scene_thumbnails
  │
  ▼
OCR (opencv + pytesseract, O(n), 5-60s)
  └── por scene o cada 10s
  │
  ▼
Transcripción (whisper, O(n²), 30-600s)  ← OPCIONAL, background
  ├── language detection
  └── full transcript + timestamps
  │
  ▼
Face/object detection (modelo CV, O(n), 10-60s)  ← OPCIONAL
  ├── detected_faces[]
  └── detected_objects[]
  │
  ▼
Embeddings (O(n), 1-5s)
  └── vector embeddings de scenes/transcript
  │
  ▼
KnowledgeAsset
  ├── metadata técnico (hash, duration, codecs…)
  ├── thumbnails[]
  ├── scenes[]
  ├── transcript (si aplica)
  ├── embeddings[]
  └── quality calculado (confidence del OCR/transcript)
  │
  ▼
AssetStore.store()
LineageStore.store_event()
EventBus.publish(MetadataChanged)
```

### Dependencias

| Herramienta | Obligatorio | Para qué |
|---|---|---|
| `ffprobe` | ✅ | Metadatos técnicos básicos |
| `ffmpeg` | ✅ | Thumbnails, scene detection |
| `Pillow` | ⬜ | Thumbnail processing |
| `opencv-python` | ⬜ | Scene detection, face/object |
| `pytesseract` + `tesseract-ocr` | ⬜ | OCR en frames |
| `openai-whisper` | ⬜ | Transcripción + language detection |
| `onnxruntime` | ⬜ | Modelos de CV (ya instalado para Qdrant) |

Todas las dependencias son opcionales. Si no están, el extractor omite esa etapa y continúa con las siguientes.

---

## 10. Pipeline específico — PDF

```
Source: document.pdf
  │
  ▼
PyMuPDF (fitz)
  ├── metadata: title, author, subject, keywords, creation_date
  ├── page_count
  ├── text: texto completo por página
  ├── has_images, image_count
  └── has_tables, table_count
  │
  ▼
OCR (pytesseract, OPCIONAL)
  └── para páginas sin texto (escaneadas)
  │
  ▼
Embeddings (O(n) por página)
  └── chunking → embedding → Qdrant
  │
  ▼
KnowledgeAsset
  ├── text (full)
  ├── page_count, has_images, has_tables
  ├── author, title, dates
  └── chunks[]
  │
  ▼
AssetStore.store()
```

---

## 11. Pipeline específico — Imagen

```
Source: image.jpg
  │
  ▼
Pillow + EXIF
  ├── width, height, format, mode
  ├── EXIF: GPS, device, date_taken, software, orientation
  └── thumbnail
  │
  ▼
OCR (pytesseract, OPCIONAL)
  └── text detection
  │
  ▼
Object/face detection (OPCIONAL)
  └── detected_objects[], detected_faces[]
  │
  ▼
Embeddings
  └── vector embedding de la imagen
  │
  ▼
KnowledgeAsset
```

---

## 12. Pipeline específico — Office

```
Source: document.docx / spreadsheet.xlsx / presentation.pptx
  │
  ▼
python-docx / openpyxl / pptx
  ├── metadata: title, author, created, modified
  ├── content: paragraphs, tables, sheets, slides
  └── has_images, image_count
  │
  ▼
Embeddings (OPCIONAL)
  └── chunks de texto → embeddings
  │
  ▼
KnowledgeAsset
```

---

## 13. GraphRAG — Diseño (sin implementar)

```
Pregunta del usuario: "¿Debo usar Python 3.12?"
  │
  ▼
GraphRAG.query("Python 3.12", context={"role": "developer"})
  │
  ├── 1. AssetStore.search("Python 3.12", asset_type="API_REFERENCE")
  │     → knowledge_asset: Python 3.12.5
  │       metadata.bugs: [asyncio_deadlock]
  │       metadata.quality: 0.95
  │       wraps: "compile:run_789"
  │
  ├── 2. MemoryStore.get_by_asset("python_3.12.5")
  │     → incident: asyncio_deadlock resolved by upgrade
  │     → conversation: "Our team discussed migrating to 3.12.5"
  │
  ├── 3. LineageStore.get_lineage("python_3.12.5")
  │     → compile_job → official_docs (github)
  │
  ├── 4. Rules → R004 (broken links) result for this asset
  │
  ├── 5. Feedback → avg_rating: 4.5/5 from 12 users
  │
  └── 6. GovernanceStore.check("python_3.12.5", "recommend", "developer")
      → True (approved for use)
  │
  ▼
Context Builder
  └── "Según el Knowledge Graph: Python 3.12.5 (released 2026-07-01) corrige un deadlock
       de asyncio presente en 3.12.0-3.12.4. Validado por 50 tests. Calidad: 0.95.
       Nuestro equipo lo usó para resolver incident_789. Valorado 4.5/5."
  │
  ▼
LLM recibe contexto + pregunta
  └── Responde sin alucinar
```

---

## 14. Compatibilidad — Verificación

| Aspecto | Cómo se preserva |
|---|---|
| **Determinismo** | `KnowledgeAsset` es frozen. No modifica `kg_active_version`. El hash SHA-256 del grafo sigue siendo el mismo. |
| **Schema v12** | Las nuevas tablas son `op_*` (operativas), ninguna `kg_*`. Migración v12→v13 limpia. |
| **API congelada** | `/health`, `/status`, `/search`, `/compile`, etc. no cambian. Solo se añaden `/metadata/*`. |
| **CLI** | `ke compile`, `ke search`, etc. no cambian. Nuevo subcomando `ke metadata`. |
| **Snapshot incremental** | `snapshot_store.py` no se modifica. Los extractores tienen su propia caché (op_assets). |
| **Rollback** | `CompileRollback` no toca `op_assets`. Las escrituras de metadata usan `begin_immediate`. |
| **Archives** | `archiver.py` no cambia. Los archives se indexan como `KnowledgeAsset` aparte. |
| **Connection factory** | Los Stores usan `open_db()` existente. |
| **175 tests existentes** | No se modifican. Se añaden tests nuevos. |

---

## 15. Riesgos

| Riesgo | Impacto | Probabilidad | Mitigación |
|---|---|---|---|
| `ffprobe` no instalado | Bajo — video sin metadatos técnicos | Alta en entornos sin ffmpeg | ✅ Graceful degradation: el extractor omite pasos sin la herramienta |
| whisper muy lento (10min por hora de video) | Medio — pipeline bloqueado | Alta para videos largos | ✅ whisper se ejecuta en background thread, no bloquea el pipeline |
| `op_assets` crece sin límite (millones de assets) | Bajo — consultas lentas | Media (proporcional al uso) | ✅ Índices en SHA-256, asset_type, y particionamiento por fecha |
| Dependencias opcionales no instaladas | Bajo — extractor devuelve menos metadatos | Alta | ✅ Cada extractor documenta qué dependencias necesita y funciona sin ellas |
| Colisión de asset_id entre extractores | Medio — asset sobreescrito | Baja | ✅ asset_id = SHA-256(source.location + asset_type). Se añade sufijo si colisiona |
| Video de 4K 60fps de 2 horas | Alto — CPU/RAM durante extracción | Baja (caso extremo) | ✅ Límite de resolución (4K max), duration max (2h), background timeout 30min |
| Rotura de compatibilidad con Document | Alto — 175 tests fallan | Muy baja | ✅ KnowledgeAsset NO modifica Document. Lo envuelve con `metadata["wraps"]`. |

---

## 16. Roadmap definitivo

### Fase 0 — Modelo de activos (2 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio de aceptación |
|---|---|---|---|---|
| 0.1 `AssetType`, `AssetSource`, `AssetRelationship`, `KnowledgeAsset` | `ontology/internal.py` | `models.py` (import) | 5 | KnowledgeAsset se crea, se serializa a JSON, envuelve Document sin modificarlo |
| 0.2 `Extractor(Protocol)`, `ExtractionResult` | `extractors/__init__.py` | — | 3 | Se puede implementar un MarkdownExtractor que cumpla el Protocol |
| 0.3 Schema.org templates | `ontology/schema_org.py` | — | 3 | software_version() produce JSON-LD válido |
| 0.4 `AssetStore(Protocol)` + `SQLiteAssetStore` | `asset_store.py` | — | 5 | CRUD completo sobre op_assets con SQLite |

### Fase 1 — Markdown + Compile + Audit (2 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio |
|---|---|---|---|---|
| 1.1 `MarkdownExtractor` | `extractors/markdown.py` | — | 3 | Extrae title, tags, relations desde SourceObject |
| 1.2 `CompileExtractor` | `extractors/compile.py` | — | 2 | Indexa CompileCompleted como KnowledgeAsset |
| 1.3 `AuditExtractor` | `extractors/audit.py` | — | 2 | Indexa op_audit como DECISION/INCIDENT |
| 1.4 `AssetIndexSubscriber` | `subscribers.py` (añadir) | `subscribers.py` | 2 | CompileCompleted → asset indexado en op_assets |
| 1.5 Eventos `ScanCompleted`, `MetadataChanged` | — | `eventbus.py` | 1 | Eventos se crean y publican sin error |

### Fase 2 — Lineage + Governance (2 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio |
|---|---|---|---|---|
| 2.1 `LineageStore(Protocol)` + `SQLiteLineageStore` | `lineage_store.py` | — | 5 | OpenLineage events se almacenan y recuperan |
| 2.2 `GovernanceStore(Protocol)` + `SQLiteGovernanceStore` | `governance_store.py` | — | 3 | Policies CRUD, check por asset_id |
| 2.3 `OpenLineageSubscriber` | `subscribers.py` (añadir) | `subscribers.py` | 2 | CompileCompleted → evento OpenLineage persistido |
| 2.4 `ke metadata lineage <asset_id>` | `cli/metadata.py` | `cli/main.py` | 1 | CLI muestra lineage de un asset |
| 2.5 `GET /metadata/lineage/{asset_id}` | — | `api.py` | 1 | API devuelve lineage del asset |

### Fase 3 — Video + Image + PDF (3 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio |
|---|---|---|---|---|
| 3.1 `VideoExtractor` (ffprobe + thumbnails) | `extractors/video.py` | — | 2 | Extrae duration, codecs, resolution. Genera thumbnails (sin ffprobe → degradación graceful) |
| 3.2 `ImageExtractor` (EXIF + OCR) | `extractors/image.py` | — | 2 | Extrae EXIF, dimensiones, OCR opcional |
| 3.3 `PdfExtractor` (texto + metadata) | `extractors/pdf.py` | — | 2 | Extrae texto, páginas, autor, fechas |
| 3.4 Pipeline `metadata_extract` stage | — | `pipeline.py` | 1 | Pipeline ejecuta extractores y publica MetadataChanged |
| 3.5 Migración v12→v13 (5 tablas op_*) | `schemas/migrations/v12_to_v13.sql` | `migrations.py` | 1 | Schema v13 con op_assets, op_lineage, op_memory, op_governance |

### Fase 4 — Audio + Office + Memory (2 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio |
|---|---|---|---|---|
| 4.1 `AudioExtractor` (ffprobe + whisper opcional) | `extractors/audio.py` | — | 1 | Extrae codec, duración, sample_rate. Transcript opcional |
| 4.2 `OfficeExtractor` (DOCX+XLSX+PPTX) | `extractors/office.py` | — | 2 | Extrae texto, tablas, metadatos de documentos Office |
| 4.3 `MemoryStore(Protocol)` + `SQLiteMemoryStore` | `memory_store.py` | — | 3 | Conversaciones e incidents se almacenan y buscan por FTS |
| 4.4 `ke metadata extract`, `ke metadata query` | `cli/metadata.py` | `cli/main.py` | 1 | CLI funcional para extraer y consultar |

### Fase 5 — Adaptadores + integración final (2 días)

| Tarea | Archivos nuevos | Archivos modificados | Tests | Criterio |
|---|---|---|---|---|
| 5.1 `WebExtractor` (HTML → texto + metadata) | `extractors/web.py` | — | 1 | Extrae title, description, text, images de HTML |
| 5.2 Métricas: asset_extractions_total, duration | — | `metrics.py` | 1 | Prometheus exporta métricas de Capa 11 |
| 5.3 FeedbackReceived → MemoryStore | — | `subscribers.py` | 1 | Feedback con rating >3 crea decision en memory |
| 5.4 GraphRAG.query() diseño final | `graphrag.py` (esqueleto) | — | 0 | Definición de interfaz, sin implementación de LLM |

### Total: 13 días hábiles (~3 semanas)

---

## Resumen de archivos

### Nuevos (14 archivos)
```
knowledge/engine/
├── ontology/
│   ├── __init__.py
│   ├── internal.py        # KnowledgeAsset, AssetType, AssetSource, AssetRelationship
│   └── schema_org.py      # SoftwareVersion, BugReport, Person, Dataset templates
├── extractors/
│   ├── __init__.py         # Extractor(Protocol), ExtractionResult, registry
│   ├── markdown.py
│   ├── video.py
│   ├── image.py
│   ├── audio.py
│   ├── pdf.py
│   ├── office.py
│   ├── web.py
│   ├── audit.py
│   └── compile.py
├── asset_store.py          # AssetStore(Protocol) + SQLiteAssetStore
├── lineage_store.py        # LineageStore(Protocol) + SQLiteLineageStore
├── memory_store.py         # MemoryStore(Protocol) + SQLiteMemoryStore
├── governance_store.py     # GovernanceStore(Protocol) + SQLiteGovernanceStore
├── graphrag.py             # Esqueleto: interfaz GraphRAG.query()
└── cli/metadata.py         # CLI commands
```

### Modificados (10 archivos)
```
knowledge/engine/
├── models.py               # Import de ontology
├── eventbus.py             # Nuevos eventos: ScanCompleted, MetadataChanged, FeedbackReceived
├── subscribers.py          # AssetIndexSubscriber, OpenLineageSubscriber
├── pipeline.py             # Stage METADATA_EXTRACT
├── api.py                  # Endpoints /metadata/*
├── cli/main.py             # Subparser "metadata"
├── metrics.py              # Nuevas métricas
├── migrations.py           # SCHEMA_VERSION = 13, MIGRATIONS[13]
├── schemas/migrations/v12_to_v13.sql  # 5 tablas op_*
└── schemas/knowledge_graph.sql        # op_assets, op_lineage, op_memory, op_governance (base)
```

### Sin cambios (archivos del núcleo)
```
compiler.py, reader.py, scanner.py, parser.py, sqlite_writer.py,
orchestrator.py, jobs.py, archiver.py, connection.py, lock.py,
determinism.py, rollback.py, snapshot_store.py, connection_pool.py,
feedback.py, rules.py, deduction.py, knowledge_base.py, notify.py
```

---

*Documento de diseño — Knowledge Engine v0.2.0 — 2026-07-02*
