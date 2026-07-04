# Auditoría de Integración — Plan v7 vs Estado Real del Repositorio

**Fecha**: 2026-07-01
**Fuente de verdad**: repositorio en `/home/ramon/URA/ura_ia_1972/`
**Documento auditado**: Plan v7 (10 capas + 16 fixes), recibido como propuesta arquitectónica

---

## 1. Inventario — Qué partes del plan v7 YA EXISTEN

| Componente v7 | Estado real | Archivo(s) |
|---|---|---|
| Backup unificado multi-destino | ✅ EXISTE | `scripts/pro/backup_unified.sh`, `backup_to_mac.sh`, `backup_gx10_configs.sh`, `backup_hetzner_to_asus.sh` |
| Structured JSON logger | ✅ EXISTE | `core/json_logger.py` — `StructuredLogger` wrapper + `JsonFormatter` |
| Auth layer con toggle | ✅ EXISTE | `core/auth_layer.py` — `validate(api_key)`, `AUTH_ENABLED` toggle |
| SNC polling loop (10s) | ✅ EXISTE | `monitor/snc.py` — auto-repair, zombie cleanup, service monitoring |
| `op_events`, `op_audit`, `op_jobs`, `op_scheduler` tablas | ✅ EXISTEN en schema | `schemas/knowledge_graph.sql` — pero NUNCA escritas |
| `kg_active_version` singleton | ✅ EXISTE | Schema + `ActiveVersionRepository` |
| CLI `ke` (8 subcomandos) | ✅ EXISTE | `knowledge/engine/cli.py` |
| `ejecutor_api.py` REST API (puerto 4096) | ✅ EXISTE | `scripts/pro/ejecutor_api.py` — **NO** usa aiohttp, usa `http.server.HTTPServer` |
| `ura_multi_agent.py` (3 agentes) | ✅ EXISTE | `core/ura_multi_agent.py` |
| `agent_hierarchy.py` (5 roles) | ✅ EXISTE | `agent_hierarchy.py` |
| `search_logger.py` feedback NDJSON | ✅ EXISTE | `core/search_logger.py` — `log_feedback()` con rating 1-5 |
| `core/metrics.py` search quality | ✅ EXISTE | `core/metrics.py` — precision@k, coverage, diversity |
| `docker_orchestrator.py` sandbox | ✅ EXISTE | `core/sandbox/docker_orchestrator.py` |
| `heartbeat.py` (3-strike restart) | ✅ EXISTE | `core/infra/heartbeat.py` |
| `rollback_manager.py` git-based | ✅ EXISTE | `core/seguridad/rollback_manager.py` |
| `fastapi>=0.111.0`, `uvicorn>=0.30.0` | ✅ YA EN `pyproject.toml` | No son nuevas dependencias |
| `mcp==1.23.3` | ✅ INSTALADO + FastMCP funciona | Falta agregar a `pyproject.toml` |
| `.nervioso/` para estado efímero | ✅ EXISTE | Contiene `audit_trail.log`, `estado_mantenimiento.json`, `reglas_auto.json` |

---

## 2. Reutilización — Qué código actual se reutiliza SIN CAMBIOS

| Módulo | Lo reutiliza v7 para... | Sin cambios |
|---|---|---|
| `knowledge/engine/models.py` | Todos los modelos de datos | ✅ No tocar |
| `knowledge/engine/parser.py` | Parseo de documentos | ✅ No tocar |
| `knowledge/engine/validator.py` + `VALID_DOC_TYPES` | Validación de documentos | ✅ No tocar |
| `knowledge/engine/verifier.py` (facade) | Verificación de integridad (Capa 4) | ✅ No tocar |
| `knowledge/engine/storage_verifier.py` | Verificación SQLite | ✅ No tocar |
| `knowledge/engine/knowledge_verifier.py` | Verificación de grafo (ciclos, huérfanos, hashes) | ✅ No tocar |
| `knowledge/engine/migrations.py` | Migraciones (todas las capas) | ✅ No tocar (nuevas tablas usan el mismo sistema) |
| `knowledge/engine/chunker.py` | Chunking para embeddings (Capa 1, 8) | ✅ No tocar |
| `knowledge/engine/reader.py` | Consultas (Capa 4, 6, 7 añaden overlay) | ⚠️ Modificar para overlay de ranking |
| `knowledge/engine/qdrant_sync.py` | Sync semántico (Capa 1 archive vectors) | ⚠️ Modificar para métricas + purge |
| `core/auth_layer.py` | Base para RBAC (Capa 3) | ⚠️ Extender con roles |
| `core/search_logger.py` | Feedback NDJSON existente (Capa 7) | ✅ No tocar — v7 propone leer del NDJSON existente |
| `scripts/pro/ejecutor_api.py` | API legacy (Capa 6) | ✅ **NO TOCAR** — nuevo servicio en puerto aparte |
| `core/ura_multi_agent.py` | Sistema multi-agente existente | ✅ No tocar — agentes de conocimiento son complemento |
| `monitor/snc.py` | Auto-repair del sistema | ✅ No tocar |

