# ÍNDICE MAESTRO URA v0.29.0
*Generado el 2026-07-28 17:02 UTC | Host: gx10-64c3 | Rama: main*

---

## 1. ARQUITECTURA

### Diagrama de componentes
```
ura/
├── core/          # Lógica de dominio (conciencia, valores, Qdrant proxy)
├── motor/         # Motor framework + config (UraConfig fuente de verdad)
├── agents/        # Agentes especializados
├── knowledge/     # Memoria a largo plazo, Knowledge Engine (Fases 0-7)
├── scripts/       # 146+ scripts (tuneladora, deploy, monitoreo, backup)
├── tests/         # 131 ficheros de test, ~2795 tests colectados
├── shared/        # shared/paths.py — fuente canónica de URA_ROOT
├── deploy/        # system_manifest.json + servicios systemd
└── docs/          # Documentación, ADRs, informes de auditoría
```

### APIs expuestas
| Puerto | Servicio | Auth | Propósito |
|--------|----------|------|-----------|
| 4098 | ura-mochila | Bearer (URA_API_KEY) | API principal FastAPI |
| 11435 | model-router | Bearer (OPENCLAW_GATEWAY_TOKEN) | Ruteo de modelos LLM |
| 8003 | ura-assistant | — | Asistente conversacional |
| 5053 | ura-audit-api | — | API de auditoría |
| 9090 | ura-api | — | Remote endpoint (post-crash) |
| 8081 | opencode | Bearer | OpenCode Web UI |
| 11434 | ollama | — | LLM inference server |
| 6333 | qdrant | — | Vector DB |

