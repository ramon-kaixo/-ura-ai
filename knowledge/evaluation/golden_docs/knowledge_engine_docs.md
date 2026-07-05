# URA Knowledge Engine Overview

The Knowledge Engine (KE) is URA's document indexing and retrieval system.

## Architecture

The KE has multiple components:
- `knowledge/engine/reader.py`: KnowledgeReader for searching indexed documents
- `knowledge/engine/compiler.py`: Coordinates scanning, parsing, validation, writing
- `knowledge/engine/chunker.py`: Chunks documents into manageable pieces
- `knowledge/engine/vector_qdrant.py`: Qdrant vector store integration
- `knowledge/engine/vector_ollama.py`: Ollama embedding generation
- `knowledge/engine/vector_retriever.py`: VectorAugmentedRetriever for hybrid search

## Data Flow

1. Documents are scanned from source directories
2. Parsed into structured KnowledgeAsset objects
3. Chunked by tokens (KE 1.x) or semantic boundaries (KE 2.0)
4. Embedded using nomic-embed-text via Ollama
5. Stored in Qdrant vector database
6. FTS5 index in SQLite for lexical search