---

## 3. Conflictos — Desviaciones entre v7 y el repo real

### 3A. El plan v7 acierta (conflictos reales que identifica correctamente)

| Conflicto | Archivo | Gravedad | v7 lo resuelve |
|---|---|---|---|
| `cli/__init__.py` importa `cli.gatekeeper` inexistente | `cli/__init__.py:3` | 🔴 Bloqueante | ✅ Sí: eliminar import |
| `collector.py` es stub (`NotImplementedError`) | `knowledge/engine/collector.py:8` | 🟡 Medio | ✅ Sí: reemplazar con `request_compile` |
| `emergency_runbook.json` vacío (`{}`) | `deploy/emergency_runbook.json` | 🟡 Medio | ✅ Sí: poblar con comandos reales |
| `op_events`, `op_audit`, `op_jobs`, `op_scheduler` existen pero NUNCA se escriben | Schema v8 | 🟡 Medio | ✅ Sí: activar escritura |
| Backups no verifican checksums | `backup_unified.sh` | 🟢 Bajo | ✅ Sí: añadir `verify_archive` |
| No hay métricas Prometheus del Engine | N/A | 🟡 Medio | ✅ Sí: metrics.py derivadas de SQLite |
| No hay hashes de determinismo | N/A | 🔴 Crítico | ✅ Sí: `graph_content_sha256` en `kg_active_version` |
| No hay tracing (correlation_id) | N/A | 🟡 Medio | ✅ Sí: `uuid4()[:8]` en orchestrator |
| No hay RBAC (solo single shared key) | `core/auth_layer.py` | 🟡 Medio | ✅ Sí: 3 roles (READER/REVIEWER/ADMIN) |
| No hay cifrado de secrets | N/A | 🟡 Medio | ✅ Sí: Fernet + `ke secrets rotate` |
| Overlay de ranking vs grafo determinista | N/A | 🔴 Crítico | ✅ Sí: v7 introduce overlay, no muta `kg_nodes` |

### 3B. El plan v7 se equivoca (conflictos que introduce o diagnostica mal)

| # | Conflicto | Archivo v7 | Gravedad | Realidad | Corrección |
|---|---|---|---|---|---|
| **C1** | `ejecutor_api.py` usa aiohttp → "no se puede mount FastAPI sobre aiohttp" | [FIX 6] | 🟡 Medio | **NO usa aiohttp**. Usa `http.server.BaseHTTPRequestHandler` + `HTTPServer` (stdlib). No hay incompatibilidad ASGI porque no hay ASGI. | La conclusión es la misma (servicio FastAPI aparte en :4097), pero la justificación es falsa. Sin impacto en el diseño. |
| **C2** | `-- 0-100` en schema de `quality`/`confidence` | [FIX 8] | 🟢 Bajo | **No existe ese comentario**. `schemas/knowledge_graph.sql` tiene `quality REAL, confidence REAL` sin comentario de rango. | El fix (unificar escala [0,1]) sigue siendo válido como disciplina, pero no hay comentario erróneo que corregir. El fix es documentación, no código. |
| **C3** | `get_logger("knowledge.writer")` API | Capa 2 pseudocódigo | 🟢 Bajo | `StructuredLogger` no tiene función `get_logger()`. La API real es `StructuredLogger("ura.knowledge.writer")` | Corregir pseudocódigo: `from core.json_logger import StructuredLogger; log = StructuredLogger("ura.knowledge.writer")` |
| **C4** | `fastapi` y `uvicorn` como nuevas dependencias | Capa 6 | 🟢 Bajo | Ya están en `pyproject.toml`: `fastapi>=0.111.0`, `uvicorn>=0.30.0` | No añadir; ya incluidas. |
| **C5** | `mcp>=1.27,<2` como versión requerida | [FIX 13] | 🟢 Bajo | `mcp==1.23.3` instalado y `FastMCP` funciona. La versión `1.23` ya tiene el SDK estable con FastMCP. | Usar `mcp>=1.23` o simplemente `mcp`. No requiere upper bound ni versión específica. |
| **C6** | Pipeline stages `VERIFYING` y `SWAPPING` existen en el enum | §14 implícito | 🟢 Bajo | Existen en `CompileStage` enum pero **NO se usan** en `compiler.py`. Solo se usan: `DISCOVERING`, `PARSING`, `VALIDATING`, `WRITING`, `DONE`, `FAILED`. | El plan v7 menciona `verify=hash gate` en el pipeline, que es un concepto nuevo, no el stage existente. No hay conflicto. |
| **C7** | `cache/` directory para `audit.ndjson` | Capa 3 [FIX 4] | 🟡 Medio | **No existe directorio `cache/`** en el repo. Hay `data/`, `.nervioso/` que ya contiene `audit_trail.log`. | Usar `.nervioso/audit.ndjson` para seguir la convención existente de estado efímero. |

