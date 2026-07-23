# Changelog

## v0.34.0-alpha.5.4 (2026-07-23)
- A3: Autofix de codigo (ruff fix + format + commit automatico)
- Scheduler-Brain integration: start_scheduler, stop_scheduler, get_scheduler_status
- ProactiveDetector: disk, memory, ollama, git checks (14 tests)
- TuneladoraScheduler: pipelines periodicos (health 5min, cleanup 60min, audit 360min)
- Integracion tests: 10 tests + 18 auto_maintain tests = 134 total
- Ruff + mypy en motor/brain/ → 0 errores

## v0.34.0-alpha.0 → v0.34.0-alpha.5.4 (2026-07-23)
- Brain infrastructure: analyzer, advisor, alerts, observer, executor, auto_maintain
- WebLearningAdapter: crawl + search + summarize via motor.core.web
- Monitorizacion: Prometheus exporter + /metrics endpoint en Prometheus format
- E2E tests: 9 tests de health, metrics, chat
- Auto-cleanup: logs, SQLite vacuum, orphaned embeddings
- Alertas: health, latency, errors, disk (4 patrones)
- Duplicate detection + tech debt report
- HOOKS_STATUS.md, ARCHITECTURE.md, ROADMAP_A2.md
- Pre-commit hooks: 12 hooks, 0 fallos
- Ruff en motor/: 35→0 errores
- mypy en motor/brain/: 0 errores
- 134 tests totales

## v0.33.0 (2026-07-23)
- G1: Prometheus metrics exporter + Grafana
- G2: E2E tests (9 tests) + CI job
- G3: Auto-cleanup logs, SQLite vacuum, embeddings
- G4: Alertas: health, latency, errors, disk
- G5: Duplicate detection + tech debt report + CI
- v0.33.1: shell=True fix, private attrs, E2E skipif
- v0.33.2: 4 ruff errors corregidos

## v0.32.0 (2026-07-23)
- F821 undefined names (3 bugs) corregidos
- Ruff 66→23 (43 auto-fix + noqa)
- SQLite schema documentado (knowledge.db, 17 tablas)
- Module-database mapping documentado
- Tuneladora tests: 11 tests, engine + plugins
- 115 tags obsoletos eliminados
- v0.32.0-alpha.1..4

## v0.31.0 (2026-07-23)
- Tuneladora: PipelineEngine + 5 plugins + ledger + checkpoint
- log.warn() → log.warning() en toda la codebase
- tuneladora_mejora.py main() complejidad 16→5
- _persist_health() except:pass corregido con logging
- api.py partido en 4 modulos (539→448 lineas)
- router.py partido en 5 modulos (535→480 lineas)
- mypy en plugin/: 22→0 errores
- Ruf en tests/: 8→0 errores
- v0.31.0-alpha.1..5

## v0.30.0 (2026-07-23)
- Merge cleanup-v3 → main (17 squashes + 9 working-tree commits)
- motor/platform/ eliminado: 15 archivos muertos, 3 preservados, 4 migrados
- Observabilidad F3: HealthRegistry, LabeledCounter, TraceContext, JSONFormatter
- Docker + docker-compose + systemd service
- CI workflow: tests + lint
- VERSIONING.md, ARCHITECTURE.md, SECURITY_AUDIT.md, DEPLOY.md
- LatencyStats corregido (record, compute_percentiles, to_dict, count, errors)
- v0.30.0-alpha.1..12

## v1.1.0 (2026-07-20)
- Sanitation Roadmap V1.1.0 complete
- Phase B: Circular dependency core↔motor broken (ollama→UraConfig)
- Phase E: 8 ADRs approved, AGENTS.md refs fixed
- Auditoría forense + plan de remediación (80 hallazgos)

## v1.0.0 (2026-07-20)
- Pre-sanitation baseline release

## v0.29.0-fase29 (2026-07-19)
- Production Readiness: observabilidad, validación, operación, resiliencia, compatibilidad, gobernanza
- Post-F29: experiencia, conocimiento, infra, herramientas, CLI, calidad

## v0.28.3-stable (2026-07-19)
- F28.1 Stabilization: race conditions, ADRs finalizados

## v0.25.0-fase25 (2026-07-18)
- Knowledge Fusion: 8 PipelineStage implementations, Entity Resolution

## v0.17.0-fase17
- Configuración Unificada: UraConfig como única fuente de verdad

## v0.16.0-fase16
- Empaquetado y deuda técnica

## v0.15.0-fase15
- Migración HTTP (Ollama)

## v0.14.8-b5
- F14 Robustez: Load & Stress, Resiliencia, E2E, Profiling, RC Audit
