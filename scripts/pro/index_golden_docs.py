#!/usr/bin/env python3
"""Create and index golden documents for KE evaluation corpus.
Run once to populate Qdrant with the 12 reference documents."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
log = logging.getLogger("index_golden")

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"
CORPUS_DIR = DOCS_DIR.parent / "corpus"

GOLDEN_DOCS: dict[str, str] = {
    "system_services_docs": """# URA System Services

URA runs multiple systemd services on the GX10 NVIDIA GB10 hardware.

## Core Services

- `ollama` (port 11434): LLM inference server, systemd base, 2 parallel requests, keep-alive 1m
- `ura-openclaw` (port 18789): Gateway MCP, hardening with CPUQuota=40%, MemoryMax=2G
- `opencode` (port 8081): OpenCode server for AI-assisted development
- `ura-executor` (port 4096): URA Executor API (renamed from opencode-executor)
- `model-router` (port 11435): URA Model Router Enhanced, cache 5min, Connection: close

## User Services

- `model-router`: Enhanced routing with caching
- `backend@codestral-22b`: llama.cpp backend for codestral-22b
- `backend@qwen2.5-coder-32b`: llama.cpp backend for qwen2.5-coder-32b

## Monitoring Services

- `ura-audit-api`: FastAPI for audit logging
- `ura-contraste` (port 8002): Proxy de Contraste + Telemetria POS
- `ura-detector`: YOLOv8 Detector + ByteTrack + Behavior Analysis

All services are managed by systemd with automatic restart policies.""",

    "ura_config_reference": """# URA Configuration Reference

The `UraConfig` class in `motor/core/config.py` is the single source of truth for configuration.

## Key Fields

- `deploy_dir`: Deployment directory (default: deploy/)
- `data_dir`: Data directory for runtime files (default: motor/data/)
- `log_level`: Logging level (default: INFO)
- `qdrant_host`: Qdrant host (default: localhost)
- `qdrant_port`: Qdrant port (default: 6333)
- `knowledge_db`: Path to knowledge SQLite database

## Configuration Loading

Configuration is loaded from a JSON file specified via --config flag.
Default config lives in deploy/system_config.json.

## Environment Variables

- `URA_STATE_DIR`: Override state directory
- `URA_LOGS_DIR`: Override logs directory
- `URA_DATA_DIR`: Override data directory
- `MOCHILA_COST_FILE`: Cost tracker file path
- `MOCHILA_HEALTH_FILE`: Provider health file path""",

    "systemd_service_guide": """# Systemd Service Management for URA

URA uses systemd for service lifecycle management on the GX10.

## Service Files

Service files are located in:
- System services: `/etc/systemd/system/`
- User services: `/etc/systemd/user/`

## Key Configuration

- `Restart=on-failure` with `RestartSec=10` for resilience
- `TimeoutStartSec=180` for models with long cold-boot times
- `CPUQuota=40%` for CPU-bound services
- `MemoryHigh` and `MemoryMax` limits for memory protection

## Timer Services

- `tuneladora.timer`: Runs every 6 hours for continuous improvement pipeline

## Health Checks

Systemd service health is monitored via:
- `systemctl is-active <service>`
- `systemctl show <service> -p MainPID`
- Custom health scripts in scripts/pro/""",

    "test_patterns_guide": """# URA Test Patterns Guide

Tests in URA follow specific patterns for different components.

## Component Tests

- EventBus: tests/test_event_bus_f11.py — publish, subscribe, pattern, async
- PluginRegistry: tests/test_registry_v2.py — discover, load, dependencies
- Pipeline: tests/test_pipeline_mvp.py — execution, rollback, hooks
- Observability: tests/test_observability_f11.py — metrics, health, readiness

## Test Conventions

- Use `tmp_path` fixture for temporary files
- Use `pytest.mark.asyncio` for async tests
- No `skip`, `xfail`, or disabled tests
- Private member access in tests: add `# ruff: noqa: SLF001` at file level
- Test file naming: test_<component>.py""",

    "pytest_configuration": """# Pytest Configuration for URA