### 3C. Omisiones del plan v7 (lo que debería mencionar y no menciona)

| # | Omisión | Relevancia | Por qué importa |
|---|---|---|---|
| **O1** | Cambiar `op_vector_sync.status` de `'done'` a `'completed'` requiere migración de schema | 🔴 Alta | `op_vector_sync` tiene `CHECK (status IN ('pending','done','failed','dead_letter'))`. Cambiar a `'completed'` requiere recrear la tabla (ALTER TABLE no soporta modificar CHECKs en SQLite). v7 [FIX 10] omite este detalle. **Solución**: mantener `'done'` en `op_vector_sync` y solo usar `'completed'` en `op_jobs` (tablas diferentes, vocabularios diferentes). No unificar. |
| **O2** | `graph_content_sha256` requiere migración de schema | 🟡 Media | `kg_active_version` necesita nueva columna. Requiere `ALTER TABLE` en migration v9. v7 lo menciona como feature pero no como cambio de schema. |
| **O3** | Quién ejecuta el `op_scheduler` loop | 🟡 Media | v7 dice "jobs corren en op_scheduler" pero no especifica qué proceso implementa el loop de polling. ¿Un systemd timer? ¿Un thread en `ejecutor_api.py`? ¿Un agente dedicado? |
| **O4** | `orchestrator.py` y `flock(compile.lock)` presupone sistema de archivos compartido | 🟢 Baja | En GX10 (single node) funciona. Si en el futuro hubiera múltiples nodos, `flock` no escala. v7 no menciona esta limitación. |
| **O5** | `simpleeval` como evaluador de reglas no está en `pyproject.toml` | 🟢 Baja | Es nueva dependencia. v7 [FIX 7] propone `simpleeval` pero no lo lista en las dependencias nuevas. |

---

## 4. Cambios Mínimos — Lo que REALMENTE hay que modificar

Tras la auditoría, estos son los cambios estrictamente necesarios, ordenados por necesidad real (no por capa):

### Imprescindibles (sin esto el sistema no es seguro ni determinista)

1. **Archiver** (`knowledge/engine/archiver.py`): backup de source (git bundle), vectores (Qdrant dump), restore = recompilar. Sin esto, ante pérdida del source los vectores no se recuperan.
2. **Hash de determinismo**: `graph_content_sha256` en `kg_active_version` + golden-master test. Sin esto no puedes verificar que el compile es reproducible.
3. **Overlay de ranking** en Reader: feedback y frescura como overlay, no en `kg_nodes`. Sin esto, cualquier feedback rompe el determinismo.
4. **Orchestrator** (`orchestrator.py`): único punto de entrada al compile. Sin esto, 6 fuentes distintas pueden llamar a `apply_compile` concurrentemente.

### Muy recomendables (sin esto, operación diaria es frágil)

5. **Métricas derivadas de SQLite** (Capa 2): porque el compiler es efímero.
6. **Audit lock-free**: NDJSON append para el read path + escritura en transacción para el write path.
7. **RBAC mínimo**: 3 roles sobre `auth_layer.py` existente.
8. **Secrets cifrados**: Fernet + rotación.

