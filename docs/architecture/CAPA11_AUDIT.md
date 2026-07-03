# Auditoría técnica — Diseño de Capa 11

**Objetivo:** Romper la arquitectura antes de escribir código.  
**Método:** Validar cada decisión contra casos reales, buscar duplicidades, cuellos de botella, y dependencias ocultas.  

---

## 1. KnowledgeAsset — Auditoría de duplicidades

### Mapa de campos: ¿quién es el propietario?

| Campo | KnowledgeAsset | Document | SourceObject | ¿Duplicado? | Resolución |
|---|---|---|---|---|---|
| `asset_id` | ✅ Propietario | ❌ No tiene | ❌ No tiene | No | OK |
| `asset_type` | ✅ Propietario | ❌ `doc_type` (string) | ❌ `kind` (string) | **Parcial** | `asset_type` unifica. `Document.doc_type` y `SourceObject.kind` se mantienen para compatibilidad. Al crear un KnowledgeAsset desde Document, se mapea: `doc_type → asset_type` |
| `content_sha256` | ❌ Derivado | ❌ Hereda de SourceObject | ✅ Propietario | **Sí** | `KnowledgeAsset.content_sha256` debe eliminarse. Se obtiene de `SourceObject.content_sha256` o se calcula al extraer. |
| `metadata` | ✅ Propietario | ❌ `frontmatter` (parcial) | ❌ No tiene | No | `metadata` es el JSON-LD enriquecido. `frontmatter` es una fuente de datos, no un duplicado. |
| `source` | ✅ Propietario | ❌ `path` (parcial) | ❌ `path` (parcial) | **Parcial** | `source.location` unifica path/URL/origen. `Document.path` y `SourceObject.path` se mantienen para compatibilidad. |
| `quality` | ✅ Propietario | ❌ `quality` (de parse) | ❌ No tiene | **Parcial** | `Document.quality` es calidad de parseo. `KnowledgeAsset.quality` es metadata + feedback + freshness. El primero alimenta al segundo. No se elimina — se complementan. |
| `relationships` | ✅ Propietario | ❌ No tiene | ❌ No tiene | No | OK |
| `created_at` | ✅ Propietario | ❌ No tiene | ❌ No tiene | No | OK |
| `updated_at` | ✅ Propietario | ❌ `updated_at` (de DB) | ❌ No tiene | **Parcial** | `Document.updated_at` es cuándo se compiló. `KnowledgeAsset.updated_at` es cuándo se extrajeron metadatos. Son distintos — se mantienen ambos. |

### Decisión final

| Campo duplicado | Acción |
|---|---|
| `content_sha256` | ❌ **ELIMINAR** de KnowledgeAsset. Se obtiene de SourceObject. |
| `source.location` | ✅ Mantener. KnowledgeAsset puede venir de fuentes que no son SourceObject (URL, API). |
| `quality` | ✅ Mantener. Son métricas distintas (parse quality vs metadata quality). |
| `updated_at` | ✅ Mantener. Son timestamps distintos. |

### Modelo corregido

```python
@dataclass(frozen=True)
class KnowledgeAsset:
    asset_id: str
    asset_type: AssetType
    metadata: AssetMetadata        # ← content_sha256 va aquí como metadata["content_sha256"] si aplica
    source: AssetSource
    relationships: tuple[AssetRelationship, ...]
    quality: float
    created_at: str
    updated_at: str
    # NO TIENE content_sha256 propio — se obtiene de metadata["content_sha256"]
```

---

## 2. Metadata — Clasificación completa

### Leyenda

| Clase | Símbolo | Cuándo se recalcula |
|---|---|---|
| **Obligatorio** | 🔴 | Siempre que el asset cambie |
| **Calculable** | 🟡 | Bajo demanda (no se almacena, se calcula al consultar) |
| **Volátil** | 🟠 | Cada vez que se accede (freshness, quality score) |
| **Persistente** | 🔵 | Una vez extraído, no cambia |
| **Costoso** | 🟣 | Se extrae una vez y se cachea (OCR, transcript) |
| **Externo** | ⚪ | Viene de API externa (GitHub, licencias) |

### Tabla completa

