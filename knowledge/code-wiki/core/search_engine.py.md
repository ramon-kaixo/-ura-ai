# `core/search_engine.py`

- **Language:** python
- **Chunks:** 3

## Symbols

### function: `search`
- Line: 14

def search(query_str, top_k):
Busca documentos relevantes para una query.

Args:
    query_str: La query de búsqueda
    top_k: Número máximo de resultados a devolver

Returns:
    Lista de diccionarios con resultados {content, source, chunk_index, similarity}

## Module Overview

Search Engine - Búsqueda simple en documentos indexados.

## Imports

```
core.config_manager.CONFIG
core.memory_engine.query
core.memory_engine.rag_enabled
logging
pathlib.Path
typing.Dict
typing.List
```