### Deseables (mejoran calidad de vida)

9. **MCP Server** con SDK oficial: integración con Claude/OpenCode.
10. **Simple jobs queue** sobre `op_jobs`: reemplazar `collector.py` stub.
11. **Pipeline DAG** con timeouts.
12. **Purge policies**: `op_vector_sync`, `op_compile_errors`, `op_compiler_runs`.
13. **Emergency runbook poblado**.

---

## 5. Cambios Innecesarios — Lo que v7 propone pero NO conviene hacer

| Propuesta v7 | Por qué NO hacerlo |
|---|---|
| `kg_nodes_history` / `kg_edges_history` (archivar versiones del grafo) | El grafo se regenera del source. Git es la historia. Añadir otra capa de history es duplicar funcionalidad y rompe "derivado=desechable" |
| `op_graph_snapshots` tabla para snapshots del grafo | Idem. Se archiva source + vectores, no el grafo. v7 [FIX 9] ya corrige esto. |
| `op_feedback` como tabla fuente de feedback | `search_logger.py` ya escribe NDJSON. La tabla `op_feedback_agg` es solo agregación, no fuente. v7 [FIX 1] ya corrige esto. |
| Migrar `ejecutor_api.py` de aiohttp a FastAPI | No usa aiohttp. Usa `http.server`. Y v7 [FIX 6] ya propone servicio aparte en :4097. |
| `tuner.py` que muta `kg_nodes.quality` | Rompe determinismo. v7 [FIX 1] ya corrige: overlay en Reader. |
| Sistema de usuarios completo (registro, login, sesiones) | 3 roles hardcodeados son suficientes para el alcance actual. |
| `Simpleeval` como dependencia obligatoria | Alternativa: AST-based evaluator con whitelist (sin dependencia externa). Si `simpleeval` no añade mantenimiento, vale; pero no es obligatorio. |

---

## 6. Riesgos — Qué puede romper compatibilidad

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| **Cambiar `'done'` → `'completed'` en `op_vector_sync`** sin migración | Alta (si se implementa literalmente) | 🔴 Database corrupta por CHECK constraint violation | **NO hacer**: mantener `'done'` en `op_vector_sync`. Solo `op_jobs` usa `'completed'`. Vocabularios independientes. |
| Post-compile hooks en `apply_compile()` lanzan excepción y rompen el compile | Media | 🔴 Compile falla, grafo no se actualiza | Hooks asíncronos via `op_jobs` (como propone v7). El hook solo encola, no ejecuta. |
| `overlay` en Reader añade latencia perceptible (>50ms) a búsquedas | Baja | 🟡 Usuarios notan lentitud | `op_feedback_agg` es tabla pequeña; `freshness_decay` es O(1). Medir antes de optimizar. |
| Nuevo servicio FastAPI :4097 compite con :4096 en puertos | Baja | 🟡 Confusión de endpoints | Reverse proxy (Caddy) enruta `/ke/*` → :4097, legacy → :4096. Documentado. |
| `graph_content_sha256` como gate de pipeline falso positivo por timestamp | Media | 🟡 Pipeline falla sin razón real | Excluir `updated_at` y `swapped_at` del hash (solo contenido semántico). |
| `op_scheduler` sin proceso dedicado nunca ejecuta tareas | Alta (si no se especifica) | 🟡 Purges, ingestas batch, feedback aggregation no corren | **Decidir**: ¿systemd timer, thread en API, o agente dedicado? |

---

## 7. Orden de Implementación — Secuencia óptima auditada