| Metadata | Clase | Propietario | Se recalcula | Almacenamiento |
|---|---|---|---|---|
| `hash` (SHA-256) | 🔴 Obligatorio | Extractor | Cada cambio de contenido | `metadata["hash"]` |
| `asset_type` | 🔴 Obligatorio | Extractor | Una vez (inmutable) | `KnowledgeAsset.asset_type` |
| `source.location` | 🔴 Obligatorio | Extractor | Una vez (inmutable) | `KnowledgeAsset.source.location` |
| `source.kind` | 🔴 Obligatorio | Extractor | Una vez (inmutable) | `KnowledgeAsset.source.kind` |
| `title` | 🔵 Persistente | Extractors | Solo si cambia el source | `metadata["title"]` |
| `description` | 🔵 Persistente | Extractors | Solo si cambia el source | `metadata["description"]` |
| `author` | 🔵 Persistente | PDF/Office/Image/Git | Solo si cambia el source | `metadata["author"]` |
| `created_at` (source) | 🔵 Persistente | Extractors | Solo si cambia el source | `metadata["source_created_at"]` |
| `duration` (video/audio) | 🔵 Persistente | ffprobe | Solo si cambia el archivo | `metadata["duration"]` |
| `width`, `height` | 🔵 Persistente | ffprobe / Pillow | Solo si cambia el archivo | `metadata["width"]`, `["height"]` |
| `fps`, `bitrate`, `codec` | 🔵 Persistente | ffprobe | Solo si cambia el archivo | `metadata["fps"]`, etc. |
| `page_count` (PDF) | 🔵 Persistente | PyMuPDF | Solo si cambia el archivo | `metadata["page_count"]` |
| `exif` | 🔵 Persistente | Pillow | Solo si cambia la imagen | `metadata["exif"]` |
| `gps_lat`, `gps_lon` | 🔵 Persistente | EXIF | Solo si cambia la imagen | `metadata["gps_lat"]`, etc. |
| `device_make`, `device_model` | 🔵 Persistente | EXIF / ffprobe | Solo si cambia el archivo | `metadata["device_make"]` |
| `text` (full) | 🔵 Persistente | PDF/Office/OCR | Solo si cambia el archivo | `metadata["text"]` (truncado a 100KB, el resto en chunks) |
| `thumbnail_paths` | 🟣 Costoso | ffmpeg / Pillow | Solo si cambia el archivo | `metadata["thumbnails"]` (paths) |
| `scene_count`, `scenes` | 🟣 Costoso | Scene detection | Solo si cambia el video | `metadata["scenes"]` |
| `ocr_text` | 🟣 Costoso | Tesseract | Solo si cambia el archivo | `metadata["ocr_text"]` |
| `transcript` | 🟣 Costoso | whisper | Solo si cambia el audio/video | `metadata["transcript"]` |
| `embeddings` | 🟣 Costoso | Embedding model | Solo si cambia el contenido | `op_assets` no almacena vectores. Referencia a Qdrant point ID. |
| `quality` | 🟠 Volátil | Rules + Feedback | Cada compile / cada feedback | `KnowledgeAsset.quality` |
| `freshness` | 🟠 Volátil | Sistema | Cada consulta | 🟡 Calculable: `now - updated_at` |
| `popularity` | 🟠 Volátil | Sistema | Cada consulta | 🟡 Calculable: `access_count / time_range` |
| `schema.org` JSON-LD | 🔵 Persistente | `ontology/schema_org.py` | Solo si cambia el source | `metadata["jsonld"]` |
| `license` | ⚪ Externo | Usuario / API | Cuando el usuario lo actualiza | `metadata["license"]` (SPDX) |
| `signature` | ⚪ Externo | Verificación externa | Cuando se verifica | `metadata["signature"]` |
| `dependencies` (Git) | 🟣 Costoso | GitExtractor | Cada clone/fetch | `metadata["dependencies"]` |
| `wraps` | 🔵 Persistente | Sistema | Una vez | `KnowledgeAsset.metadata["wraps"]` |

### Campos calculables (NO se almacenan)

| Campo | Fórmula | ¿Dónde se calcula? |
|---|---|---|
| `freshness` | `now - updated_at` | En la query (GraphRAG, API) |
| `popularity` | `access_count / 30d` | En la query |
| `confidence` | `avg(feedback.rating)` | En la query (desde op_feedback_agg) |
| `stale` | `freshness > 90d` | En la query |
| `total_extractions` | `COUNT(op_lineage WHERE output = asset_id)` | En la query |

---

