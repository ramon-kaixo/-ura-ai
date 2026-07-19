# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Fase 0: requirements/base.txt, requirements/gpu.txt, requirements/dev.txt
- Fase 1: GitHub Actions CI (lint, typecheck, test, security) + publish
- Fase 2: Repo cleanup (colisión macOS resuelta, .gitignore runtime data)
- Fase 3: Scripts huérfanos archivados (6 → .nervioso/descarte/)

## [0.29.0] — 2026-07-19

### Added
- F29 B1: Observabilidad — ComponentLogger estructurado, HealthAggregator, PlatformMetrics
- F29 B2: Validación técnica — benchmark_f29_b2.py, reporte de throughput/latencia/memoria
- F29 B3: Validación funcional — 5 informes de dominio (jurídico, técnico, código, científico, conversacional)
- F29 B4: Operación — runbook, backup_f26_memory.py, graceful shutdown
- F29 B5: Resiliencia — CircuitBreaker, Backpressure, 7 chaos tests
- F29 B6: Compatibilidad — rolling upgrade + downgrade procedure
- F29 B7: Gobernanza — ownership table, runbooks, SLO targets
- 101 tests nuevos: delivery(42), resilience(29), secrets(15), registry(15)
- deploy/polkit/10-ura.rules — regla polkit para systemctl sin sudo
- F14-F02: MultiAgentRuntime.cancel() ahora acepta workflow_id=None
- F14-F03: EpisodeStore auto-recreate tras SQLite corrupta
- F14-F05: HybridRetriever fallback graceful sin Qdrant
- T06: 0 errores de lint (ruff ALL rules, 2356 → 0)

### Changed
- pyproject.toml: dependencies actualizadas, optional-dependencies reorganizados
- scripts/pro/ → 140 scripts activos (6 huérfanos archivados)

### Fixed
- tests/test_unit.py: sys.exit envuelto en `__name__ == '__main__'`
- knowledge/engine/: 26 `except: pass` auditados como degradación controlada
- docs/architecture.md → docs/architecture_diagram.md (colisión case-sensitive macOS)

## [0.28.3] — 2026-07-19

### Added
- F28.1 Stabilization: 0 bugs críticos, ADRs Approved, tag estable
- P1 fixes: checksum verification, LocalTransport race condition, TraceExporter DropPolicy
- P2 ADR-compliance: ErrorCode(StrEnum), ErrorEnvelope.from_original(), size budgets, compression
- P3 ProtocolEnvelope wrappers: ToolRequest/ToolResult + to_envelope()/from_envelope()
- 6 ADRs Approved: 028-01..06, 028-10

### Changed
- motor/platform/: 8 `except:pass` blocks with logging (T08)
- tests: 71/71 tracing, 67/67 protocol — todos verdes

## [0.27.0] — 2026-07-18

### Added
- Fase 27: Arquitectura de agentes autónomos
- Agent ABCs + models frozen (ADR-027-01/02)
- CapabilityGate con 6 denial codes
- ToolRunner con 20 constraints + backpressure vía Semaphore
- Scheduler: FIFO + aging (priority decay cada 30s) + GracefulShutdown
- Planner: rule-based determinista (sin LLM en hot path)
- AgentOrchestrator: 18 constraints, DI-based
- 109 tests, 0 regresiones

## [0.26.0] — 2026-07-17

### Added
- Fase 26: Memoria Histórica
- Timeline (proyección temporal), Journal (WAL con fsync+checksum), Snapshot (punto de recuperación)
- Health/Readiness/Liveness probes
- Graceful Shutdown con timeout
- Cifrado AES-256-CTR opcional en journal y snapshot
- 10,644 ops/s append, 46,000+ ops/s state_at

## [0.25.0] — 2026-07-16

### Added
- Fase 25: Knowledge Fusion
- ABCs (8), modelos (12), enums, config, registry
- 8 PipelineStage implementations + BaseStage
- Entity Resolution Avanzado: ContextualEntityResolver con desambiguación contextual
- LRU cache, n-gramas, polisemia (Apple, Tesla, Amazon, Washington)

## [0.17.0] — 2026-07-14

### Added
- Fase 17: Configuración Unificada
- UraConfig como vista tipada de CONFIG
- Deprecación de config.local.json
- scripts/pro/audit_config.py con 3 comprobaciones automáticas

## [0.11.0] — 2026-07-10

### Added
- Fase 11: Plataforma — Motor extensible
- EventBus tipado (tópicos, payloads, sync/async)
- Plugin manifest + RegistryV2
- Pipelines dinámicos (engine YAML, etapas base, CLI)
- Observabilidad: /metrics, /health, /ready

## [0.10.0] — 2026-07-08

### Added
- Fase 10: Estabilización
- CI verde, 540 tests, 0 fallos
- DegradedMode, PluginRegistry, Executor
- 67 tests nuevos
- Benchmarks: 0 degradaciones

## [0.0.1] — 2026-05-01

### Added
- Initial project structure
- Multi-agent architecture
- Knowledge Engine foundation