### Mapa de dependencias
- **core → motor**: mochila_server, _state, heartbeat, agents, memory_engine
- **motor → core**: config, health_monitor, cli, hybrid_memory
- **tests → todo**: tests importan de core/, motor/, scripts/
- **shared/**: shared/paths.py importado por core/agents/constants.py

---

## 2. SPRINTS Y VERSIONES

| Versión | Fecha | Estado | Objetivo |
|---------|-------|--------|----------|
| v0.29.0 | 2026-07-28 | 🟢 Activo | Estabilización + auditoría externa |

**Commit actual:** 452ba9b feat: external_audit.sh con OpenRouter/Claude + fallback Ollama + cron
**Commits totales:** 949
**Último tag:** backup_test_backup_20260728_151856

---

## 3. ESTADO ACTUAL

| Métrica | Valor | Fecha |
|---------|-------|-------|
| Tests pasados | (error) | 2026-07-28 |
| Tests fallidos | (error) | 2026-07-28 |
| Tests skipped | (error) | 2026-07-28 |
| Linting (ruff) |  errores | 2026-07-28 |
| Bandit HIGH | 0 | 2026-07-28 |
| Merge conflicts | 0 | 2026-07-28 |
| Stashes activos | 0 | 2026-07-28 |
| Servicios activos URA | 19 | 2026-07-28 |
| Servicios fallidos | 2 | 2026-07-28 |
| Modelos Ollama | 14 disponibles | 2026-07-28 |

---

## 4. HERRAMIENTAS

### Tuneladora
- Mantenimiento: scripts/pro/tuneladora_mantenimiento.py (ligero 6h, medio 24h, profundo 7d)
- Mejora continua: scripts/pro/tuneladora_mejora.py (v2.3 con checkpoint)
- Pipeline: scripts/pro/tuneladora/pipeline/runner.py (check, fix, gate)
- Auto-fix gate: se ejecuta cada 5 min (ruff + pytest + commit automático)
- Watch daemon: scripts/pro/tuneladora/watch_daemon.sh (inotifywait)
- Preflight: scripts/pro/tuneladora/preflight_system.py (audit sistema vs manifiesto)

### Ollama
- Endpoint: http://localhost:11434
- Modelos disponibles: 14
- Config: OLLAMA_NUM_PARALLEL=1, OLLAMA_KEEP_ALIVE=5m
- GPU: NVIDIA Blackwell (memoria unificada 128GB)

### OpenRouter / IA externa
- Script: scripts/pro/external_audit.sh
- OpenRouter: Claude 3.5 Sonnet (requiere OPENROUTER_API_KEY)
- Fallback: Ollama qwen2.5-coder:14b
- Output: docs/external_audits/YYYYMMDD_HHMM_CLAUDE.md

### Prometheus/Grafana
- Prometheus: http://localhost:9093 (Docker)
- Grafana: http://localhost:3000 (Docker, solo admins)
- Alertas: ura-prometheus con reglas personalizadas

---

## 5. DECISIONES (ADRs)

- [docs/architecture/ADR-001-ndjson-audit.md](docs/architecture/ADR-001-ndjson-audit.md): ADR-001: NDJSON para auditoría del read path
- [docs/architecture/ADR-002-flock-compile-lock.md](docs/architecture/ADR-002-flock-compile-lock.md): ADR-002: flock(2) para exclusión mutua del compile
- [docs/architecture/ADR-003-determinism-abi.md](docs/architecture/ADR-003-determinism-abi.md): ADR-003: Determinism ABI v1
- [docs/architecture/ADR-004-async-archive.md](docs/architecture/ADR-004-async-archive.md): ADR-004: Archive asíncrono (fire-and-forget)
- [docs/architecture/ADR-005-sqlite-wal.md](docs/architecture/ADR-005-sqlite-wal.md): ADR-005: SQLite WAL mode
- [docs/architecture/ADR-006-systemd-timer.md](docs/architecture/ADR-006-systemd-timer.md): ADR-006: systemd timer como consumidor de op_jobs
- [docs/architecture/ADR-007-REGLA_NUCLEO.md](docs/architecture/ADR-007-REGLA_NUCLEO.md): ADR-007: Regla del Núcleo — Excepciones Controladas
- [docs/architecture/ADR-011-01-PLUGIN_API_CONTRACT.md](docs/architecture/ADR-011-01-PLUGIN_API_CONTRACT.md): ADR-011-01: Contrato de API de Plugins
- [docs/architecture/ADR-011-02-EVENTBUS_CONTRACT.md](docs/architecture/ADR-011-02-EVENTBUS_CONTRACT.md): ADR-011-02: EventBus con Contratos Tipados
- [docs/architecture/ADR-011-03-HOOKS_SYSTEM.md](docs/architecture/ADR-011-03-HOOKS_SYSTEM.md): ADR-011-03: Sistema de Hooks Desacoplado del Núcleo
- [docs/architecture/ADR-011-04-PLUGIN_VERSIONING.md](docs/architecture/ADR-011-04-PLUGIN_VERSIONING.md): ADR-011-04: Versionado y Compatibilidad de Plugins
- [docs/architecture/ADR-012-01-QUALITY_CONTRACT.md](docs/architecture/ADR-012-01-QUALITY_CONTRACT.md): ADR-012-01: Contrato de Calidad — Métricas de Recuperación y Razonamiento
- [docs/architecture/ADR-012-02-MEMORY_MODEL.md](docs/architecture/ADR-012-02-MEMORY_MODEL.md): ADR-012-02: Memory Model — Episódica, Semántica, Working, Largo Plazo
- [docs/architecture/ADR-012-03-MEMORY_LIFECYCLE.md](docs/architecture/ADR-012-03-MEMORY_LIFECYCLE.md): ADR-012-03: Memory Lifecycle — Creación, Consolidación, Compresión, Olvido
- [docs/architecture/ADR-013-01-CONSENSUS_PROTOCOL.md](docs/architecture/ADR-013-01-CONSENSUS_PROTOCOL.md): ADR-013-01: Consensus Protocol — Votación Ponderada entre Agentes
- [docs/architecture/ADR-013-02-DEPLOYMENT_OBSERVABILITY.md](docs/architecture/ADR-013-02-DEPLOYMENT_OBSERVABILITY.md): ADR-013-02: Deployment & Observability — Docker, pip, Prometheus, Documentación
- [docs/architecture/ADR-025-02-KNOWLEDGE_IDENTITY.md](docs/architecture/ADR-025-02-KNOWLEDGE_IDENTITY.md): ADR-025-02: Knowledge Identity Model
- [docs/architecture/ADR-025-03-FACT_VERSIONING.md](docs/architecture/ADR-025-03-FACT_VERSIONING.md): ADR-025-03: Fact Versioning Model
- [docs/architecture/ADR-025-04-HASH_IDENTITY_POLICY.md](docs/architecture/ADR-025-04-HASH_IDENTITY_POLICY.md): ADR-025-04: Hash & Identity Policy
- [docs/architecture/ADR-026-01-MEMORY_ARCHITECTURE.md](docs/architecture/ADR-026-01-MEMORY_ARCHITECTURE.md): ADR-026-01: Memoria Histórica — Arquitectura (v2)
- [docs/architecture/ADR-027-01-AGENT_MODEL.md](docs/architecture/ADR-027-01-AGENT_MODEL.md): ADR-027-01: Modelo de Agentes
- [docs/architecture/ADR-028-01-PROTOCOL_ARCHITECTURE.md](docs/architecture/ADR-028-01-PROTOCOL_ARCHITECTURE.md): ADR-028-01: Internal Platform Protocol Architecture (v2)
- [docs/architecture/ADR-028-03-VERSIONING.md](docs/architecture/ADR-028-03-VERSIONING.md): ADR-028-03: Protocol Versioning + Compatibility (merged)
- [docs/architecture/ADR-028-04-SERIALIZATION.md](docs/architecture/ADR-028-04-SERIALIZATION.md): ADR-028-04: Serialization Contract (v2)
- [docs/architecture/ADR-028-05-OBSERVABILITY.md](docs/architecture/ADR-028-05-OBSERVABILITY.md): ADR-028-05: Observability Contract (v2)
- [docs/architecture/ADR-028-06-ERRORS.md](docs/architecture/ADR-028-06-ERRORS.md): ADR-028-06: Error Contract (v2)
- [docs/architecture/ADR-028-07-EVOLUTION.md](docs/architecture/ADR-028-07-EVOLUTION.md): ADR-028-07: Evolution Strategy (v2)
- [docs/architecture/ADR-028-08-SECURITY.md](docs/architecture/ADR-028-08-SECURITY.md): ADR-028-08: Platform Security — Inter-Subsystem Authentication
- [docs/architecture/ADR-028-09-CONFIGURATION.md](docs/architecture/ADR-028-09-CONFIGURATION.md): ADR-028-09: Platform Unified Configuration
- [docs/architecture/ADR-028-10-OBSERVABILITY.md](docs/architecture/ADR-028-10-OBSERVABILITY.md): ADR-028-10: Platform Observability
- [docs/architecture/ADR-028-11-F28.1-STABILIZATION.md](docs/architecture/ADR-028-11-F28.1-STABILIZATION.md): ADR-028-11: F28.1 Stabilization — Cierre Definitivo de F28
- [docs/architecture/ADR-029-01-OBSERVABILITY.md](docs/architecture/ADR-029-01-OBSERVABILITY.md): ADR-029-01: Observabilidad de Plataforma
- [docs/architecture/ADR-029-02-VALIDATION.md](docs/architecture/ADR-029-02-VALIDATION.md): ADR-029-02: Validación — Técnica y Funcional
- [docs/architecture/ADR-029-03-OPS.md](docs/architecture/ADR-029-03-OPS.md): ADR-029-03: Operación
- [docs/architecture/ADR-029-04-RESILIENCE.md](docs/architecture/ADR-029-04-RESILIENCE.md): ADR-029-04: Resiliencia
- [docs/architecture/ADR-029-05-COMPAT.md](docs/architecture/ADR-029-05-COMPAT.md): ADR-029-05: Compatibilidad y Evolución
- [docs/architecture/ADR-029-06-GOVERNANCE.md](docs/architecture/ADR-029-06-GOVERNANCE.md): ADR-029-06: Gobernanza
- [docs/architecture/ADR-030-INFRAESTRUCTURA_CONGELADA.md](docs/architecture/ADR-030-INFRAESTRUCTURA_CONGELADA.md): ADR-030: Infraestructura Congelada en v2.3
- [docs/architecture/ADR-031-EVOLUCION_CODIGO.md](docs/architecture/ADR-031-EVOLUCION_CODIGO.md): ADR-031: Evolución del Código — Reuso, Calidad y Consolidación

---

## 6. HISTORIAL DE CAMBIOS

| Fecha | Commit | Qué se hizo | Por qué | Quién validó |
|-------|--------|-------------|--------|-------------|
| 2026-07-28 | 452ba9b | feat: external_audit.sh con OpenRouter/Claude + fallback Ollama + cron | |
| 2026-07-28 | da1ceda | fix: deadlock en vector_memory.py:46 — _embed() fuera del lock | |
| 2026-07-28 | 06125bc | fix: ~20 tests pre-existentes rotos — todos arreglados | |
| 2026-07-28 | 8dfc6e5 | fix: ultimo merge conflict en model_router.py eliminado | |
| 2026-07-28 | 12e06c6 | fix: ura_maintenance.py restaurado de commit limpio (auto-fix lo revirtio) | |
| 2026-07-28 | 66f92e4 | fix: merge conflicts reintroducidos por auto-fix gate — resueltos desde commit limpio | |
| 2026-07-28 | 581007e | fix: 454 tests pass, 0 fail — todos los PluginBase + models + merge conflicts | |
| 2026-07-28 | ce260f6 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-28 | e6c0ad5 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-28 | db95e29 | fix: 260 tests pass, 0 fail — plugins, auth, audit | |
| 2026-07-28 | e74c33a | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-27 | 1e90b7c | fix: test_audit_api — 3 tests reparados (very_long, surrogates, cid) | |
| 2026-07-27 | b0b8f5b | cleanup: barrido final — tests 90/0, ruff 37 cosmeticos, bandit 0 HIGH | |
| 2026-07-27 | a8a24ed | fix: FASE 4 arquitectura — shared/paths.py, sys.exit, URA_ROOT centralizado | |
| 2026-07-27 | 54ff2ec | fix: FASE 1-3 del plan de recuperacion | |
| 2026-07-27 | 1bdf52d | fix: merge conflicts + strategy.py call_with_retry signature | |
| 2026-07-27 | f263a20 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-27 | c11476c | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-27 | 8330c6e | docs: auditoria completa URA + recovery scripts — 14 fases, fixes criticos aplicados | |
| 2026-07-27 | aba5c07 | fix: 4 pendientes auditoria — model-router auth, openclaw key, contraste partof, sudoers recovery | |
| 2026-07-27 | 86d6834 | fix: openclaw restart-loop documentado en manifiesto | |
| 2026-07-27 | bee3b8c | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-27 | 6247b28 | fix: audit findings — timers/openclaw en manifiesto, secrets 600, model-router user eliminado | |
| 2026-07-26 | 49fba89 | docs: flujo Mac→Asus verificado — pipeline 6.5s, auth OK | |
| 2026-07-26 | ef0d297 | docs: config map audit — duplicacion URA_ROOT, RUTAS_CONFIG, CONFIG_PATH | |
| 2026-07-26 | 48f6f97 | fix: preflight integrado en tuneladoras + 31 tests | |
| 2026-07-26 | eb2cee9 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | 6134107 | docs: god modules audit | |
| 2026-07-26 | 6a70ce5 | fix: preflight filtro efimeros, heartbeat con auth, manifest completo, open-webui auth | |
| 2026-07-26 | 6d0e66b | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | 2654669 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | f2e2eb7 | fix: manifesto completo con maintenance, fallback, router-user eliminado | |
| 2026-07-26 | 1b253f8 | fix: eliminar router-health fantasma + limpiar build/ + docker en manifesto | |
| 2026-07-26 | 1c1f053 | feat: System Manifest + Pre-flight Check | |
| 2026-07-26 | 786d608 | fix: add Bearer token to watch_inbox Mochila client (auth F1.1) | |
| 2026-07-26 | b227a95 | fix: add Bearer token header to Mochila HTTP client (auth F1.1) | |
| 2026-07-26 | bcb98ba | docs: infrastructure index | |
| 2026-07-26 | e3aa712 | fix: eliminar model-router user duplicado + ura-router-health conflictivo; infra documentada | |
| 2026-07-26 | 2cc00d7 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | 5b30ec5 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | fd61429 | chore: ignore SQLite WAL files (knowledge.db-shm, knowledge.db-wal) | |
| 2026-07-26 | 6f608ff | fix: recover from stash conflict corruption - restore 69 files from 775311b + security hotfixes | |
| 2026-07-26 | 47eac14 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | a199b5f | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | 26ea7cc | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | ecb76e0 | fix: watch_daemon_poll (Samba-compatible) + Sofia prompt injection + commit em dash | |
| 2026-07-26 | e9cb7b0 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-26 | a5c26c4 | tuneladora: auto-fix gate - 1 file(s) | |
| 2026-07-25 | 68c0220 | tuneladora: auto-fix gate — 1 file(s) | |
| 2026-07-25 | fbe240d | tuneladora: auto-fix gate — 1 file(s) | |

---

## 7. PENDIENTES Y DEUDA TÉCNICA

### Tests rotos pre-existentes
- test_audit_message_store: 3 fallos (RuntimeError vs sqlite3) — ARREGLADOS ✅
- test_ci_cd: 7 fallos (YAML + extras) — ARREGLADOS ✅
- test_documentation: 1 fallo (ADR desactualizado) — ARREGLADOS ✅
- test_integration_f10/f11: 8 fallos (PluginBase) — ARREGLADOS ✅
- test_observability_f11: 1 fallo (PluginBase) — ARREGLADOS ✅
- test_openclaw: 2 fallos (runbook structure) — ARREGLADOS ✅

### Linting pendiente
- Ruff:  errores (mayoría EXE002 cosmético)
- Bandit HIGH: {bandit_high}

### Refactor planeado
- Deadlock vector_memory.py — ARREGLADO ✅
- Import circular core↔motor (9 archivos) — pendiente
- sys.exit() en librerías core/ — pendiente (1 migrado a RuntimeError)
- shared/paths.py como fuente canónica URA_ROOT — ARRANCADO ✅
- Auto-fix gate reintroduce merge conflicts — mitigado (stashes eliminados)

---
*Última actualización: 2026-07-28 17:02 UTC*
