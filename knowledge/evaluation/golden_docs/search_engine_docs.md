# URA Search Engine

URA provides multiple search modes through the KnowledgeReader.

## Lexical Search

Full-text search via the FTS5 index in SQLite.
Uses SQLite FTS5 MATCH syntax with stemmed tokens.
Returns results ordered by relevance score.

## Semantic Search

Vector similarity search via Qdrant.
Query is embedded using nomic-embed-text via Ollama.
Returns results ordered by cosine similarity.

## Hybrid Search

Combines lexical and semantic results using Reciprocal Rank Fusion (RRF).
Configured via `VectorAugmentedRetriever` with configurable RRF k parameter.

## Retrieval Modes

- `mode='lexical'`: FTS5 only
- `mode='semantic'`: Qdrant only (when available)
- `mode='hybrid'`: Both (when both indices available)