## 3. Pipeline — Simulación completa

### Escenario: `ke pipeline run` con 6 assets

```
Input: [doc.md, doc.pdf, photo.jpg, video.mp4, song.mp3, repo/ (git)]
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1: snapshot (scanner.py)                             │
│                                                              │
│  doc.md     → SourceObject(kind=markdown, content=bytes)     │
│  doc.pdf    → SourceObject(kind=pdf,     content=bytes)     │
│  photo.jpg  → SourceObject(kind=image,  content=bytes)      │
│  video.mp4  → SourceObject(kind=video,  content=bytes)      │
│  song.mp3   → SourceObject(kind=audio,  content=bytes)      │
│  repo/      → NO (no es un archivo individual, es directorio)│
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2: compile (compiler.py)                              │
│                                                              │
│  Solo procesa .md → parser → validator → writer → kg_nodes   │
│  doc.md → Document → kg_nodes, kg_edges                       │
│  PDF, JPG, MP4, MP3 → IGNORADOS (no son .md)                 │
│                                                              │
│  EventBus.publish(CompileCompleted)                           │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 3: verify (verifier.py)                               │
│  STAGE 4: archive (archiver.py)                              │
│  STAGE 5: qdrant (qdrant_sync.py)                            │
│  STAGE 6: rules (rules.py)                                   │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 7: metadata_extract (NUEVO — opcional)                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Pool de extractores (ThreadPoolExecutor, max=3)     │    │
│  │                                                       │    │
│  │  Hilo 1: MarkdownExtractor(doc.md)                   │    │
│  │    ├── SourceObject → KnowledgeAsset                  │    │
│  │    ├── Tiempo: ~5ms                                   │    │
│  │    └── AssetStore.store()                             │    │
│  │                                                       │    │
│  │  Hilo 2: PdfExtractor(doc.pdf)                       │    │
│  │    ├── PyMuPDF → text, pages, author, title           │    │
│  │    ├── OCR opcional (pytesseract)                     │    │
│  │    ├── Tiempo: ~500ms                                 │    │
│  │    └── AssetStore.store()                             │    │
│  │                                                       │    │
│  │  Hilo 3: ImageExtractor(photo.jpg)                   │    │
│  │    ├── Pillow → EXIF, dimensions, thumbnail           │    │
│  │    ├── OCR + embeddings opcionales                    │    │
│  │    ├── Tiempo: ~100ms                                 │    │
│  │    └── AssetStore.store()                             │    │
│  │                                                       │    │
│  │  ── Los 3 terminan ──                                 │    │
│  │                                                       │    │
│  │  Hilo 1: VideoExtractor(video.mp4)                   │    │
│  │    ├── ffprobe → duration, codecs, resolution         │    │
│  │    ├── ffmpeg → thumbnails (~3s)                     │    │
│  │    ├── Scene detection (~5s)                          │    │
│  │    ├── Los pasos lentos van a BACKGROUND QUEUE        │    │
│  │    │   └── OCR, whisper, embeddings                   │    │
│  │    ├── Tiempo síncrono: ~8s                           │    │
│  │    └── AssetStore.store()                             │    │
│  │                                                       │    │
│  │  Hilo 2: AudioExtractor(song.mp3)                    │    │
│  │    ├── ffprobe → duration, codec, bitrate             │    │
│  │    ├── Tiempo: ~500ms                                 │    │
│  │    └── AssetStore.store()                             │    │
│  │                                                       │    │
│  │  Hilo 3: GitExtractor(repo/) — BACKGROUND            │    │
│  │    └── git log, branches, tags (~10s)                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  EventBus.publish(MetadataExtracted)                          │
│  EventBus.publish(OpenLineageEvent)                           │
└──────────────────────────────────────────────────────────────┘
```

### Módulos ejecutados por etapa

| Etapa | Módulos |
|---|---|
| snapshot | `scanner.py` |
| compile | `compiler.py`, `parser.py`, `validator.py`, `sqlite_writer.py` |
| verify | `verifier.py`, `knowledge_verifier.py`, `storage_verifier.py` |
| archive | `archiver.py` |
| qdrant | `qdrant_sync.py` |
| rules | `rules.py` |
| metadata_extract | `extractors/*.py`, `asset_store.py`, `lineage_store.py` |

---

## 4. Coste por extractor

