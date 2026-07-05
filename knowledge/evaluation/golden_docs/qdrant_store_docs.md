# Qdrant Vector Store in URA

URA uses Qdrant as its vector database for semantic search.

## Collections

- `ura_documents`: Main document collection (191 points currently indexed)
- `ura_documents_hybrid`: Hybrid search collection
- `fallos_ura`: Error/failure records
- `historial_total`: Complete history
- `memoria_web`: Web memory
- `perfil_ramon`: User profile vectors

## Configuration

- Host: localhost (port 6333)
- Distance: Cosine similarity
- Embedding dimension: 768 (nomic-embed-text)
- Points are upserted with payload containing: texto, id, source, chunk_index, title

## Query

Search is performed via cosine similarity between query embedding and stored vectors.
Results include payload metadata and similarity score.
