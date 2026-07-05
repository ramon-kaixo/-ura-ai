# Retrieval Methods in URA

URA supports multiple retrieval strategies for finding relevant documents.

## Vector Retrieval

Uses embedding similarity search in Qdrant. The query is embedded using
nomic-embed-text and the nearest document vectors are retrieved.

## FTS5 Lexical Retrieval

Uses SQLite FTS5 full-text search. Good for exact keyword matches
and technical terms. Works well for code and configuration queries.

## Hybrid Retrieval

Combines vector and lexical results using Reciprocal Rank Fusion (RRF).
Configurable RRF k parameter balances between the two modalities.
Available via VectorAugmentedRetriever class.

## Evaluation Metrics

- Recall@k: Proportion of relevant documents in top-k results
- Precision@k: Proportion of top-k results that are relevant
- MRR: Mean Reciprocal Rank of first relevant result
- nDCG: Normalized Discounted Cumulative Gain
- MAP: Mean Average Precision across all queries