| Extractor | CPU | RAM | IO | Dependencias | Tiempo esperado | Concurrencia |
|---|---|---|---|---|---|---|
| **Markdown** | Bajo | <10MB | Bajo (lectura) | Ninguna | <10ms | Ilimitada |
| **Compile** | Bajo | <10MB | Bajo | Ninguna | <5ms | Ilimitada |
| **Audit** | Bajo | <50MB | Medio (SQL) | Ninguna | <50ms/doc | Ilimitada |
| **Image** (sin OCR) | Bajo | <100MB | Medio (lectura) | Pillow | <100ms | Ilimitada |
| **Image** (con OCR) | Medio | <200MB | Medio | Pillow + pytesseract | 1-5s | 3 hilos máx |
| **PDF** (sin OCR) | Bajo | <200MB | Medio | PyMuPDF | 0.5-2s | 3 hilos máx |
| **PDF** (con OCR) | Medio | <500MB | Medio | PyMuPDF + pytesseract | 2-10s | 1 hilo máx |
| **Office** | Bajo | <200MB | Medio | python-docx / openpyxl / pptx | 0.1-2s | Ilimitada |
| **Audio** (sin whisper) | Bajo | <50MB | Bajo | ffprobe | <1s | Ilimitada |
| **Audio** (con whisper) | **GPU/High CPU** | 1-4GB | Bajo | ffprobe + whisper | 10-300s | 1 hilo máx (GPU) |
| **Video** (sin whisper) | Medio | <500MB | Alto (lectura) | ffprobe + ffmpeg + opencv | 1-10s | 2 hilos máx |
| **Video** (con whisper) | **GPU/High CPU** | 2-8GB | Alto | ffprobe + ffmpeg + opencv + whisper | 30-600s | 1 hilo máx (GPU) |
| **Git** (shallow clone) | Medio | <500MB | Alto (red) | git | 5-30s | 2 hilos máx |
| **Web** | Bajo | <50MB | Alto (red) | httpx + bs4 | 1-5s | 5 hilos máx (respetar robots.txt) |

### Cuellos de botella identificados

1. **whisper (transcripción)**: GPU/mucha RAM, bloquea el hilo. Solución: background job con timeout de 30min.
2. **Scene detection (video)**: CPU intensivo, bloquea el pool. Solución: limitar a 1 video concurrente.
3. **Git clone**: IO de red, variable. Solución: shallow clone (`--depth 1`) por defecto.
4. **Tesseract OCR**: CPU, sin GPU. Solución: limitar a 3 OCR concurrentes.
5. **ffmpeg thumbnails**: IO de disco al leer el video completo. Solución: `-ss` para seek rápido.

### Límites de concurrencia

| Recurso | Límite | Implementación |
|---|---|---|
| OCR (tesseract) | 3 concurrentes | Semáforo global `_OCR_SEM = threading.Semaphore(3)` |
| whisper | 1 concurrente | Semáforo global `_WHISPER_SEM = threading.Semaphore(1)` |
| ffmpeg | 2 concurrentes | Semáforo global `_FFMPEG_SEM = threading.Semaphore(2)` |
| Git clone | 2 concurrentes | Semáforo global `_GIT_SEM = threading.Semaphore(2)` |
| Web fetch | 5 concurrentes | httpx limits (`max_connections=5`) |
| Extractores totales | CPU_COUNT / 2 | `ThreadPoolExecutor(max_workers=max(1, cpu_count()//2))` |

---

## 5. Scheduler — Extracción asíncrona

### Estados

```
PENDING ──► RUNNING ──► COMPLETED
                │
                ├──► FAILED ──► RETRY (max 3) ──► RUNNING
                │                              └──► SKIPPED (si permanente)
                │
                └──► SKIPPED (por timeout, dependencia faltante)
```

### Diseño

```python
@dataclass
class ExtractionJob:
    id: str
    source: AssetSource
    extractor_id: str
    status: JobStatus  # PENDING | RUNNING | FAILED | COMPLETED | RETRY | SKIPPED
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    result: ExtractionResult | None = None
```

### Política de reintentos

| Error | Reintentar? | Espera |
|---|---|---|
| Timeout (extractor > max_duration) | ✅ Sí, hasta 3 veces | 5s, 30s, 120s |
| Dependencia faltante (ffprobe no instalado) | ❌ No, SKIP permanente | — |
| Archivo no encontrado | ❌ No, SKIP | — |
| Error de red transitorio (Git, Web) | ✅ Sí, hasta 3 veces | 10s, 60s, 300s |
| Error de memoria (OOM) | ❌ No, FAILED | — |
| Error de metadata corrupta | ❌ No, SKIP | — |

