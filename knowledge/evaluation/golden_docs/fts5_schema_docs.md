# FTS5 Schema for URA Knowledge Base

URA uses SQLite FTS5 for full-text search capabilities.

## FTS5 Table Structure

The FTS5 virtual table `kg_nodes_fts` has columns:
- id: Unique identifier
- title: Document title
- body: Document body text
- tags: Comma-separated tags

## Content Table

The FTS5 content table references `kg_nodes` which stores:
- id: TEXT primary key
- type: Node type (doc, chunk, etc.)
- path: Original file path
- content_sha256: Content hash
- frontmatter: YAML frontmatter as JSON
- body: Document body text
- tags: Comma-separated tags
- title: Document title
- metadata: JSON metadata
- embedding_id: Reference to Qdrant vector
