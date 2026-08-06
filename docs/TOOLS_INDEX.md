# 🧰 Índice de Herramientas — URA v3.2

**Total:** 107 herramientas ejecutables | **Actualizado:** `python3 scripts/pro/tools_index.py`

---

| Herramienta | Descripción | Uso |
|-------------|-------------|-----|
n| `core/agents/cli.py` | CLI entry point for the multi-agent system. | — |
| `core/auth_layer.py` | Auth Layer - Validación de API keys para endpoints protegidos. | — |
| `core/change_guardian.py` | URA Change Guardian — Guardián de cambios con rollback automático | — |
| `core/config_manager.py` | Config Manager - Carga unificada de configuración con perfiles por sistema opera | — |
| `core/debate/debate_engine.py` | debate_engine.py — SDA: Sistema de Debate entre Agentes. | — |
| `core/debate/plan_validator.py` | plan_validator.py — Inyección de contexto real del sistema en el debate. | `python3 plan_validator.py                      # imprime JSO` |
| `core/event_bus.py` | event_bus.py — Bus de eventos asíncrono con journal persistente y ZeroMQ PUB/SUB | — |
| `core/guardian_disco.py` | Guardián de Disco — Detección de cambios vía SHA-256 con verificación post-escri | `python3 core/guardián_disco.py --scan              # Escanea` |
| `core/guardian_openclaw.py` | Guardián de Seguridad para OpenClaw | — |
| `core/infra/heartbeat.py` | Heartbeat check para ura-mochila.service. | `python3 core/infra/heartbeat.py                  # una ejecu` |
| `core/ingestador_red.py` | Ingestador de Red Global — Tailscale SSH + Distribución de Tareas. | `python3 core/ingestador_red.py --status            # Estado ` |
| `core/memory_engine.py` | Memory Engine — RAG (Retrieval-Augmented Generation) para URA. | — |
| `core/model_router/cli.py` | CLI — entrypoint: main() + verificar_politicas_seguridad_preflight. | — |
| `core/qdrant_retention.py` | qdrant_retention.py — Política de retención y limpieza por colección Qdrant. | — |
| `core/resolver_red.py` | DNS Resolver + Network Failover — MagicDNS + Cable + Tailscale. | `python3 core/resolver_red.py --resolver <hostname>    # Reso` |
| `core/sandbox.py` | Módulo: core/sandbox.py | — |
| `core/search_engine.py` | Search Engine - Búsqueda simple en documentos indexados. | — |
| `core/search_logger.py` | search_logger.py — NDJSON query logging for search quality analysis. | — |
| `core/secretario_cache.py` | secretario_cache.py — Cliente ligero desde Mac hacia ASUS para embedding + cache | — |
| `core/utils/anonymizer.py` | anonymizer.py — Saneamiento determinista de datos sensibles. | — |
| `core/voice/anker_mac_pipeline.py` | Pipeline de audio determinista para Mac mini M4 (Apple Silicon). | — |
| `core/voice/anker_pipeline.py` | Pipeline de audio determinista para Anker PowerConf S500. | — |
| `core/voice/tts_piper.py` | Motor de síntesis TTS local con Piper para URA. | — |
| `core/watchdog_funciones.py` | watchdog_funciones.py — Decorador para monitorear tiempo de ejecución. | — |
| `knowledge/engine/cli/main.py` | CLI main — parser, entry point, shared helpers. | — |
| `mantenimiento/ura_maintenance.py` | URA Maintenance System - Sistema de mantenimiento automatizado (SEGURE) | — |
| `mantenimiento/ura_maintenance_remote.py` | URA Maintenance Remote - Ejecuta mantenimiento en nodos remotos del enjambre (SE | — |
| `monitor/error_logger.py` | Error Logger — Log circular de errores para URA. | — |
| `monitor/health_check.py` | Health Check v2 — Diagnóstico completo del GX10. | — |
| `monitor/log_alerts.py` | Log Alerts v2 — Centraliza y de-duplica errores críticos desde GX10. | — |
| `monitor/mac_heartbeat.py` | Mac Heartbeat — Detección de presencia Mac. | — |
| `monitor/openclaw.py` | OpenClaw — Brazo ejecutor de emergencia bajo control del SNC. | — |
| `monitor/snc.py` | Sistema Nervioso Central (SNC) — Polling activo cada 10s. | — |
| `monitor/snc_remote.py` | SNC Remote — Observador en Mac. | — |
| `motor/assistant/main.py` | URA Assistant — servidor conversacional FastAPI. | — |
| `motor/cli/main.py` | (sin descripción) | — |
| `motor/health_monitor.py` | Health Monitor — alertas automáticas cuando componentes se degradan. | — |
| `motor/tests/test_pipeline.py` | (sin descripción) | — |
| `motor/tests/test_preflight.py` | (sin descripción) | — |
| `motor/tests/test_scanner.py` | (sin descripción) | — |
| `mutants/tests/integration/test_openclaw.py` | Tests de integración — OpenClaw + SNC | — |
| `mutants/tests/legacy/test_sda.py` | Unit Test Suite — SDA (Sistema de Debate entre Agentes) | — |
| `mutants/tests/legacy/test_unit.py` | Unit Test Suite — URA v3.0 | — |
| `mutants/tests/unit/test_ast_sentinel.py` | Test AST Sentinel. | — |
| `mutants/tests/unit/test_memoria_fallos.py` | Test memoria_fallos. | — |
| `mutants/tests/unit/test_memoria_movimiento.py` | Test memoria_movimiento. | — |
| `mutants/tests/unit/test_mochila.py` | Test mochila_engine. | — |
| `mutants/tests/unit/test_prompt_injector.py` | Test Prompt Injector. | — |
| `scraping/meta_miner_remote.py` | Meta Miner Remoto — Extracción determinista de metadatos de código. | — |
| `scripts/health_check_brain.py` | Health check para motor/brain/ — verifica imports, instancias, hooks. | `python3 scripts/health_check_brain.py           # stdout` |
| `scripts/pro/adr_generator.py` | ADR Generator — Genera documentos de decisión automáticamente tras commits signi | — |
| `scripts/pro/audit_inventario.py` | audit_inventario.py — Inventario automatizado de herramientas del repo. | `Uso: python3 scripts/pro/audit_inventario.py [--json data/in` |
| `scripts/pro/audit_secrets.py` | Auditoría de secretos — detecta secretos hardcodeados, credenciales en | `python3 scripts/pro/audit_secrets.py` |
| `scripts/pro/auditor_router.py` | Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir. | `python3 scripts/pro/auditor_router.py              # Auditor` |
| `scripts/pro/auditoria_continua.py` | Auditoría Continua — suite única de comprobaciones automáticas. | — |
| `scripts/pro/auditoria_paralela.py` | Auditoría paralela — 10 checks automáticos de salud del sistema. | `python3 scripts/pro/auditoria_paralela.py          # ejecuta` |
| `scripts/pro/auto_reglas.py` | Auto-Reglas — Sistema de reparación auto-aprendida. | — |
| `scripts/pro/backup_assistant.py` | Backup del asistente conversacional — DBs y configuración. | — |
| `scripts/pro/backup_f26_memory.py` | F29 B4 — Backup + Restore para F26 Memory. | `python3 scripts/pro/backup_f26_memory.py backup [--path /tmp` |
| `scripts/pro/capturar_evidencias.py` | capturar_evidencias.py — registra evidencias objetivas del proyecto. | `Uso: python3 scripts/pro/capturar_evidencias.py` |
| `scripts/pro/change_log.py` | Unified Change Log — registro estructurado de cambios del repositorio. | `python3 scripts/pro/change_log.py --record <commit_hash>` |
| `scripts/pro/chaos_test.py` | chaos_test.py — Ingeniería del caos para URA. | `python3 scripts/pro/chaos_test.py --list          # Listar t` |
| `scripts/pro/check_secrets.py` | check_secrets.py — Pre-commit hook: detecta secrets hardcodeados. | — |
| `scripts/pro/cleanup_assistant.py` | Limpieza automática de conversaciones antiguas. | `Ejecutar diariamente: crontab -e → @daily python3 /path/to/c` |
| `scripts/pro/commit_msg_validator.py` | Validador de mensajes de commit (conventional commits). | `python3 scripts/pro/commit_msg_validator.py <mensaje>` |
| `scripts/pro/compactadora.py` | Compactadora Determinista — Reintegra código refactorizado. | — |
| `scripts/pro/conciencia.py` | Conciencia Unificada — Memoria global de todos los procesos del pipeline. | `python3 conciencia.py --leer                          # Ver ` |
| `scripts/pro/consolidacion.py` | Consolidación Automática — ciclo completo de calidad. | — |
| `scripts/pro/dashboard.py` | Dashboard de Salud de URA — métricas del sistema completo. | — |
| `scripts/pro/gpu_health.py` | GPU Health Check — Detección temprana del bug de power cap (15W/650MHz). | `python3 gpu_health.py              → Salida legible` |
| `scripts/pro/hardening_audit.py` | hardening_audit.py — Audita el nivel de hardening de todos los servicios systemd | `Uso: python3 scripts/pro/hardening_audit.py` |
| `scripts/pro/lock_manager.py` | Lock Manager — Cerrojo de exclusión mutua para operaciones GPU. | — |
| `scripts/pro/manage_timers.py` | manage_timers.py — gestiona los timers systemd de URA. | `python3 scripts/pro/manage_timers.py status   # estado de ca` |
| `scripts/pro/master_conciencia.py` | master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan | — |
| `scripts/pro/metrics_server.py` | metrics_server.py — URA Search Quality Dashboard. | — |
| `scripts/pro/orchestrator.py` | Orquestador de health checks — ejecuta antes de push. | — |
| `scripts/pro/orquestador.py` | Orquestador de tareas — pipeline estructurado de 8 fases. | `python3 scripts/pro/orquestador.py data/tasks/TAREA.json` |
| `scripts/pro/pipeline_refactor.py` | Pipeline de Refactorización — independiente, invocable desde mejora continua. | `python3 scripts/pro/pipeline_refactor.py [--workers 4] [--mo` |
| `scripts/pro/pipeline_supremo.py` | Pipeline Supremo — Orquestador completo de refactorizacion URA. | — |
| `scripts/pro/plugin_registry.py` | Plugin Registry — Auto-descubrimiento de scripts. | — |
| `scripts/pro/quality_gate.py` | Quality Gate: decide si el codigo es aceptable basado en reportes de la tunelado | — |
| `scripts/pro/refactor_large_functions_v2.py` | Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION. | — |
| `scripts/pro/reglas_loader.py` | Reglas Loader desde JSON. | — |
| `scripts/pro/reindex_vectors.py` | reindex_vectors.py — Reindexa todos los assets en el VectorStore. | `python3 scripts/pro/reindex_vectors.py [--db PATH] [--execut` |
| `scripts/pro/router_rate_limiter.py` | Rate Limiter para Model Router - Previene abusos por IP. | — |
| `scripts/pro/sanear_codigo.py` | Sanear código automáticamente: corrige errores de ruff categoría por categoría. | `Uso: python3 scripts/pro/sanear_codigo.py [--check-only]` |
| `scripts/pro/tests/test_logger_regression.py` | Test de regresión: Logger.warn() vs Logger.warning(). | — |
| `scripts/pro/tuneladora/generate_index.py` | generate_index — indexa el código fuente en memoria semántica + repo_index.json. | — |
| `scripts/pro/tuneladora/install_service.py` | Instala el servicio systemd de la tuneladora. | — |
| `scripts/pro/tuneladora/notifier.py` | Notificador de fallos del pipeline de la tuneladora. | — |
| `scripts/pro/tuneladora/preflight_system.py` | Pre-flight check: evita duplicados de servicios, puertos, screens. | — |
| `scripts/pro/tuneladora/scheduler_daemon.py` | Scheduler daemon — punto de entrada systemd para TuneladoraScheduler. | — |
| `scripts/pro/tuneladora/shadow/shadow_health.py` | Shadow Health — orquestador multi-capa de health checks para el pipeline. | — |
| `scripts/pro/tuneladora/tuneladora_pipeline.py` | CLI principal del pipeline tuneladora v7.0. | `python3 scripts/pro/tuneladora/tuneladora_pipeline.py --mode` |
| `scripts/pro/tuneladora_mantenimiento.py` | TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback. | — |
| `scripts/pro/tuneladora_mejora.py` | Tuneladora de Mejora Continua — v2.3 con checkpoint, ledger y presupuesto. | — |
| `scripts/pro/ura_query.py` | URA RAG query — Contexto vectorial. | — |
| `tests/integration/test_openclaw.py` | Tests de integración — OpenClaw + SNC | — |
| `tests/legacy/test_sda.py` | Unit Test Suite — SDA (Sistema de Debate entre Agentes) | — |
| `tests/legacy/test_unit.py` | Unit Test Suite — URA v3.0 | — |
| `tests/unit/test_ast_sentinel.py` | Test AST Sentinel. | — |
| `tests/unit/test_memoria_fallos.py` | Test memoria_fallos. | — |
| `tests/unit/test_memoria_movimiento.py` | Test memoria_movimiento. | — |
| `tests/unit/test_mochila.py` | Test mochila_engine. | — |
| `tests/unit/test_prompt_injector.py` | Test Prompt Injector. | — |
| `ura.py` | URA CLI — Punto de entrada central (wrapper hacia motor/cli/main.py). | — |
| `ura_chat.py` | CLI interactivo para el asistente conversacional. | — |

---

## Por categoría


### core/

- **`cli`** — CLI entry point for the multi-agent system.
- **`auth_layer`** — Auth Layer - Validación de API keys para endpoints protegidos.
- **`change_guardian`** — URA Change Guardian — Guardián de cambios con rollback automático
- **`config_manager`** — Config Manager - Carga unificada de configuración con perfiles por sistema operativo.
- **`debate_engine`** — debate_engine.py — SDA: Sistema de Debate entre Agentes.
- **`plan_validator`** — plan_validator.py — Inyección de contexto real del sistema en el debate.
  - Uso: `python3 plan_validator.py                      # imprime JSON con contexto`
- **`event_bus`** — event_bus.py — Bus de eventos asíncrono con journal persistente y ZeroMQ PUB/SUB.
- **`guardian_disco`** — Guardián de Disco — Detección de cambios vía SHA-256 con verificación post-escritura.
  - Uso: `python3 core/guardián_disco.py --scan              # Escanear y comparar con sna`
- **`guardian_openclaw`** — Guardián de Seguridad para OpenClaw
- **`heartbeat`** — Heartbeat check para ura-mochila.service.
  - Uso: `python3 core/infra/heartbeat.py                  # una ejecucion`
- **`ingestador_red`** — Ingestador de Red Global — Tailscale SSH + Distribución de Tareas.
  - Uso: `python3 core/ingestador_red.py --status            # Estado de todos los disposi`
- **`memory_engine`** — Memory Engine — RAG (Retrieval-Augmented Generation) para URA.
- **`cli`** — CLI — entrypoint: main() + verificar_politicas_seguridad_preflight.
- **`qdrant_retention`** — qdrant_retention.py — Política de retención y limpieza por colección Qdrant.
- **`resolver_red`** — DNS Resolver + Network Failover — MagicDNS + Cable + Tailscale.
  - Uso: `python3 core/resolver_red.py --resolver <hostname>    # Resolver DNS a IP`
- **`sandbox`** — Módulo: core/sandbox.py
- **`search_engine`** — Search Engine - Búsqueda simple en documentos indexados.
- **`search_logger`** — search_logger.py — NDJSON query logging for search quality analysis.
- **`secretario_cache`** — secretario_cache.py — Cliente ligero desde Mac hacia ASUS para embedding + cache.
- **`anonymizer`** — anonymizer.py — Saneamiento determinista de datos sensibles.
- **`anker_mac_pipeline`** — Pipeline de audio determinista para Mac mini M4 (Apple Silicon).
- **`anker_pipeline`** — Pipeline de audio determinista para Anker PowerConf S500.
- **`tts_piper`** — Motor de síntesis TTS local con Piper para URA.
- **`watchdog_funciones`** — watchdog_funciones.py — Decorador para monitorear tiempo de ejecución.

### knowledge/

- **`main`** — CLI main — parser, entry point, shared helpers.

### mantenimiento/

- **`ura_maintenance`** — URA Maintenance System - Sistema de mantenimiento automatizado (SEGURE)
- **`ura_maintenance_remote`** — URA Maintenance Remote - Ejecuta mantenimiento en nodos remotos del enjambre (SEGURE)

### monitor/

- **`error_logger`** — Error Logger — Log circular de errores para URA.
- **`health_check`** — Health Check v2 — Diagnóstico completo del GX10.
- **`log_alerts`** — Log Alerts v2 — Centraliza y de-duplica errores críticos desde GX10.
- **`mac_heartbeat`** — Mac Heartbeat — Detección de presencia Mac.
- **`openclaw`** — OpenClaw — Brazo ejecutor de emergencia bajo control del SNC.
- **`snc`** — Sistema Nervioso Central (SNC) — Polling activo cada 10s.
- **`snc_remote`** — SNC Remote — Observador en Mac.

### motor/

- **`main`** — URA Assistant — servidor conversacional FastAPI.
- **`main`** — (sin descripción)
- **`health_monitor`** — Health Monitor — alertas automáticas cuando componentes se degradan.
- **`test_pipeline`** — (sin descripción)
- **`test_preflight`** — (sin descripción)
- **`test_scanner`** — (sin descripción)

### mutants/

- **`test_openclaw`** — Tests de integración — OpenClaw + SNC
- **`test_sda`** — Unit Test Suite — SDA (Sistema de Debate entre Agentes)
- **`test_unit`** — Unit Test Suite — URA v3.0
- **`test_ast_sentinel`** — Test AST Sentinel.
- **`test_memoria_fallos`** — Test memoria_fallos.
- **`test_memoria_movimiento`** — Test memoria_movimiento.
- **`test_mochila`** — Test mochila_engine.
- **`test_prompt_injector`** — Test Prompt Injector.

### raíz/

- **`ura`** — URA CLI — Punto de entrada central (wrapper hacia motor/cli/main.py).
- **`ura_chat`** — CLI interactivo para el asistente conversacional.

### scraping/

- **`meta_miner_remote`** — Meta Miner Remoto — Extracción determinista de metadatos de código.

### scripts/

- **`health_check_brain`** — Health check para motor/brain/ — verifica imports, instancias, hooks.
  - Uso: `python3 scripts/health_check_brain.py           # stdout`
- **`adr_generator`** — ADR Generator — Genera documentos de decisión automáticamente tras commits significativos.
- **`audit_inventario`** — audit_inventario.py — Inventario automatizado de herramientas del repo.
  - Uso: `Uso: python3 scripts/pro/audit_inventario.py [--json data/inventario_herramienta`
- **`audit_secrets`** — Auditoría de secretos — detecta secretos hardcodeados, credenciales en
  - Uso: `python3 scripts/pro/audit_secrets.py`
- **`auditor_router`** — Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir.
  - Uso: `python3 scripts/pro/auditor_router.py              # Auditoría completa`
- **`auditoria_continua`** — Auditoría Continua — suite única de comprobaciones automáticas.
- **`auditoria_paralela`** — Auditoría paralela — 10 checks automáticos de salud del sistema.
  - Uso: `python3 scripts/pro/auditoria_paralela.py          # ejecuta los 10 checks`
- **`auto_reglas`** — Auto-Reglas — Sistema de reparación auto-aprendida.
- **`backup_assistant`** — Backup del asistente conversacional — DBs y configuración.
- **`backup_f26_memory`** — F29 B4 — Backup + Restore para F26 Memory.
  - Uso: `python3 scripts/pro/backup_f26_memory.py backup [--path /tmp/memory_backup.json]`
- **`capturar_evidencias`** — capturar_evidencias.py — registra evidencias objetivas del proyecto.
  - Uso: `Uso: python3 scripts/pro/capturar_evidencias.py`
- **`change_log`** — Unified Change Log — registro estructurado de cambios del repositorio.
  - Uso: `python3 scripts/pro/change_log.py --record <commit_hash>`
- **`chaos_test`** — chaos_test.py — Ingeniería del caos para URA.
  - Uso: `python3 scripts/pro/chaos_test.py --list          # Listar tests disponibles`
- **`check_secrets`** — check_secrets.py — Pre-commit hook: detecta secrets hardcodeados.
- **`cleanup_assistant`** — Limpieza automática de conversaciones antiguas.
  - Uso: `Ejecutar diariamente: crontab -e → @daily python3 /path/to/cleanup.py`
- **`commit_msg_validator`** — Validador de mensajes de commit (conventional commits).
  - Uso: `python3 scripts/pro/commit_msg_validator.py <mensaje>`
- **`compactadora`** — Compactadora Determinista — Reintegra código refactorizado.
- **`conciencia`** — Conciencia Unificada — Memoria global de todos los procesos del pipeline.
  - Uso: `python3 conciencia.py --leer                          # Ver estado general`
- **`consolidacion`** — Consolidación Automática — ciclo completo de calidad.
- **`dashboard`** — Dashboard de Salud de URA — métricas del sistema completo.
- **`gpu_health`** — GPU Health Check — Detección temprana del bug de power cap (15W/650MHz).
  - Uso: `python3 gpu_health.py              → Salida legible`
- **`hardening_audit`** — hardening_audit.py — Audita el nivel de hardening de todos los servicios systemd URA.
  - Uso: `Uso: python3 scripts/pro/hardening_audit.py`
- **`lock_manager`** — Lock Manager — Cerrojo de exclusión mutua para operaciones GPU.
- **`manage_timers`** — manage_timers.py — gestiona los timers systemd de URA.
  - Uso: `python3 scripts/pro/manage_timers.py status   # estado de cada timer`
- **`master_conciencia`** — master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan.
- **`metrics_server`** — metrics_server.py — URA Search Quality Dashboard.
- **`orchestrator`** — Orquestador de health checks — ejecuta antes de push.
- **`orquestador`** — Orquestador de tareas — pipeline estructurado de 8 fases.
  - Uso: `python3 scripts/pro/orquestador.py data/tasks/TAREA.json`
- **`pipeline_refactor`** — Pipeline de Refactorización — independiente, invocable desde mejora continua.
  - Uso: `python3 scripts/pro/pipeline_refactor.py [--workers 4] [--model qwen2.5-coder:14`
- **`pipeline_supremo`** — Pipeline Supremo — Orquestador completo de refactorizacion URA.
- **`plugin_registry`** — Plugin Registry — Auto-descubrimiento de scripts.
- **`quality_gate`** — Quality Gate: decide si el codigo es aceptable basado en reportes de la tuneladora.
- **`refactor_large_functions_v2`** — Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION.
- **`reglas_loader`** — Reglas Loader desde JSON.
- **`reindex_vectors`** — reindex_vectors.py — Reindexa todos los assets en el VectorStore.
  - Uso: `python3 scripts/pro/reindex_vectors.py [--db PATH] [--execute] [--batch N]`
- **`router_rate_limiter`** — Rate Limiter para Model Router - Previene abusos por IP.
- **`sanear_codigo`** — Sanear código automáticamente: corrige errores de ruff categoría por categoría.
  - Uso: `Uso: python3 scripts/pro/sanear_codigo.py [--check-only]`
- **`test_logger_regression`** — Test de regresión: Logger.warn() vs Logger.warning().
- **`generate_index`** — generate_index — indexa el código fuente en memoria semántica + repo_index.json.
- **`install_service`** — Instala el servicio systemd de la tuneladora.
- **`notifier`** — Notificador de fallos del pipeline de la tuneladora.
- **`preflight_system`** — Pre-flight check: evita duplicados de servicios, puertos, screens.
- **`scheduler_daemon`** — Scheduler daemon — punto de entrada systemd para TuneladoraScheduler.
- **`shadow_health`** — Shadow Health — orquestador multi-capa de health checks para el pipeline.
- **`tuneladora_pipeline`** — CLI principal del pipeline tuneladora v7.0.
  - Uso: `python3 scripts/pro/tuneladora/tuneladora_pipeline.py --mode check`
- **`tuneladora_mantenimiento`** — TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback.
- **`tuneladora_mejora`** — Tuneladora de Mejora Continua — v2.3 con checkpoint, ledger y presupuesto.
- **`ura_query`** — URA RAG query — Contexto vectorial.

### tests/

- **`test_openclaw`** — Tests de integración — OpenClaw + SNC
- **`test_sda`** — Unit Test Suite — SDA (Sistema de Debate entre Agentes)
- **`test_unit`** — Unit Test Suite — URA v3.0
- **`test_ast_sentinel`** — Test AST Sentinel.
- **`test_memoria_fallos`** — Test memoria_fallos.
- **`test_memoria_movimiento`** — Test memoria_movimiento.
- **`test_mochila`** — Test mochila_engine.
- **`test_prompt_injector`** — Test Prompt Injector.