URA uses pytest 9.0.3 with specific configuration.

## Running Tests

Run all tests: `pytest -q --tb=line`
With coverage: `pytest --cov=motor.core.state --cov=motor.plugin`

## Excluded Tests

Some tests are excluded from the default run:
- test_unit.py: triggers sys.exit(78) from model_router import
- test_openclaw.py: syntax error in except block
- test_vram_guard.py: imports model_router
- test_sda.py: imports guardian_logger.py (syntax error)
- test_snc_anomalias.py: missing scanner dependency

## Dependencies

- pytest 9.0.3
- pytest-asyncio 1.4.0
- pytest-timeout
- hypothesis 6.153.2""",

    "mock_plugin_fixtures": """# Mock Plugins for Testing

Creating mock plugins for tests follows a standard pattern.

## Basic Mock Plugin

```python
class _SimplePlugin(PluginBase):
    def __init__(self, name: str = "simple"):
        super().__init__()
        self.manifest = PluginManifest(name=name, version="1.0.0")
        self.executed = False
    
    def execute(self, context=None):
        self.executed = True
        return {"result": "ok"}
```

## Mock with Hooks

```python
class _HookablePlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.manifest = PluginManifest(
            name="hookable", hooks=["pre_ingest"]
        )
    
    def execute(self, context=None):
        return {}
    
    def on_pre_ingest(self, event):
        return event
```

## Failing Mock

```python
class _FailingPlugin(PluginBase):
    def execute(self, context=None):
        raise RuntimeError("intentional failure")
```

## Cancelling Mock

```python
class _CancellingPlugin(PluginBase):
    def on_pre_ingest(self, event):
        return None  # cancels the operation
```""",

    "knowledge_engine_docs": """# URA Knowledge Engine Overview

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
6. FTS5 index in SQLite for lexical search""",

    "fts5_schema_docs": """# FTS5 Schema for URA Knowledge Base

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
- embedding_id: Reference to Qdrant vector""",

    "qdrant_store_docs": """# Qdrant Vector Store in URA

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
Results include payload metadata and similarity score.""",

    "search_engine_docs": """# URA Search Engine

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
- `mode='hybrid'`: Both (when both indices available)""",

    "retrieval_methods_guide": """# Retrieval Methods in URA

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
- MAP: Mean Average Precision across all queries""",

    "query_optimization_docs": """# Query Optimization in URA

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
- Batch query processing for throughput""",
}


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for doc_id, content in GOLDEN_DOCS.items():
        path = DOCS_DIR / f"{doc_id}.md"
        path.write_text(content.strip() + "\n")
        log.info("Created: %s", path.name)

    log.info("===== Indexing golden docs into KE =====")

    try:
        from motor.core.config import UraConfig
        from motor.core.qdrant_client import QdrantClient
    except ImportError as e:
        log.error("Import error: %s — cannot index", e)
        return 1

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available — cannot index")
        return 1

    total_chunks = 0
    for doc_id, content in GOLDEN_DOCS.items():
        metadata = {
            "id": doc_id,
            "source": doc_id,
            "title": doc_id.replace("_", " ").title(),
            "doc_type": "evaluation",
        }
        ok = qc.guardar_documento(doc_id, content.strip(), metadata=metadata)
        if ok:
            total_chunks += 1
            log.info("Indexed: %s", doc_id)
        else:
            log.error("Failed to index: %s", doc_id)

    log.info("Indexed %d golden docs", total_chunks)

    # Validate
    log.info("===== Validating index =====")
    found = 0
    for doc_id in GOLDEN_DOCS:
        results = qc.buscar_documentos(doc_id.replace("_", " "), limit=1)
        if results:
            found += 1
            log.info("  %s: FOUND (score=%.4f)", doc_id, results[0].get("score", 0))
        else:
            log.warning("  %s: NOT FOUND", doc_id)

    log.info("Coverage: %d/%d = %.1f%%", found, len(GOLDEN_DOCS), found / len(GOLDEN_DOCS) * 100)
    if found < 12:
        log.warning("Some golden docs not indexed — corpus validation may fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