### Cola de extracción

Los extractores lentos se encolan en una tabla SQLite `op_extraction_queue`:

```sql
CREATE TABLE IF NOT EXISTS op_extraction_queue (
    id              TEXT PRIMARY KEY,
    source_location TEXT NOT NULL,
    asset_type      TEXT NOT NULL,
    extractor_id    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    priority        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT,
    error           TEXT,
    result_asset_id TEXT,
    dependencies_ok INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_op_extraction_status ON op_extraction_queue(status);
```

---

## 6. Cache — Invalidación

### Claves de cache

| Tipo de cache | Clave | Valor | TTL |
|---|---|---|---|
| Extracción completa | `extract:{asset_type}:{sha256}` | `KnowledgeAsset` (JSON) | Hasta que cambie SHA |
| Metadata técnica | `tech:{asset_type}:{sha256}` | `{duration, codecs, ...}` | Hasta que cambie SHA |
| Thumbnails | `thumb:{asset_type}:{sha256}` | paths a archivos | Hasta que cambie SHA |
| OCR | `ocr:{sha256}` | Texto OCR | Hasta que cambie SHA |
| Transcripción | `transcript:{sha256}` | Texto transcrito | Hasta que cambie SHA |
| Embeddings | `embed:{sha256}` | Vector ID en Qdrant | Hasta que cambie SHA |

### Invalidación

```
¿Cambió SHA-256?           → Invalidar TODO (cache completa)
¿Cambió mtime?             → Invalidar metadata técnica (re-extraer rápido)
¿Cambió extractor_version? → Invalidar metadata de ese extractor
¿Cambió model_version?     → Invalidar solo embeddings/OCR/transcript
```

### Almacenamiento

La cache primaria es `op_assets` (misma tabla). Si un asset ya existe con el mismo SHA-256, se devuelve sin re-extraer. La cache secundaria es en disco (`.cache/ura/extractions/{sha256[:2]}/{sha256}.json`).

No se introduce Redis ni memcached — SQLite + filesystem son suficientes para el volumen esperado (miles, no millones de assets por día).

---

## 7. Versionado de extractores

### Esquema

Cada `Extractor` tiene una propiedad `version`:

```python
class MarkdownExtractor:
    version: str = "1.0.0"  # SemVer
```

Al extraer, se almacena `metadata["_extractor_version"]` en el `KnowledgeAsset`.

### ¿Cuándo cambia la versión?

| Cambio | Versión | Efecto |
|---|---|---|
| Bugfix en extracción | `1.0.0 → 1.0.1` | Metadata existente sigue siendo válida |
| Nuevo campo metadata | `1.0.0 → 1.1.0` | Metadata existente se re-extrae si se consulta |
| Cambio en algoritmo de extracción | `1.0.0 → 2.0.0` | Toda metadata existente se invalida y re-extrae |

### Detección de cambio de versión

```python
stored_version = existing_asset.metadata.get("_extractor_version", "0.0.0")
current_version = extractor.version
if current_version != stored_version:
    re_extract = True  # El extractor actual puede producir metadata mejorada
```

---

## 8. Dependencias opcionales — Tabla completa

### Extractor → Librería → Herramienta

