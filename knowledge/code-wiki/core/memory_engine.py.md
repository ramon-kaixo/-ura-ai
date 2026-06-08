# `core/memory_engine.py`

- **Language:** python
- **Chunks:** 12

## Symbols

### function: `_sha256`
- Line: 33

def _sha256(filepath):
Hash SHA-256 de un archivo (determinista).

### function: `_chunk_text`
- Line: 42

def _chunk_text(text, size, overlap):
Divide texto en chunks con overlap (determinista).

### function: `_chromadb_available`
- Line: 56

def _chromadb_available():
Verifica si chromadb está instalado.

### function: `_get_collection`
- Line: 62

def _get_collection():
Obtiene o crea la colección ChromaDB.

### function: `load_manifest`
- Line: 77

def load_manifest():
Carga el manifest de indexación.

### function: `save_manifest`
- Line: 87

def save_manifest(manifest):
Guarda el manifest (determinista: mismo estado → mismo archivo).

### function: `index_documents`
- Line: 106

def index_documents(force):
Indexa todos los documentos en data/documentos/.
- Archivos nuevos → chunk + embed
- Archivos modificados (SHA-256 ≠) → re-indexa
- Archivos sin cambios → no toca (idempotente)
- Archivos eliminados → borra chunks de ChromaDB
Retorna dict con estadísticas.

### function: `query`
- Line: 203

def query(question, top_k):
Busca los chunks más relevantes para una pregunta.
Retorna lista de {content, source, chunk_index, similarity}.

### function: `get_sources`
- Line: 248

def get_sources(results):
Extrae fuentes únicas de los resultados de query().

### function: `rag_enabled`
- Line: 264

def rag_enabled():
Verifica si RAG está configurado y disponible.

## Module Overview

Memory Engine — RAG (Retrieval-Augmented Generation) para URA.
Indexa documentos locales en ChromaDB y enriquece consultas con contexto.
Determinista: sin variables globales, todo el estado en disco.

## Imports

```
chromadb
contextlib
core.config_manager.CONFIG
datetime.datetime
hashlib
importlib.util
json
logging
pathlib.Path
shutil
sys
```