```
Fase 0  (1.5 d) — Pre-requisitos + red de seguridad
  □ Fix cli/__init__.py (eliminar import roto)
  □ Emergency runbook poblado (comandos reales)
  □ collector.py → request_compile stub
  □ knowledge/engine/orchestrator.py (request_compile + compile_worker con flock)
  □ Test golden-master de determinismo (baseline antes de tocar nada)

Fase A  (2.5 d) — Capa 1 Archival
  □ archiver.py (source git bundle, vectors dump, restore=recompile, verify)
  □ Tabla op_archives (migration v9)
  □ Purge policies (op_vector_sync, op_compile_errors, op_compiler_runs)
  □ CLI: ke archive, ke archive list, ke archive restore, ke archive verify
  □ backup verification en backup_unified.sh

Fase B  (2 d) — Capa 2 Observabilidad
  □ knowledge/engine/metrics.py (Prometheus: derivadas de SQLite)
  □ /metrics endpoint en nuevo servicio FastAPI :4097
  □ correlation_id propagation en orchestrator
  □ Structured logging gradual (flag URA_STRUCTURED_LOGS)

Fase C  (2.5 d) — Capa 3 Seguridad
  □ knowledge/engine/audit.py (read=NDJSON→.nervioso/, write=op_audit en txn)
  □ Ingesta batch NDJSON→op_audit (job programado)
  □ knowledge/engine/secrets.py (Fernet + ke secrets rotate)
  □ RBAC 3 roles sobre auth_layer.py existente
  □ Proteger endpoints del nuevo FastAPI :4097 con roles

Fase D  (2.5 d) — Capa 4 Razonamiento
  □ knowledge/engine/rules.py (simpleeval o AST evaluator)
  □ R001–R005 (warnings + overlay, no mutan kg_nodes)
  □ knowledge/engine/deduction.py (StateDeductor)
  □ knowledge/engine/recommendation.py (RecommendationValidator)
  □ CLI: ke rules list|eval <doc_id>, ke deduce

Fase E  (2 d) — Capa 5 Agentes
  □ knowledge/engine/jobs.py (wrapper sobre op_jobs, estados=pending|running|completed|failed|dead_letter)
  □ knowledge/agents/ (base.py, agent_compile, agent_quality, agent_archival)
  □ knowledge/engine/pipeline.py (DAG: snapshot→compile→verify→archive→qdrant_sync→rule_eval)
  □ Verify gate: graph_content_sha256 reproduce?
  ── NOTA: op_vector_sync mantiene 'done', op_jobs usa 'completed' (no unificar) ──

Fase F  (2 d) — Capa 6 Interfaces  [paralelizable con D–E]
  □ Servicio FastAPI :4097 (ke/status, ke/search, ke/docs, ke/compile, ke/archive...)
  □ Reverse proxy Caddy (:443 → :4096 legacy + :4097 KE)
  □ MCP Server (FastMCP SDK oficial, ya instalado)
  □ Arreglar cli/__init__.py (ya en Fase 0, verificar)

Fase G  (1 d) — Capa 7 Feedback  [paralelizable con D–E]
  □ op_feedback_agg (tabla agregada desde NDJSON existente)
  □ Overlay en Reader: effective_score = base ⊕ feedback ⊕ freshness
  □ CLI: ke feedback <doc_id> --rating 4

Fase I  (1 d) — Capa 9 DR  [tras A]
  □ scripts/dr/drill_restore.sh (recompile + hash verify)
  □ backup verify integrado

Fase H  (opc. 3–5 d) — Capa 8 ML  [post-G]
  Fase J  (opc. 2–3 d) — Capa 10 Integraciones  [post-F]
```

---

## 8. Estimación — Tiempo y complejidad por fase

| Fase | Días | Dependencias | Riesgo | Líneas nuevas (est.) | Líneas modificadas |
|---|---|---|---|---|---|
| **0** | 1.5 | Ninguna | 🟢 Bajo | ~150 | ~10 |
| **A** | 2.5 | Fase 0 | 🟡 Medio | ~400 | ~50 |
| **B** | 2 | Fase A | 🟢 Bajo | ~300 | ~80 |
| **C** | 2.5 | Fase B | 🟡 Medio | ~350 | ~60 |
| **D** | 2.5 | Fase C | 🟡 Medio | ~500 | ~40 |
| **E** | 2 | Fases A–D | 🟡 Medio | ~400 | ~30 |
| **F** | 2 | Fase C | 🟡 Medio | ~350 | ~10 |
| **G** | 1 | Fase F | 🟢 Bajo | ~150 | ~50 |
| **I** | 1 | Fase A | 🟢 Bajo | ~80 | ~30 |
| **H** | 3–5 | Fase G | 🔴 Alto | ~600 | ~20 |
| **J** | 2–3 | Fase F | 🟡 Medio | ~300 | ~10 |

**Total MVP (0–G+I)**: ~15–17 días efectivos  
**Total completo (0–J)**: ~20–25 días efectivos  
**Complejidad general**: 🟡 Media (baja por fase, pero 12 módulos nuevos requieren coordinación)

---

## 9. Mapa de Archivos — Estado Final Auditado