| Extractor | Librería Python | Herramienta sistema | Obligatoria | Fallback | Resultado degradado |
|---|---|---|---|---|---|
| Markdown | yaml (built-in) | — | ✅ Sí | — | — |
| Image | Pillow | — | ✅ Sí | — | Sin dimensiones ni EXIF |
| Image | pytesseract | tesseract-ocr | ⬜ No | Sin OCR | Sin texto en imágenes |
| Image | — | — | — | Sin thumbnail | Sin thumbnail |
| PDF | PyMuPDF (fitz) | — | ✅ Sí | — | Sin texto ni metadatos |
| PDF | pytesseract | tesseract-ocr | ⬜ No | Sin OCR | Sin texto en páginas escaneadas |
| Video | — | ffprobe | ✅ Sí | No metadata | `AssetType=VIDEO` sin metadatos técnicos |
| Video | — | ffmpeg | ✅ Sí | No thumbnails | Sin thumbnails ni scenes |
| Video | opencv-python | — | ⬜ No | Sin scene detection | Sin scene_count |
| Video | pytesseract | tesseract-ocr | ⬜ No | Sin OCR | Sin OCR en frames |
| Video | openai-whisper | — | ⬜ No | Sin transcript | Sin transcripción |
| Audio | — | ffprobe | ✅ Sí | No metadata | `AssetType=AUDIO` sin metadatos técnicos |
| Audio | openai-whisper | — | ⬜ No | Sin transcript | Sin transcripción |
| Office (DOCX) | python-docx | — | ✅ Sí | — | Sin texto ni metadatos |
| Office (XLSX) | openpyxl | — | ✅ Sí | — | Sin texto ni metadatos |
| Office (PPTX) | pptx | — | ✅ Sí | — | Sin texto ni metadatos |
| Git | — | git (built-in) | ✅ Sí | — | Sin metadatos Git |
| Web | httpx | — | ✅ Sí | — | Sin contenido web |
| Web | beautifulsoup4 | — | ✅ Sí | — | Sin parseo HTML |
| Cualquiera | embedding model | — | ⬜ No | Sin embeddings | Sin vectores |

### Estrategia de degradación

```python
class VideoExtractor:
    def __init__(self):
        self._has_ffprobe = shutil.which("ffprobe") is not None
        self._has_ffmpeg = shutil.which("ffmpeg") is not None
        self._has_opencv = self._import_optional("cv2")
        self._has_tesseract = self._import_optional("pytesseract")
        self._has_whisper = self._import_optional("whisper")
    
    def extract(self, source):
        result = ExtractionResult(asset_type=AssetType.VIDEO)
        if self._has_ffprobe:
            result.asset.metadata.update(self._extract_technical(source))
        if self._has_ffmpeg:
            result.asset.metadata["thumbnails"] = self._generate_thumbnails(source)
        # ... el extractor siempre produce un resultado, aunque sea mínimo
        return result
```

---

## 9. Base de datos — esquema final

### Resumen de tablas

| Tabla | Propósito | Capa |
|---|---|---|
| `kg_nodes`, `kg_edges`, `kg_active_version` | Grafo de conocimiento | Núcleo (existente) |
| `op_audit`, `op_jobs`, `op_compiler_runs` | Operacional | Núcleo (existente) |
| `op_assets` | KnowledgeAssets | Capa 11 (nueva) |
| `op_lineage` | OpenLineage events | Capa 11 (nueva) |
| `op_memory` | Conversaciones + incidents | Capa 11 (nueva) |
| `op_extraction_queue` | Cola de extracción asíncrona | Capa 11 (nueva) |
| `op_governance` | Políticas + auditoría | Capa 11 (nueva) |

Migración v12→v13: 5 nuevas tablas, todas `op_*`. No se modifican `kg_*` ni `op_*` existentes.

---

## Resumen de correcciones al diseño original

| # | Problema encontrado | Corrección |
|---|---|---|
| 1 | `KnowledgeAsset.content_sha256` duplica `SourceObject.content_sha256` | Eliminado del modelo. Se accede vía `metadata["content_sha256"]`. |
| 2 | Extractores sin versión → no se puede saber qué metadata es de qué versión | Añadido `Extractor.version` + `metadata["_extractor_version"]`. |
| 3 | Sin scheduler para extractores lentos → bloquean compile | Tabla `op_extraction_queue` + background worker + semáforos de concurrencia. |
| 4 | Sin cache de extracciones → re-extraer archivos sin cambios | Cache por SHA-256 + mtime + extractor version. |
| 5 | Dependencias opcionales no documentadas → ffmpeg obligatorio sin saberlo | Tabla completa con fallbacks y degradación. |
| 6 | Concurrencia sin límites → 10 OCR simultáneos saturan CPU | Semáforos: OCR=3, whisper=1, ffmpeg=2, git=2, web=5. |
| 7 | Metadatos volátiles almacenados → freshness obsoleto en 1 hora | freshness, popularity, confidence son calculables (no se almacenan). |
| 8 | Pipeline sin etapa metadata → no se sabe cuándo ejecutar extractores | Stage 7 opcional `metadata_extract` al final del pipeline. |

---

*Documento de auditoría técnica — Knowledge Engine v0.2.0 — 2026-07-02*
