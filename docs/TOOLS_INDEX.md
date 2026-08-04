# 🧰 Índice de Herramientas — URA v3.2

**Total:** 178 herramientas ejecutables | **Actualizado:** `python3 scripts/pro/tools_index.py`

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
| `scraping/meta_miner_remote.py` | Meta Miner Remoto — Extracción determinista de metadatos de código. | — |
| `scripts/generate_synthetic_data.py` | Generador de datos sintéticos para pruebas de URA. | `python3 scripts/generate_synthetic_data.py --help` |
| `scripts/health_check_brain.py` | Health check para motor/brain/ — verifica imports, instancias, hooks. | `python3 scripts/health_check_brain.py           # stdout` |
| `scripts/pro/PLUGIN_TEMPLATE.py` | PLUGIN_TEMPLATE — Copiar y modificar para crear un script nuevo. | — |
| `scripts/pro/adr_generator.py` | ADR Generator — Genera documentos de decisión automáticamente tras commits signi | — |
| `scripts/pro/ajustar_contexto.py` | Ajuste Dinámico de Contexto para Refactorización. | — |
| `scripts/pro/alineador.py` | alineador.py — Valida que las respuestas de URA/OpenClaw sean utiles y no se des | — |
| `scripts/pro/analisis_completo.py` | analisis_completo.py — Analisis integral de URA (estado + monologo + acciones). | — |
| `scripts/pro/analizar_fallo_conciencia.py` | analizar_fallo_conciencia.py — Analiza resultados del test de conciencia | — |
| `scripts/pro/arq_auditor.py` | ARQ Auditor — auditoría arquitectónica automatizada (Bloques A–K). | `python3 scripts/pro/arq_auditor.py                    # info` |
| `scripts/pro/arq_checker.py` | ARQ-600: Validación funcional automatizada. | `python3 scripts/pro/arq_checker.py                    # stdo` |
| `scripts/pro/audit_config.py` | Auditoría de configuración unificada (F17 scope). | `python3 scripts/pro/audit_config.py` |
| `scripts/pro/audit_inventario.py` | audit_inventario.py — Inventario automatizado de herramientas del repo. | `Uso: python3 scripts/pro/audit_inventario.py [--json data/in` |
| `scripts/pro/audit_secrets.py` | Auditoría de secretos — detecta secretos hardcodeados, credenciales en | `python3 scripts/pro/audit_secrets.py` |
| `scripts/pro/auditor_dormidos.py` | (sin descripción) | — |
| `scripts/pro/auditor_makefile.py` | auditor_makefile.py — Auditoría de targets del Makefile (Fase 1 adaptada). | `Uso: python3 scripts/pro/auditor_makefile.py` |
| `scripts/pro/auditor_real.py` | auditor_real.py — Auditoría real de TODO el repo (Fase 1 adaptada). | `Uso: python3 scripts/pro/auditor_real.py` |
| `scripts/pro/auditor_router.py` | Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir. | `python3 scripts/pro/auditor_router.py              # Auditor` |
| `scripts/pro/auditoria_continua.py` | Auditoría Continua — suite única de comprobaciones automáticas. | — |
| `scripts/pro/auto_conciencia.py` | auto_conciencia.py — URA se auto-evalua y autocorrige usando OpenClaw. | — |
| `scripts/pro/auto_reglas.py` | Auto-Reglas — Sistema de reparación auto-aprendida. | — |
| `scripts/pro/autonomy/autonomy.py` | Autonomía v3.2 — orquestador multi-objetivo con planificación adaptativa. | — |
| `scripts/pro/autonomy/learning/aprendizaje.py` | Aprendizaje v4.0 — subsistema completo de aprendizaje avanzado. | — |
| `scripts/pro/autonomy/memory/memoria.py` | Memoria Semántica — capa de conocimiento sobre el ExecutionLedger. | — |
| `scripts/pro/autonomy/research/investigacion.py` | Investigación Autónoma — genera hipótesis, busca evidencias, sintetiza conclusio | — |
| `scripts/pro/autonomy/swarm/swarm.py` | Swarm URA — sistema multiagente coordinado. | — |
| `scripts/pro/backup_assistant.py` | Backup del asistente conversacional — DBs y configuración. | — |
| `scripts/pro/backup_f26_memory.py` | F29 B4 — Backup + Restore para F26 Memory. | `python3 scripts/pro/backup_f26_memory.py backup [--path /tmp` |
| `scripts/pro/captura_virtual.py` | captura_virtual.py — Captura programatica en Xvfb :99. | — |
| `scripts/pro/change_log.py` | Unified Change Log — registro estructurado de cambios del repositorio. | `python3 scripts/pro/change_log.py --record <commit_hash>` |
| `scripts/pro/chaos_f29_b5.py` | F29 B5 — Chaos Tests (7 escenarios). | `python3 scripts/pro/chaos_f29_b5.py [--all | --ct N]` |
| `scripts/pro/chaos_test.py` | chaos_test.py — Ingeniería del caos para URA. | `python3 scripts/pro/chaos_test.py --list          # Listar t` |
| `scripts/pro/check_secrets.py` | check_secrets.py — Pre-commit hook: detecta secrets hardcodeados. | — |
| `scripts/pro/chunk_optimizer.py` | Chunk Optimizer — Ajuste dinámico de tamaño según tasa de error. | `python3 chunk_optimizer.py --estado           # Ver estado a` |
| `scripts/pro/cleanup_assistant.py` | Limpieza automática de conversaciones antiguas. | `Ejecutar diariamente: crontab -e → @daily python3 /path/to/c` |
| `scripts/pro/commit_msg_validator.py` | Validador de mensajes de commit (conventional commits). | `python3 scripts/pro/commit_msg_validator.py <mensaje>` |
| `scripts/pro/compactador_espacios.py` | COMPACTADOR DE ESPACIOS - Reduce codigo Python 25-30% quitando huecos. | — |
| `scripts/pro/compactadora.py` | Compactadora Determinista — Reintegra código refactorizado. | — |
| `scripts/pro/compilador_opiniones.py` | compilador_opiniones.py — Compilador de opiniones con reparación JSON y reintent | — |
| `scripts/pro/conciencia.py` | Conciencia Unificada — Memoria global de todos los procesos del pipeline. | `python3 conciencia.py --leer                          # Ver ` |
| `scripts/pro/consolidacion.py` | Consolidación Automática — ciclo completo de calidad. | — |
| `scripts/pro/dashboard.py` | Dashboard de Salud de URA — métricas del sistema completo. | — |
| `scripts/pro/ejecutor_api.py` | ejecutor_api.py — Endpoint de automatizacion remota para URA. | — |
| `scripts/pro/f14_e2e.py` | F14 — Bloque 3: End-to-End (8 casos, componentes reales ≥70%). | — |
| `scripts/pro/f14_load_test.py` | F14 Load & Stress Test — Bloque 1. | `python3 scripts/pro/f14_load_test.py --benchmark L01 --level` |
| `scripts/pro/f14_profiling.py` | F14 — Bloque 4: Profiling (5 escenarios, detección de leaks y degradación). | — |
| `scripts/pro/f14_resilience.py` | F14 Resilience Tests — Bloque 2. | `python3 scripts/pro/f14_resilience.py           # ejecuta to` |
| `scripts/pro/f821_watch.py` | Monitoriza progreso de errores F821 (undefined name) via ruff. | `python3 f821_watch.py snapshot --label "antes-refactor"` |
| `scripts/pro/fix_masivo.py` | Fix masivo de errores ruff que requieren cambios estructurales. | `Ejecutar: python3 scripts/pro/fix_masivo.py` |
| `scripts/pro/generate_arch_diagram.py` | generate_arch_diagram.py — Genera diagrama Mermaid de la arquitectura URA. | — |
| `scripts/pro/gpu_health.py` | GPU Health Check — Detección temprana del bug de power cap (15W/650MHz). | `python3 gpu_health.py              → Salida legible` |
| `scripts/pro/hardening_audit.py` | hardening_audit.py — Audita el nivel de hardening de todos los servicios systemd | `Uso: python3 scripts/pro/hardening_audit.py` |
| `scripts/pro/index_golden_docs.py` | Create and index golden documents for KE evaluation corpus. | — |
| `scripts/pro/index_semantic_chunks.py` | Index golden documents with SemanticChunker for KE 2.0 comparison. | — |
| `scripts/pro/inspectores.py` | 10 Inspectores Paralelos — 120 checks de calidad en ~0.12s. | `python3 inspectores.py <archivo>` |
| `scripts/pro/inventario_f5.py` | Inventario reproducible de funciones de produccion (LOC y complejidad ciclomatic | `python3 scripts/pro/inventario_f5.py                # tabla ` |
| `scripts/pro/knowledge_engine.py` | Knowledge Engine — entry point. | — |
| `scripts/pro/lock_manager.py` | Lock Manager — Cerrojo de exclusión mutua para operaciones GPU. | — |
| `scripts/pro/master_conciencia.py` | master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan | — |
| `scripts/pro/mcp_mochila.py` | MCP stdio server wrapping mochila tools + HybridMemory for OpenClaw. | — |
| `scripts/pro/meta_mejora.py` | meta_mejora.py — URA mejora su propio prompt con medicion de impacto. | — |
| `scripts/pro/metrics_server.py` | metrics_server.py — URA Search Quality Dashboard. | — |
| `scripts/pro/openclaw_firmador.py` | openclaw_firmador.py — Agente-Firmador BLAKE2b (Protocolo de Control de Inodos). | — |
| `scripts/pro/openclaw_reviewer.py` | OpenClaw Reviewer — Revisor Independiente con qwen2.5-coder:q8_0. | `python3 openclaw_reviewer.py original.py refactorizado.py` |
| `scripts/pro/orchestrator.py` | Orquestador de health checks — ejecuta antes de push. | — |
| `scripts/pro/pareto_router.py` | Pareto Router — Distribución 20/80 de datos en el ecosistema URA. | `python3 scripts/pro/pareto_router.py --clasificar    # Clasi` |
| `scripts/pro/pipeline_refactor.py` | Pipeline de Refactorización — independiente, invocable desde mejora continua. | `python3 scripts/pro/pipeline_refactor.py [--workers 4] [--mo` |
| `scripts/pro/pipeline_supremo.py` | Pipeline Supremo — Orquestador completo de refactorizacion URA. | — |
| `scripts/pro/plugin_registry.py` | Plugin Registry — Auto-descubrimiento de scripts. | — |
| `scripts/pro/poda_mecanica.py` | Poda Mecánica + Anclaje Cromático — Fase 0 del Pipeline. | `python3 poda_mecanica.py <archivo> [--output <dir>] [--json]` |
| `scripts/pro/quality_gate.py` | Quality Gate: decide si el codigo es aceptable basado en reportes de la tunelado | — |
| `scripts/pro/refactor_large_functions_v2.py` | Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION. | — |
| `scripts/pro/refactor_v2.py` | (sin descripción) | — |
| `scripts/pro/reglas_applier.py` | Reglas Applier — Aplica reparaciones deterministas. | — |
| `scripts/pro/reglas_generator.py` | Reglas Generator — Auto-aprendizaje desde patrones. | — |
| `scripts/pro/reglas_loader.py` | Reglas Loader desde JSON. | — |
| `scripts/pro/reindex_vectors.py` | reindex_vectors.py — Reindexa todos los assets en el VectorStore. | `python3 scripts/pro/reindex_vectors.py [--db PATH] [--execut` |
| `scripts/pro/reuse/reuse.py` | Reuse Detector — busca código duplicado antes de crear código nuevo. | `python3 scripts/pro/reuse/reuse.py index             → index` |
| `scripts/pro/reuse/test_regression.py` | Regression tests para el Reuse Detector. | — |
| `scripts/pro/reuse_detector_plugin.py` | PLUGIN wrapper para ReuseDetector (plugin_registry solo escanea scripts/pro/). | — |
| `scripts/pro/revisor.py` | revisor.py — Interfaz controladora del Escudo de Auditoría URA. | `python3 scripts/pro/revisor.py --quick    # Ruff solo (<2s)` |
| `scripts/pro/router_rate_limiter.py` | Rate Limiter para Model Router - Previene abusos por IP. | — |
| `scripts/pro/sandbox_industrial.py` | Sandbox Industrial — Aislamiento total para reescritura masiva de archivos monst | — |
| `scripts/pro/sanear_codigo.py` | Sanear código automáticamente: corrige errores de ruff categoría por categoría. | `Uso: python3 scripts/pro/sanear_codigo.py [--check-only]` |
| `scripts/pro/scanner_autoajuste.py` | Scanner Auto-ajustable — ENTRADA + SALIDA con bucle cerrado. | `python3 scanner_autoajuste.py archivo.py           # Modo EN` |
| `scripts/pro/sincronizar_vocabulario.py` | Sincronización bidireccional SSH del vocabulario de corrección de voz entre Mac  | `*/5 * * * * /usr/bin/python3 /Users/ramonesnaola/URA/ura_ia_` |
| `scripts/pro/systemd_orphan_scanner.py` | systemd_orphan_scanner.py — Detect orphan systemd units (missing ExecStart). | `python3 scripts/pro/systemd_orphan_scanner.py            # d` |
| `scripts/pro/test_latencia_mac.py` | Benchmark de latencia del pipeline de voz en Mac mini M4. | `python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/test` |
| `scripts/pro/tests/test_logger_regression.py` | Test de regresión: Logger.warn() vs Logger.warning(). | — |
| `scripts/pro/token_screen.py` | Token Screen + RAM Guardian — Puerta de Entrada del Pipeline. | `python3 token_screen.py archivo.py          → Verifica si ha` |
| `scripts/pro/tools_index.py` | tools_index.py — Genera índice de todas las herramientas ejecutables del repo. | — |
| `scripts/pro/tuneladora/generate_index.py` | generate_index — indexa el código fuente en memoria semántica + repo_index.json. | — |
| `scripts/pro/tuneladora/install_service.py` | Instala el servicio systemd de la tuneladora. | — |
| `scripts/pro/tuneladora/preflight_system.py` | Pre-flight check: evita duplicados de servicios, puertos, screens. | — |
| `scripts/pro/tuneladora/scheduler_daemon.py` | Scheduler daemon — punto de entrada systemd para TuneladoraScheduler. | — |
| `scripts/pro/tuneladora/shadow/shadow_health.py` | Shadow Health — orquestador multi-capa de health checks para el pipeline. | — |
| `scripts/pro/tuneladora/tuneladora_pipeline.py` | CLI principal del pipeline tuneladora v7.0. | `python3 scripts/pro/tuneladora/tuneladora_pipeline.py --mode` |
| `scripts/pro/tuneladora_mantenimiento.py` | TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback. | — |
| `scripts/pro/tuneladora_mejora.py` | Tuneladora de Mejora Continua — v2.3 con checkpoint, ledger y presupuesto. | — |
| `scripts/pro/uitars_gx10.py` | uitars_gx10.py — UI-TARS para GX10 con fallback Ollama vision. | — |
| `scripts/pro/uitars_hetzner.py` | uitars_hetzner.py — UI-TARS en Hetzner conectado al monitor visual VNC. | — |
| `scripts/pro/ura_query.py` | URA RAG query — Contexto vectorial. | — |
| `scripts/pro/ura_self_modify.py` | ura_self_modify.py — Permite a URA modificar su propio prompt y tools. | — |
| `scripts/pro/ura_watch_asus.py` | ura_watch_asus.py — Vigila ASUS GX10 desde Mac, envía WoL si no responde. | — |
| `scripts/pro/watch_inbox.py` | Watchdog de inbox: detecta archivos nuevos → ingestar con retry + backoff. | — |
| `scripts/pro/watermark_aggregator.py` | Agregador de Watermarks — Detecta patrones sistémicos y gestiona incidencias. | `python3 watermark_aggregator.py                          # V` |
| `scripts/profile_startup.py` | Profile Startup — Diagnóstico de rendimiento de arranque. | — |
| `scripts/soak_test.py` | Soak Test (OBS-5) — test prolongado con datos sintéticos variados. | `python3 scripts/soak_test.py [--duration 3600] [--rate 10]` |
| `scripts/tests/stress_vram_guard.py` | Stress-test del ConcurrentVRAMGuard (asyncio.Semaphore 2). | `python3 scripts/tests/stress_vram_guard.py` |
| `scripts/trace-replay.py` | Trace Replay — reconstruye el recorrido completo de un trace_id (OBS-4). | `python3 scripts/trace-replay.py --trace <trace_id> <trace_fi` |
| `scripts/trace-viewer.py` | Trace Viewer (OBS-10) — generate HTML or JSON tree for a trace. | `python3 scripts/trace-viewer.py --trace <trace_id> <trace_fi` |
| `scripts/ura-stats.py` | ura-stats.py — Metricas del Guardian Post-Inferencia. | `python3 ura-stats.py --last 24h` |
| `scripts/watchdog_contraste.py` | Watchdog para proxy_contraste — restart automático si cae. | — |
| `tests/integration/test_openclaw.py` | Tests de integración — OpenClaw + SNC | — |
| `tests/legacy/test_sda.py` | Unit Test Suite — SDA (Sistema de Debate entre Agentes) | — |
| `tests/legacy/test_unit.py` | Unit Test Suite — URA v3.0 | — |
| `tests/unit/test_ast_sentinel.py` | Test AST Sentinel. | — |
| `tests/unit/test_memoria_fallos.py` | Test memoria_fallos. | — |
| `tests/unit/test_memoria_movimiento.py` | Test memoria_movimiento. | — |
| `tests/unit/test_mochila.py` | Test mochila_engine. | — |
| `tests/unit/test_prompt_injector.py` | Test Prompt Injector. | — |
| `tools/benchmarks/benchmark_baseline.py` | Run benchmark and compare against stored baseline (Fase 8 — B08). | `python3 scripts/pro/benchmark_baseline.py              # run` |
| `tools/benchmarks/benchmark_compare_chunking.py` | Compare KE 1.x (single-chunk) vs KE 2.0 (semantic chunking). | — |
| `tools/benchmarks/benchmark_f10_perf.py` | Benchmark F10-07: rendimiento comparativo baseline vs actual. | — |
| `tools/benchmarks/benchmark_f24.py` | Benchmark F24 — Web Intelligence end-to-end. | `python3 scripts/pro/benchmark_f24.py [--iterations 5]` |
| `tools/benchmarks/benchmark_f29_b2.py` | F29 B2 — Validación Técnica: benchmarks de throughput, latencia y memoria. | `python3 scripts/pro/benchmark_f29_b2.py [--output resultados` |
| `tools/benchmarks/benchmark_final_reranking.py` | Benchmark final: Vector-only vs Hybrid vs Hybrid+CrossEncoder vs Hybrid+LLM. | — |
| `tools/benchmarks/benchmark_final_retrieval.py` | 5-way benchmark: Vector-only vs Chunking vs Hybrid vs Hybrid+CE vs Hybrid+LLM. | — |
| `tools/benchmarks/benchmark_hybrid.py` | Benchmark: vectorial vs BM25 vs hybrid vs semantic chunking baseline. | — |
| `tools/benchmarks/benchmark_hybrid_refined.py` | Hybrid retrieval refinement: compare 5 fusion strategies to meet ADR-012-01. | — |
| `tools/benchmarks/benchmark_ke.py` | Benchmark KE 1.x retrieval quality and latency. | `python3 scripts/pro/benchmark_ke.py                         ` |
| `tools/benchmarks/benchmark_llm.py` | Benchmark del cliente LLM unificado (motor.core.llm). | `python3 scripts/pro/benchmark_llm.py [--iterations N] [--pro` |
| `tools/benchmarks/benchmark_qdrant.py` | benchmark_qdrant.py — 10 pruebas de estrés sobre Qdrant + RAG. | `Ejecutar: python3 scripts/pro/benchmark_qdrant.py.` |
| `tools/benchmarks/benchmark_rag.py` | Benchmark comparativo de estrategias de Retrieval. | `python3 scripts/pro/benchmark_rag.py --corpus corpus.json --` |
| `tools/benchmarks/benchmark_rerank.py` | Benchmark: vector-only vs hybrid vs hybrid+reranker. | — |
| `tools/benchmarks/benchmark_reranking.py` | Benchmark: Vector-only vs Hybrid vs Hybrid+Reranker (NoOp, LLM). | — |
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

### raíz/

- **`ura`** — URA CLI — Punto de entrada central (wrapper hacia motor/cli/main.py).
- **`ura_chat`** — CLI interactivo para el asistente conversacional.

### scraping/

- **`meta_miner_remote`** — Meta Miner Remoto — Extracción determinista de metadatos de código.

### scripts/

- **`generate_synthetic_data`** — Generador de datos sintéticos para pruebas de URA.
  - Uso: `python3 scripts/generate_synthetic_data.py --help`
- **`health_check_brain`** — Health check para motor/brain/ — verifica imports, instancias, hooks.
  - Uso: `python3 scripts/health_check_brain.py           # stdout`
- **`PLUGIN_TEMPLATE`** — PLUGIN_TEMPLATE — Copiar y modificar para crear un script nuevo.
- **`adr_generator`** — ADR Generator — Genera documentos de decisión automáticamente tras commits significativos.
- **`ajustar_contexto`** — Ajuste Dinámico de Contexto para Refactorización.
- **`alineador`** — alineador.py — Valida que las respuestas de URA/OpenClaw sean utiles y no se desvien.
- **`analisis_completo`** — analisis_completo.py — Analisis integral de URA (estado + monologo + acciones).
- **`analizar_fallo_conciencia`** — analizar_fallo_conciencia.py — Analiza resultados del test de conciencia
- **`arq_auditor`** — ARQ Auditor — auditoría arquitectónica automatizada (Bloques A–K).
  - Uso: `python3 scripts/pro/arq_auditor.py                    # informe completo`
- **`arq_checker`** — ARQ-600: Validación funcional automatizada.
  - Uso: `python3 scripts/pro/arq_checker.py                    # stdout`
- **`audit_config`** — Auditoría de configuración unificada (F17 scope).
  - Uso: `python3 scripts/pro/audit_config.py`
- **`audit_inventario`** — audit_inventario.py — Inventario automatizado de herramientas del repo.
  - Uso: `Uso: python3 scripts/pro/audit_inventario.py [--json data/inventario_herramienta`
- **`audit_secrets`** — Auditoría de secretos — detecta secretos hardcodeados, credenciales en
  - Uso: `python3 scripts/pro/audit_secrets.py`
- **`auditor_dormidos`** — (sin descripción)
- **`auditor_makefile`** — auditor_makefile.py — Auditoría de targets del Makefile (Fase 1 adaptada).
  - Uso: `Uso: python3 scripts/pro/auditor_makefile.py`
- **`auditor_real`** — auditor_real.py — Auditoría real de TODO el repo (Fase 1 adaptada).
  - Uso: `Uso: python3 scripts/pro/auditor_real.py`
- **`auditor_router`** — Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir.
  - Uso: `python3 scripts/pro/auditor_router.py              # Auditoría completa`
- **`auditoria_continua`** — Auditoría Continua — suite única de comprobaciones automáticas.
- **`auto_conciencia`** — auto_conciencia.py — URA se auto-evalua y autocorrige usando OpenClaw.
- **`auto_reglas`** — Auto-Reglas — Sistema de reparación auto-aprendida.
- **`autonomy`** — Autonomía v3.2 — orquestador multi-objetivo con planificación adaptativa.
- **`aprendizaje`** — Aprendizaje v4.0 — subsistema completo de aprendizaje avanzado.
- **`memoria`** — Memoria Semántica — capa de conocimiento sobre el ExecutionLedger.
- **`investigacion`** — Investigación Autónoma — genera hipótesis, busca evidencias, sintetiza conclusiones.
- **`swarm`** — Swarm URA — sistema multiagente coordinado.
- **`backup_assistant`** — Backup del asistente conversacional — DBs y configuración.
- **`backup_f26_memory`** — F29 B4 — Backup + Restore para F26 Memory.
  - Uso: `python3 scripts/pro/backup_f26_memory.py backup [--path /tmp/memory_backup.json]`
- **`captura_virtual`** — captura_virtual.py — Captura programatica en Xvfb :99.
- **`change_log`** — Unified Change Log — registro estructurado de cambios del repositorio.
  - Uso: `python3 scripts/pro/change_log.py --record <commit_hash>`
- **`chaos_f29_b5`** — F29 B5 — Chaos Tests (7 escenarios).
  - Uso: `python3 scripts/pro/chaos_f29_b5.py [--all | --ct N]`
- **`chaos_test`** — chaos_test.py — Ingeniería del caos para URA.
  - Uso: `python3 scripts/pro/chaos_test.py --list          # Listar tests disponibles`
- **`check_secrets`** — check_secrets.py — Pre-commit hook: detecta secrets hardcodeados.
- **`chunk_optimizer`** — Chunk Optimizer — Ajuste dinámico de tamaño según tasa de error.
  - Uso: `python3 chunk_optimizer.py --estado           # Ver estado actual`
- **`cleanup_assistant`** — Limpieza automática de conversaciones antiguas.
  - Uso: `Ejecutar diariamente: crontab -e → @daily python3 /path/to/cleanup.py`
- **`commit_msg_validator`** — Validador de mensajes de commit (conventional commits).
  - Uso: `python3 scripts/pro/commit_msg_validator.py <mensaje>`
- **`compactador_espacios`** — COMPACTADOR DE ESPACIOS - Reduce codigo Python 25-30% quitando huecos.
- **`compactadora`** — Compactadora Determinista — Reintegra código refactorizado.
- **`compilador_opiniones`** — compilador_opiniones.py — Compilador de opiniones con reparación JSON y reintentos.
- **`conciencia`** — Conciencia Unificada — Memoria global de todos los procesos del pipeline.
  - Uso: `python3 conciencia.py --leer                          # Ver estado general`
- **`consolidacion`** — Consolidación Automática — ciclo completo de calidad.
- **`dashboard`** — Dashboard de Salud de URA — métricas del sistema completo.
- **`ejecutor_api`** — ejecutor_api.py — Endpoint de automatizacion remota para URA.
- **`f14_e2e`** — F14 — Bloque 3: End-to-End (8 casos, componentes reales ≥70%).
- **`f14_load_test`** — F14 Load & Stress Test — Bloque 1.
  - Uso: `python3 scripts/pro/f14_load_test.py --benchmark L01 --levels 10,100,1000`
- **`f14_profiling`** — F14 — Bloque 4: Profiling (5 escenarios, detección de leaks y degradación).
- **`f14_resilience`** — F14 Resilience Tests — Bloque 2.
  - Uso: `python3 scripts/pro/f14_resilience.py           # ejecuta todos los escenarios`
- **`f821_watch`** — Monitoriza progreso de errores F821 (undefined name) via ruff.
  - Uso: `python3 f821_watch.py snapshot --label "antes-refactor"`
- **`fix_masivo`** — Fix masivo de errores ruff que requieren cambios estructurales.
  - Uso: `Ejecutar: python3 scripts/pro/fix_masivo.py`
- **`generate_arch_diagram`** — generate_arch_diagram.py — Genera diagrama Mermaid de la arquitectura URA.
- **`gpu_health`** — GPU Health Check — Detección temprana del bug de power cap (15W/650MHz).
  - Uso: `python3 gpu_health.py              → Salida legible`
- **`hardening_audit`** — hardening_audit.py — Audita el nivel de hardening de todos los servicios systemd URA.
  - Uso: `Uso: python3 scripts/pro/hardening_audit.py`
- **`index_golden_docs`** — Create and index golden documents for KE evaluation corpus.
- **`index_semantic_chunks`** — Index golden documents with SemanticChunker for KE 2.0 comparison.
- **`inspectores`** — 10 Inspectores Paralelos — 120 checks de calidad en ~0.12s.
  - Uso: `python3 inspectores.py <archivo>`
- **`inventario_f5`** — Inventario reproducible de funciones de produccion (LOC y complejidad ciclomatica).
  - Uso: `python3 scripts/pro/inventario_f5.py                # tabla markdown + totales`
- **`knowledge_engine`** — Knowledge Engine — entry point.
- **`lock_manager`** — Lock Manager — Cerrojo de exclusión mutua para operaciones GPU.
- **`master_conciencia`** — master_conciencia.py — Prueba todas las acciones de URA y verifica que funcionan.
- **`mcp_mochila`** — MCP stdio server wrapping mochila tools + HybridMemory for OpenClaw.
- **`meta_mejora`** — meta_mejora.py — URA mejora su propio prompt con medicion de impacto.
- **`metrics_server`** — metrics_server.py — URA Search Quality Dashboard.
- **`openclaw_firmador`** — openclaw_firmador.py — Agente-Firmador BLAKE2b (Protocolo de Control de Inodos).
- **`openclaw_reviewer`** — OpenClaw Reviewer — Revisor Independiente con qwen2.5-coder:q8_0.
  - Uso: `python3 openclaw_reviewer.py original.py refactorizado.py`
- **`orchestrator`** — Orquestador de health checks — ejecuta antes de push.
- **`pareto_router`** — Pareto Router — Distribución 20/80 de datos en el ecosistema URA.
  - Uso: `python3 scripts/pro/pareto_router.py --clasificar    # Clasificar datos del pipe`
- **`pipeline_refactor`** — Pipeline de Refactorización — independiente, invocable desde mejora continua.
  - Uso: `python3 scripts/pro/pipeline_refactor.py [--workers 4] [--model qwen2.5-coder:14`
- **`pipeline_supremo`** — Pipeline Supremo — Orquestador completo de refactorizacion URA.
- **`plugin_registry`** — Plugin Registry — Auto-descubrimiento de scripts.
- **`poda_mecanica`** — Poda Mecánica + Anclaje Cromático — Fase 0 del Pipeline.
  - Uso: `python3 poda_mecanica.py <archivo> [--output <dir>] [--json]`
- **`quality_gate`** — Quality Gate: decide si el codigo es aceptable basado en reportes de la tuneladora.
- **`refactor_large_functions_v2`** — Refactoriza funciones grandes (>80 lineas) usando LLM con COMPACTACION.
- **`refactor_v2`** — (sin descripción)
- **`reglas_applier`** — Reglas Applier — Aplica reparaciones deterministas.
- **`reglas_generator`** — Reglas Generator — Auto-aprendizaje desde patrones.
- **`reglas_loader`** — Reglas Loader desde JSON.
- **`reindex_vectors`** — reindex_vectors.py — Reindexa todos los assets en el VectorStore.
  - Uso: `python3 scripts/pro/reindex_vectors.py [--db PATH] [--execute] [--batch N]`
- **`reuse`** — Reuse Detector — busca código duplicado antes de crear código nuevo.
  - Uso: `python3 scripts/pro/reuse/reuse.py index             → indexar el proyecto`
- **`test_regression`** — Regression tests para el Reuse Detector.
- **`reuse_detector_plugin`** — PLUGIN wrapper para ReuseDetector (plugin_registry solo escanea scripts/pro/).
- **`revisor`** — revisor.py — Interfaz controladora del Escudo de Auditoría URA.
  - Uso: `python3 scripts/pro/revisor.py --quick    # Ruff solo (<2s)`
- **`router_rate_limiter`** — Rate Limiter para Model Router - Previene abusos por IP.
- **`sandbox_industrial`** — Sandbox Industrial — Aislamiento total para reescritura masiva de archivos monstruo.
- **`sanear_codigo`** — Sanear código automáticamente: corrige errores de ruff categoría por categoría.
  - Uso: `Uso: python3 scripts/pro/sanear_codigo.py [--check-only]`
- **`scanner_autoajuste`** — Scanner Auto-ajustable — ENTRADA + SALIDA con bucle cerrado.
  - Uso: `python3 scanner_autoajuste.py archivo.py           # Modo ENTRADA: capturar snap`
- **`sincronizar_vocabulario`** — Sincronización bidireccional SSH del vocabulario de corrección de voz entre Mac y ASUS.
  - Uso: `*/5 * * * * /usr/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/sin`
- **`systemd_orphan_scanner`** — systemd_orphan_scanner.py — Detect orphan systemd units (missing ExecStart).
  - Uso: `python3 scripts/pro/systemd_orphan_scanner.py            # default: --ura-only`
- **`test_latencia_mac`** — Benchmark de latencia del pipeline de voz en Mac mini M4.
  - Uso: `python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/test_latencia_mac.py`
- **`test_logger_regression`** — Test de regresión: Logger.warn() vs Logger.warning().
- **`token_screen`** — Token Screen + RAM Guardian — Puerta de Entrada del Pipeline.
  - Uso: `python3 token_screen.py archivo.py          → Verifica si hay RAM y ajusta conte`
- **`tools_index`** — tools_index.py — Genera índice de todas las herramientas ejecutables del repo.
- **`generate_index`** — generate_index — indexa el código fuente en memoria semántica + repo_index.json.
- **`install_service`** — Instala el servicio systemd de la tuneladora.
- **`preflight_system`** — Pre-flight check: evita duplicados de servicios, puertos, screens.
- **`scheduler_daemon`** — Scheduler daemon — punto de entrada systemd para TuneladoraScheduler.
- **`shadow_health`** — Shadow Health — orquestador multi-capa de health checks para el pipeline.
- **`tuneladora_pipeline`** — CLI principal del pipeline tuneladora v7.0.
  - Uso: `python3 scripts/pro/tuneladora/tuneladora_pipeline.py --mode check`
- **`tuneladora_mantenimiento`** — TUNELADORA DE MANTENIMIENTO — Flujo unificado con commit/rollback.
- **`tuneladora_mejora`** — Tuneladora de Mejora Continua — v2.3 con checkpoint, ledger y presupuesto.
- **`uitars_gx10`** — uitars_gx10.py — UI-TARS para GX10 con fallback Ollama vision.
- **`uitars_hetzner`** — uitars_hetzner.py — UI-TARS en Hetzner conectado al monitor visual VNC.
- **`ura_query`** — URA RAG query — Contexto vectorial.
- **`ura_self_modify`** — ura_self_modify.py — Permite a URA modificar su propio prompt y tools.
- **`ura_watch_asus`** — ura_watch_asus.py — Vigila ASUS GX10 desde Mac, envía WoL si no responde.
- **`watch_inbox`** — Watchdog de inbox: detecta archivos nuevos → ingestar con retry + backoff.
- **`watermark_aggregator`** — Agregador de Watermarks — Detecta patrones sistémicos y gestiona incidencias.
  - Uso: `python3 watermark_aggregator.py                          # Ver estado`
- **`profile_startup`** — Profile Startup — Diagnóstico de rendimiento de arranque.
- **`soak_test`** — Soak Test (OBS-5) — test prolongado con datos sintéticos variados.
  - Uso: `python3 scripts/soak_test.py [--duration 3600] [--rate 10]`
- **`stress_vram_guard`** — Stress-test del ConcurrentVRAMGuard (asyncio.Semaphore 2).
  - Uso: `python3 scripts/tests/stress_vram_guard.py`
- **`trace-replay`** — Trace Replay — reconstruye el recorrido completo de un trace_id (OBS-4).
  - Uso: `python3 scripts/trace-replay.py --trace <trace_id> <trace_file>`
- **`trace-viewer`** — Trace Viewer (OBS-10) — generate HTML or JSON tree for a trace.
  - Uso: `python3 scripts/trace-viewer.py --trace <trace_id> <trace_file> --html > trace.h`
- **`ura-stats`** — ura-stats.py — Metricas del Guardian Post-Inferencia.
  - Uso: `python3 ura-stats.py --last 24h`
- **`watchdog_contraste`** — Watchdog para proxy_contraste — restart automático si cae.

### tests/

- **`test_openclaw`** — Tests de integración — OpenClaw + SNC
- **`test_sda`** — Unit Test Suite — SDA (Sistema de Debate entre Agentes)
- **`test_unit`** — Unit Test Suite — URA v3.0
- **`test_ast_sentinel`** — Test AST Sentinel.
- **`test_memoria_fallos`** — Test memoria_fallos.
- **`test_memoria_movimiento`** — Test memoria_movimiento.
- **`test_mochila`** — Test mochila_engine.
- **`test_prompt_injector`** — Test Prompt Injector.

### tools/

- **`benchmark_baseline`** — Run benchmark and compare against stored baseline (Fase 8 — B08).
  - Uso: `python3 scripts/pro/benchmark_baseline.py              # run + compare`
- **`benchmark_compare_chunking`** — Compare KE 1.x (single-chunk) vs KE 2.0 (semantic chunking).
- **`benchmark_f10_perf`** — Benchmark F10-07: rendimiento comparativo baseline vs actual.
- **`benchmark_f24`** — Benchmark F24 — Web Intelligence end-to-end.
  - Uso: `python3 scripts/pro/benchmark_f24.py [--iterations 5]`
- **`benchmark_f29_b2`** — F29 B2 — Validación Técnica: benchmarks de throughput, latencia y memoria.
  - Uso: `python3 scripts/pro/benchmark_f29_b2.py [--output resultados.json]`
- **`benchmark_final_reranking`** — Benchmark final: Vector-only vs Hybrid vs Hybrid+CrossEncoder vs Hybrid+LLM.
- **`benchmark_final_retrieval`** — 5-way benchmark: Vector-only vs Chunking vs Hybrid vs Hybrid+CE vs Hybrid+LLM.
- **`benchmark_hybrid`** — Benchmark: vectorial vs BM25 vs hybrid vs semantic chunking baseline.
- **`benchmark_hybrid_refined`** — Hybrid retrieval refinement: compare 5 fusion strategies to meet ADR-012-01.
- **`benchmark_ke`** — Benchmark KE 1.x retrieval quality and latency.
  - Uso: `python3 scripts/pro/benchmark_ke.py                                    # full ru`
- **`benchmark_llm`** — Benchmark del cliente LLM unificado (motor.core.llm).
  - Uso: `python3 scripts/pro/benchmark_llm.py [--iterations N] [--provider ollama|openai]`
- **`benchmark_qdrant`** — benchmark_qdrant.py — 10 pruebas de estrés sobre Qdrant + RAG.
  - Uso: `Ejecutar: python3 scripts/pro/benchmark_qdrant.py.`
- **`benchmark_rag`** — Benchmark comparativo de estrategias de Retrieval.
  - Uso: `python3 scripts/pro/benchmark_rag.py --corpus corpus.json --retrievers bm25 sema`
- **`benchmark_rerank`** — Benchmark: vector-only vs hybrid vs hybrid+reranker.
- **`benchmark_reranking`** — Benchmark: Vector-only vs Hybrid vs Hybrid+Reranker (NoOp, LLM).
