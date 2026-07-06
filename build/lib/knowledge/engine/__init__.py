"""Knowledge Engine — URA Knowledge Operating System.

Módulos:
  models.py            — Domain models (contratos internos, frozen)
  errors.py            — Error codes KE0xx, KE1xx, KE2xx
  scanner.py           — Source discoverer + Snapshot logic
  storage_verifier.py  — Storage layer checks (PRAGMA, FTS, schema)
  knowledge_verifier.py— Knowledge consistency checks (edges, cycles, hashes...)
  verifier.py          — Facade que combina storage + knowledge verifiers
  compiler.py          — Coordinator: scanner → parser → validator → writer
  sqlite_writer.py     — Persistence layer (Nunca parsea, nunca valida)
  collector.py         — File system watcher + job queue (post-Fase C)
  reader.py            — KnowledgeReader (post-Fase C)
  archiver.py          — Source archival (git bundle) + verify + restore
  metrics.py           — Prometheus metrics (in-memory + SQLite-derived)
  logging_config.py    — Structured logs (JSON) + correlation_id propagation
  cli.py               — CLI entry point (thin: parse args → call service → output)
"""

from knowledge.engine.agent import Agent as Agent
from knowledge.engine.agent import KnowledgeGraphAgent as KnowledgeGraphAgent
from knowledge.engine.archiver import archive_source as archive_source
from knowledge.engine.archiver import list_archives as list_archives
from knowledge.engine.archiver import restore_source as restore_source
from knowledge.engine.archiver import verify_archive as verify_archive
from knowledge.engine.audit import AuditService as AuditService
from knowledge.engine.audit import NDJSONAuditBackend as NDJSONAuditBackend
from knowledge.engine.audit import SQLiteAuditBackend as SQLiteAuditBackend
from knowledge.engine.audit import get_audit as get_audit
from knowledge.engine.audit import set_audit as set_audit
from knowledge.engine.compiler import compile_source as compile_source
from knowledge.engine.deduction import StateDeductor as StateDeductor
from knowledge.engine.determinism import (
    get_determinism_algorithm as get_determinism_algorithm,
)
from knowledge.engine.determinism import (
    get_determinism_hash as get_determinism_hash,
)
from knowledge.engine.determinism import (
    record_determinism_hash as record_determinism_hash,
)
from knowledge.engine.errors import ErrorCode as ErrorCode
from knowledge.engine.errors import Severity as Severity
from knowledge.engine.errors import all_codes as all_codes
from knowledge.engine.errors import lookup as lookup
from knowledge.engine.logging_config import set_correlation_id as set_correlation_id
from knowledge.engine.logging_config import setup_logging as setup_logging
from knowledge.engine.metrics import export_metrics as export_metrics
from knowledge.engine.metrics import record_archive as record_archive
from knowledge.engine.metrics import record_compile as record_compile
from knowledge.engine.metrics import record_error as record_error
from knowledge.engine.metrics import record_qdrant_sync as record_qdrant_sync
from knowledge.engine.metrics import record_search as record_search
from knowledge.engine.models import (
    ArchiveManifest as ArchiveManifest,
)
from knowledge.engine.models import (
    CompileContext as CompileContext,
)
from knowledge.engine.models import (
    CompileError as CompileError,
)
from knowledge.engine.models import (
    CompileFeatures as CompileFeatures,
)
from knowledge.engine.models import (
    CompileResult as CompileResult,
)
from knowledge.engine.models import (
    Document as Document,
)
from knowledge.engine.models import (
    Frontmatter as Frontmatter,
)
from knowledge.engine.models import (
    GraphEdge as GraphEdge,
)
from knowledge.engine.models import (
    GraphNode as GraphNode,
)
from knowledge.engine.models import (
    KnowledgeObject as KnowledgeObject,
)
from knowledge.engine.models import (
    Relation as Relation,
)
from knowledge.engine.models import (
    SearchResult as SearchResult,
)
from knowledge.engine.models import (
    Snapshot as Snapshot,
)
from knowledge.engine.models import (
    SourceObject as SourceObject,
)
from knowledge.engine.models import (
    ValidationResult as ValidationResult,
)
from knowledge.engine.orchestrator import request_compile as request_compile
from knowledge.engine.parser import parse_source as parse_source
from knowledge.engine.pipeline import Pipeline as Pipeline
from knowledge.engine.reader import KnowledgeReader as KnowledgeReader
from knowledge.engine.recommendation import (
    Recommendation as Recommendation,
)
from knowledge.engine.recommendation import (
    RecommendationValidator as RecommendationValidator,
)
from knowledge.engine.rules import Rule as Rule
from knowledge.engine.rules import RuleEvaluator as RuleEvaluator
from knowledge.engine.rules import safe_eval as safe_eval
from knowledge.engine.scanner import scan_incremental as scan_incremental
from knowledge.engine.scanner import scan_source as scan_source
from knowledge.engine.scanner import take_snapshot as take_snapshot
from knowledge.engine.validator import VALID_DOC_TYPES as VALID_DOC_TYPES
from knowledge.engine.validator import validate_batch as validate_batch
from knowledge.engine.validator import validate_knowledge_object as validate_knowledge_object
from knowledge.engine.vector_base import Embedder as Embedder
from knowledge.engine.vector_base import VectorItem as VectorItem
from knowledge.engine.vector_base import VectorResult as VectorResult
from knowledge.engine.vector_base import VectorStore as VectorStore
from knowledge.engine.vector_ollama import OllamaEmbedder as OllamaEmbedder
from knowledge.engine.vector_qdrant import QdrantVectorStore as QdrantVectorStore
from knowledge.engine.vector_retriever import (
    VectorAugmentedRetriever as VectorAugmentedRetriever,
)
from knowledge.engine.verifier import verify_graph as verify_graph
