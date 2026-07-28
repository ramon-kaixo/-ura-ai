# ÍNDICE MAESTRO URA v0.33.2
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
| v0.33.2 | 2026-07-28 | 🟢 Activo | Estabilización + auditoría externa |

**Commit actual:** d04d414 feat: FASES 1-4 completadas — indice, auditoria multi-LLM, ADRs, recuperacion
**Commits totales:** 949
**Último tag:** backup_test_backup_20260728_151856

---

## 3. ESTADO ACTUAL

| Métrica | Valor | Fecha |
|---------|-------|-------|
| Tests pasados (subset fijo) | 565 | 2026-07-28 |
| Tests fallidos (subset fijo) | 0 | 2026-07-28 |
| Tests skipped (subset fijo) | 5 | 2026-07-28 |
| Linting (ruff) | 37 errores (cosméticos) | 2026-07-28 |
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

| Fecha | Commit | Qué se hizo | Tests antes/después | Quién validó |
|-------|--------|-------------|---------------------|-------------|
| 2026-07-28 | d04d414 | feat: FASES 1-4 completadas — indice, auditoria multi-LLM, ADRs, recuperacion | 565/0/5 | AI agent |
| 2026-07-28 | 452ba9b | feat: external_audit.sh con OpenRouter/Claude + fallback Ollama + cron | — | AI agent |
| 2026-07-28 | da1ceda | fix: deadlock en vector_memory.py:46 — _embed() fuera del lock | — | AI agent |
| 2026-07-28 | 06125bc | fix: ~20 tests pre-existentes rotos — todos arreglados | — | AI agent |
| 2026-07-28 | 8dfc6e5 | fix: ultimo merge conflict en model_router.py eliminado | — | AI agent |

---

## 7. PENDIENTES Y DEUDA TÉCNICA

### Tests rotos pre-existentes
- **test_audit_conversation.py**: ~12 fallos intermitentes + deadlock (hangs sin -x). Causa: race condition en manejo de sesiones SQLite con hilos concurrentes. No se ha corregido para no modificar features (ADR-007).
- **Suite completo (`pytest tests/`)**: se cuelga. No completa en <10 min por 4 causas: (1) deadlock test_audit_conversation.py, (2) test_knowledge_engine.py masivo (2621 líneas), (3) test_llm_bridge.py necesita model-router, (4) tests integración pesados.
- **vector_memory.py deadlock**: ARREGLADO ✅ en commit da1ceda (_embed() fuera del lock). El suite completo se cuelga si se ejecuta test_audit_conversation.py ANTES que los tests de vector_memory.
- **model-router caído**: systemd exit 78 (falta OPENCLAW_GATEWAY_TOKEN en entorno). Solución: rootfs RW + daemon-reload.
- **Rootfs RO**: `/` montado RO en kernel cmdline. Recuperación vía GRUB (cambiar `ro`→`rw`) + `recovery_rootfs_rw.sh`.

### Tests arreglados (FASES 1-4)
- test_plugin, test_plugin_registry, test_events, test_pipeline_mvp (127+25+141+21 = 314) — ✅
- test_assistant_auth, test_audit_models, test_audit_message_store, test_ci_cd (15+35+15+7 = 72) — ✅
- test_documentation, test_integration_f10/11, test_observability_f11 (20+14+25 = 59) — ✅
- test_openclaw, test_vram_guard, test_snc_*, test_unit (11+10+27+20 = 68) — ✅
- **Total subset fijo: 565 passed, 5 skipped, 0 failed**

### Linting
- Ruff: 37 errores (mayoría EXE002 cosmético — permisos de ejecución en .py)
- Bandit HIGH: 0

### Deuda técnica
- **Cobertura de tests**: desconocida. No se ha ejecutado `pytest --cov` completo. El subset fijo no representa cobertura real del proyecto.
- **OpenRouter no configurado**: sin OPENROUTER_API_KEY. Fallback a Ollama local no responde por timeout. El script external_audit.sh requiere clave para funcionar con Claude.
- **Import circular core↔motor**: 9 archivos identificados — pendiente de refactor.
- **sys.exit() en librerías core/**: pendiente (1 migrado a RuntimeError en shared/paths.py).
- **shared/paths.py como fuente canónica**: ARRANCADO ✅ (core/agents/constants.py ya importa de shared).

---
*Última actualización: 2026-07-28 17:02 UTC*
