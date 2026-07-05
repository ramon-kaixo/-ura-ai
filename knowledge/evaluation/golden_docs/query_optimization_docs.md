# Query Optimization in URA

Optimizing search queries improves retrieval quality and user experience.

## Query Expansion

Techniques for expanding queries include:
- Adding synonyms from a domain-specific dictionary
- Including related terms from the knowledge graph
- Using LLM-generated related queries

## Chunking Strategy

Document chunking affects retrieval quality:
- Token-based chunking: Fixed window of N tokens with overlap
- Semantic chunking: Split by document structure (headings, paragraphs)
- Chunk size affects both precision and recall

## Score Thresholds

- Scores above 0.7: Highly relevant
- Scores 0.5-0.7: Moderately relevant
- Scores below 0.5: Low relevance, may indicate poor query-doc match
- Threshold for 'no context': < 0.6 on best result

## Performance Optimization

- Embedding cache for frequent queries
- Result caching with configurable TTL
- Batch query processing for throughput