### Nuevos (11, no 12)

El plan v7 propone 12. Auditoría reduce a 11 (elimina `tuner.py` que mutaba `kg_nodes`, ya corregido en [FIX 1]):

| Archivo | Capa | LOC est. |
|---|---|---|
| `knowledge/engine/orchestrator.py` | §4 | ~120 |
| `knowledge/engine/archiver.py` | 1 | ~250 |
| `knowledge/engine/metrics.py` | 2 | ~150 |
| `knowledge/engine/audit.py` | 3 | ~150 |
| `knowledge/engine/secrets.py` | 3 | ~80 |
| `knowledge/engine/rules.py` | 4 | ~250 |
| `knowledge/engine/deduction.py` | 4 | ~120 |
| `knowledge/engine/recommendation.py` | 4 | ~80 |
| `knowledge/engine/jobs.py` | 5 | ~100 |
| `knowledge/engine/pipeline.py` | 5 | ~150 |
| `knowledge/agents/` (package) | 5 | ~200 |
| `knowledge/engine/mcp_server.py` | 6 | ~100 |

Más el servicio FastAPI en `scripts/ke_api.py` o similar (~250 LOC).

### Modificados (8, no 10)

El plan v7 propone 10. Auditoría elimina `ejecutor_api.py` (no tocar, servicio aparte):

| Archivo | Cambio |
|---|---|
| `knowledge/engine/compiler.py` | Hooks post-commit (archive-request, metrics, audit-en-txn, graph_content_sha256) |
| `knowledge/engine/reader.py` | Overlay de ranking + audit NDJSON + RBAC guard |
| `knowledge/engine/sqlite_writer.py` | Purge policies + escribir op_audit en txn |
| `knowledge/engine/scanner.py` | Métricas → tablas (snapshot size, doc count) |
| `knowledge/engine/qdrant_sync.py` | Métricas → tablas + purge policy |
| `knowledge/engine/collector.py` | Stub → `orchestrator.request_compile()` |
| `knowledge/engine/cli.py` | Nuevos comandos: archive, rules, deduce, feedback |
| `knowledge/engine/__init__.py` | Exportar nuevos módulos |
| `cli/__init__.py` | Eliminar import roto (fix mínimo) |
| `schemas/knowledge_graph.sql` | Migration v9: `op_archives`, `graph_content_sha256` en `kg_active_version`, `op_feedback_agg` |

---

## 10. Resumen de Decisiones Arquitectónicas

| Decisión | Resolución |
|---|---|
| `'done'` vs `'completed'` en estados | ✅ Mantener `'done'` en `op_vector_sync` (por compatibilidad de schema). Solo `op_jobs` usa `'completed'`. NO unificar. |
| Servicio FastAPI :4097 vs migrar ejecutor_api | ✅ Servicio nuevo, puerto nuevo. Legacy intacto. Reverse proxy Caddy. |
| `cache/` vs `.nervioso/` para audit NDJSON | ✅ Usar `.nervioso/` (convención existente, ya contiene audit_trail.log) |
| `simpleeval` vs AST builtin | ✅ `simpleeval` como dependencia (más seguro que AST manual, menos código que mantener). Añadir a pyproject.toml. |
| `StructuredLogger` vs `get_logger()` | ✅ Usar API real: `StructuredLogger("ura.knowledge.xxx")`. El pseudocódigo de v7 es ilustrativo, no normativo. |
| `op_scheduler` loop | ✅ Decisión: systemd timer + script que llama a `ke job-process` (el worker de orchestator.py). Más simple que un thread dentro del API. |
| Hash de determinismo en `graph_content_sha256` | ✅ Excluir `updated_at` y `swapped_at` del contenido del hash. Solo columnas semánticas: `id, type, path, content_sha256, body, frontmatter, quality, confidence, embed_hash` de `kg_nodes` + `src, dst, relation` de `kg_edges`. |

---

*Auditoría completada. 3 errores factuales corregidos en el plan v7 (C1, C2, C4), 3 imprecisiones menores (C3, C5, C6), 1 omisión de convención del repo (C7), 5 omisiones de detalle técnico (O1–O5). El plan es sólido y viable tras estas correcciones. La decisión más importante que no está en v7: NO cambiar `'done'` a `'completed'` en `op_vector_sync` — requeriría recrear la tabla y no aporta valor real.*
