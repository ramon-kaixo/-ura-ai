# Roadmap post-Fase 4 — Consolidación y escalabilidad

---

## Objetivos estratégicos

| Área | Prioridad | Estado actual | Meta |
|---|---|---|---|
| **GraphRAG** | Inmediata | `SQLiteGraphRetriever` funcional, 0 tests | Añadir `retrieve_neighbors()`, tests de ciclo, benchmark 100K |
| **Extractores reales** | Alta | Solo `MarkdownExtractor` | PDF, video, audio, imagen, Git, web |
| **Backend vectorial** | Alta | Ninguno | ChromaDB / Qdrant como backend opcional |
| **Rendimiento** | Media | Stores sin índices, búsqueda LIKE | Índices GIN, FTS5, optimización de queries |

---

## Fase 4b — Consolidación de GraphRAG (3 días)

### Lo que falta
- `retrieve_neighbors()` no implementado
- Tests de ciclo en grafos de 100K nodos
- Benchmark formal de `build_context()`

### Tareas

| Tarea | Archivos | Dependencias | Tests | Criterio |
|---|---|---|---|---|
| `retrieve_neighbors(asset_id, depth)` | `graphrag.py` | AssetStore, LineageStore | 3 | Vecinos hasta profundidad 3, sin ciclos infinitos |
| Benchmark 100K assets | `tests/bench_graphrag.py` | graphrag.py | — | build_context < 1s con 100K assets |
| Tests de ciclo (A→B→C→A) | `tests/test_graphrag.py` | graphrag.py | 2 | retrieve_neighbors no entra en loop infinito |
| Contexto con assets aislados | `tests/test_graphrag.py` | graphrag.py | 1 | Asset sin relaciones → contexto vacío |

---

## Fase 5 — Extractores reales (2 semanas)

### Prioridad de implementación

| Extractor | Tiempo | Dependencias | Complejidad |
|---|---|---|---|
| **PDF** (`PyMuPDF`) | 2 días | `PyMuPDF` | Baja — extraer texto, páginas, metadatos |
| **Imagen** (`Pillow` + `pytesseract`) | 2 días | `Pillow`, `pytesseract` opcional | Media — EXIF, OCR, thumbnails |
| **Audio** (`ffprobe` + `whisper`) | 3 días | `ffprobe`, `openai-whisper` opcional | Alta — transcript con whisper |
| **Video** (`ffprobe` + `ffmpeg` + `opencv`) | 4 días | `ffprobe`, `ffmpeg`, `opencv-python` opcional | Alta — scenes, thumbnails, OCR |
| **Web** (`httpx` + `bs4`) | 2 días | `httpx`, `beautifulsoup4` | Media — HTML → texto, metadata |
| **Git** (`gitpython` o subprocess) | 2 días | `git` | Media — commits, tags, releases |

### Arquitectura

```
extractors/
├── __init__.py       (Extractor Protocol, registry)
├── base.py           (clase base, helpers comunes)
├── markdown.py       ✅ existente
├── pdf.py            ← NUEVO
├── image.py          ← NUEVO
├── audio.py          ← NUEVO
├── video.py          ← NUEVO
├── web.py            ← NUEVO
├── git.py            ← NUEVO
```

### Reglas
1. Cada extractor tiene `version` SemVer, `supported_mime_types`, `cost`, `dependencies` opcionales
2. Sin dependencia obligatoria: si `PyMuPDF` no está, `PdfExtractor` retorna metadata mínima
3. Todos implementan `Extractor(Protocol)` y se registran automáticamente
4. Sin modificar `compiler.py`, `scanner.py`, `parser.py`

---

## Fase 6 — Backend vectorial opcional (1 semana)

### Objetivo
Permitir que `GraphRetriever.build_context()` use embeddings para mejorar ranking, sin depender de ningún proveedor.

### Arquitectura

```python
class VectorBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def search(self, query_embedding: list[float], limit: int = 10) -> list[str]: ...

class OllamaVectorBackend:
    """Usa Ollama API (nomic-embed-text)."""
    def __init__(self, base_url="http://localhost:11434", model="nomic-embed-text"): ...

class QdrantVectorBackend:
    """Usa Qdrant como vector store."""
    def __init__(self, collection="ura_embeddings", url="http://localhost:6333"): ...
```

### Integración con GraphRAG

```python
class SQLiteGraphRetriever:
    def __init__(self, db_path, vector_backend: VectorBackend | None = None):
        ...
    
    def build_context(self, query, ...):
        if self._vector_backend:
            query_embedding = self._vector_backend.embed([query])[0]
            # Usar embedding para rerankear assets recuperados
            # No reemplazar la recuperación LIKE, solo rerankear
```

### Dependencias

| Backend | Librería | Obligatoria |
|---|---|---|
| `OllamaVectorBackend` | `httpx` (ya instalado) | No |
| `QdrantVectorBackend` | `qdrant-client` (ya instalado) | No |

Ninguna dependencia es obligatoria. Sin backend vectorial → ranking heurístico actual.

---

## Fase 7 — Optimización de rendimiento (1 semana)

### Cuellos de botella actuales

| Operación | Problema | Solución |
|---|---|---|
| `build_context()` con 100K assets | `AssetStore.list_assets` sin filtro escanea toda la tabla | Añadir índice FTS5 en `op_assets.title` |
| `MemoryStore.search()` | `LIKE '%query%'` no usa índice | Añadir índice FTS5 en `op_memory.title, content` |
| `LineageStore.get_lineage()` | `LIKE '%asset_id%'` escanea toda `input_ids`/`output_ids` | Añadir tabla `op_lineage_edges(src, dst, relation)` con índices |
| `SQLiteGraphRetriever` crea stores cada vez | Lazy init repetido en `build_context()` | Cachear stores en `__init__` |

### Índices propuestos

```sql
-- Búsqueda FTS5 en assets
CREATE VIRTUAL TABLE IF NOT EXISTS op_assets_fts USING fts5(title, metadata);

-- Búsqueda FTS5 en memorias
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(title, content);

-- Lineage optimizado
CREATE TABLE IF NOT EXISTS op_lineage_edges (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'depends_on',
    PRIMARY KEY (src, dst)
);
```

### Benchmark targets

| Operación | Actual (100K) | Target |
|---|---|---|
| `build_context("test")` | ~150ms | <50ms |
| `retrieve_assets("test")` | ~100ms | <30ms |
| `retrieve_memory("test")` | ~80ms | <20ms |
| Stores: lazy init overhead | ~15ms primera vez | <1ms |

---

## Resumen de fases

```
Fase 4b — Consolidar GraphRAG       3 días  ← AHORA
Fase 5  — Extractores reales (x6)  10 días
Fase 6  — Backend vectorial          5 días
Fase 7  — Optimización rendimiento   5 días
                                 ─────────
                                 23 días hábiles (~5 semanas)
```

### Sin modificar en ninguna fase

```
compiler.py, scanner.py, parser.py, reader.py, orchestrator.py,
connection.py, lock.py, determinism.py, rollback.py, eventbus.py
```

### 175 tests existentes se mantienen en todas las fases.
