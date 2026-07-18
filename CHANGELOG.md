# Changelog

## [0.28.0] — 2026-07-19 — Fase 28 Platform Protocols

### Added
- F28: ProtocolEnvelope (5 headers), ProtocolValidator, VersionNegotiator, Transport ABC + LocalTransport, ErrorEnvelope
- F28: Observabilidad Distribuida (TraceId/SpanId, TraceExporter, Sampler, MetricsCollector, HealthAggregator, span tree validation)
- F28: RateLimiter (token bucket), payload sanitization (8 blocked patterns), structured JSON logging
- 63 tracing tests, 488 total F25–F28+OBS tests, soak 3288 ops/60s 0 errors

## [0.27.0] — 2026-07-18 — Fase 27 Autonomous Agents

### Added
- F27: CapabilityGate (6 denial codes), ToolRunner (20 constraints, Semaphore backpressure)
- F27: Scheduler (FIFO + aging + GracefulShutdown), Planner (rule-based, no LLM in hot path)
- F27: AgentOrchestrator (18 constraints, DI-based, CapabilityGate integrated)
- 109 tests, 0 regresiones

## [0.26.0] — 2026-07-17 — Fase 26 Historical Memory

### Added
- F26: MemoryTimeline (temporal projection), Journal (WAL with fsync+checksum), Snapshot (recovery point)
- F26: Health/Readiness/Liveness probes, graceful shutdown
- F26: AES-256-CTR optional encryption (PBKDF2, cryptography library)

## [0.25.0] — 2026-07-16 — Fase 25 Knowledge Fusion

### Added
- F25: Pipeline stages (Extraction, Normalization, KnowledgeMerger, MemoryCandidate)
- F25: Entity Resolution (ContextualEntityResolver with LRU cache, n-gramas, polysemy handling)
- F25: FactIndex, FactHistory, bucket-based conflict detection
- F25: Bridge to F26 Memory (MemoryCandidateSelectionStage)

## [0.2.0] — 2026-07-01 — Release Candidate

## [0.2.0] — 2026-07-01 — Release Candidate

### Added
- Fase D: Rule evaluation engine (SafeEval AST, R001-R005)
- Fase D: StateDeductor (coverage, orphan, hub nodes)
- Fase D: RecommendationValidator
- CLI commands: `ke rules list|eval`, `ke deduce`
- Cross-process concurrency test (10 compile + 5 archive, 0 SQLITE_BUSY)
- Stress tests: 5 escenarios (writer/readers, archive, kill, queue, contention)
- Resilience tests: v8→v11 migration, downgrade protection, corruption
- Property tests: 200 random markdowns parsed deterministically
- CI pipeline: `scripts/ci.sh` (ruff, tests, golden-master, property, doctor, audit-db, invariants)
- ADRs: 6 documentos de arquitectura (NDJSON, flock, determinism ABI, WAL, async archive, systemd)
- API documentation: `docs/api/API.md`
- Benchmark baseline: `docs/benchmarks/BASELINE.md`
- Release checklist: `docs/architecture/RELEASE_CHECKLIST.md`
- Invariants: `docs/architecture/INVARIANTS.md` (11 reglas vinculantes)

### Changed
- `cmd_compile` ahora pasa por `request_compile()` con flock (seguridad entre procesos)
- `verify_archive`/`restore_source` aceptan `archive_dir` opcional (path traversal fix)
- `get_audit()` fallback a no-op si `~/.ura/audit/` no es escribible
- Timestamp de archive con microsegundos (colisión entre procesos)
- `determinism_algorithm` ahora se escribe correctamente (compiler delega en determinism.py)
- Schema base incluye `determinism_algorithm` (DBs frescas consistentes)

### Fixed
- `cmd_compile` sin flock → 10 procesos simultáneos causaban SQLITE_BUSY
- Colisión de timestamp entre procesos en archive
- Deadlock de importación en hilos (__init__.py)
- `wal_path.stat()` sin `exists()` en ke audit-db
- frontmatter sin `sort_keys` → hash inestable
- `process_archive_jobs` sin `BEGIN IMMEDIATE` tras cada COMMIT
- `determinism_algorithm` dead code (nunca se escribía en DB)
- 15/15 SafeEval bypasses bloqueados (__class__, __bases__, lambda, etc.)

### Security
- SafeEval: AST whitelist, dunder blocking, límites (depth 10, nodes 100, chars 2048, calls 10)
- path traversal en manifest/archive corregido
- `shell=True` nunca usado
- Dependency: simpleeval reemplazado por AST nativo (0 dependencias externas)

## [0.1.0] — 2026-06-24 — Fase C completa

### Added
- Auditoría NDJSON (read path lock-free)
- Connection factory única (`connection.py`)
- `begin_immediate` para todas las escrituras SQLite
- `compile_lock` context manager con flock
- Determinism hash versionado (sha256-v1)
- Stale recovery para jobs
- Métricas Prometheus (compile, search, archive, audit, queue)

### Changed
- API pública congelada
- ENGINE_VERSION y MIN/MAX_SCHEMA en migrations.py
- CLI commands: `audit-db`, `job-process`

### Fixed
- `verify_archive` path traversal (CRITICAL)
- Conexiones SQLite sin PRAGMAs (10/15 sin WAL)
- Jobs stuck en "running" forever

## [0.0.1] — 2026-06-17 — Fase A + B

### Added
- Knowledge Engine inicial
- Fase A: Archival (git bundle + manifest + restore)
- Fase B: Observabilidad (métricas, logs estructurados, correlation_id)
- 170 tests, stress tests, cross-process tests
