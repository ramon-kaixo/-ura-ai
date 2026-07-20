# URA — AI Agent Instructions

## REGLA PRINCIPAL: SIEMPRE TRABAJAR EN ASUS (MEJORA CONTINUA)

**IMPORTANTE**: El código fuente principal está en ASUS (GX10) en `/home/ramon/URA/ura_ia_1972/`.

- **Mac** (`/Users/ramonesnaola/URA/ura_ia_1972/`) es solo para desarrollo ligero y sincronización
- **ASUS** (`/home/ramon/URA/ura_ia_1972/`) es el servidor de mejora continua donde debe ejecutarse todo
- Para sincronizar de Mac → ASUS: usar `scp` o `rsync` a `ramon@10.164.1.99`
- Para trabajar directamente en ASUS: usar `ssh ramon@10.164.1.99 "cd /home/ramon/URA/ura_ia_1972 && <comando>"`

### Flujo de Trabajo Obligatorio
1. **Desarrollar** en Mac (edithores, tests locales)
2. **Sincronizar** a ASUS cuando el código esté listo
3. **Ejecutar** y verificar en ASUS (el servidor real)
4. **NUNCA** dejar código sin sincronizar a ASUS por más de una sesión

## Project Context
URA is a multi-agent desktop assistant with specialized agents, a consciousness coordinator, a self-improving sandbox, and an autonomous swarm of research buzzers.

## Build & Test Commands
- Install: `pip install -r requirements.txt`
- Lint: `ruff check . && ruff format .`
- Test: `pytest -q` (needs hypothesis, pytest-asyncio, pytest-timeout)
- Full audit: `python3 /home/ramon/URA/ura_ia_1972/scripts/pro/pipeline_refactor.py --help`
- Demo: `bash scripts/demo.sh`
- Sandbox mejora: `docker exec sandbox-mejora-continua bash /workspace/tuneladora_mejora.sh`

## Architecture
- `core/` — Domain logic (consciousness, values, forensic scribe, rollback) + `core/qdrant_client.py` (regenerable, proxy hacia motor/)
- `motor/` — Motor framework + `motor/core/config.py` (UraConfig único, fuente de verdad)
- `agents/` — Specialized agents (organized by domain in subdirectories for new additions)
- `adapters/` — (no creado aún). External connectors: `core/mochila/providers/` (Ollama, Gemini, Groq, DeepSeek, OpenRouter), `core/notifier.py` (Telegram, Pushover), `knowledge/engine/notify.py` (Slack, Email)
- `knowledge/` — Long-term memory, document fragments, knowledge base, vectorizar_docs
- `knowledge/engine/` — Knowledge Engine (Fases 0-7). Almacenamiento, indexado, lineage, memoria, vectorial, FTS5
- `scripts/pro/` — Scripts de pipeline, utilidades y automatización (~146 archivos)

## Fases

| Fase | Estado | Entrega |
|------|--------|---------|
| 0–6 | ✅ Cerradas | FTS5, edges, background queue, autorecuperación, reconcile |
| **7** | ✅ **Cerrada** (v3.0) | Optimizaciones Producción. Tag `v0.6.0-fase7`. 16 correcciones. PHASE7_CLOSEOUT.md |
| **8** | ✅ **Cerrada** | Hardening, Cobertura y Documentación. 10 correcciones. `docs/architecture/FASE8_DESIGN.md` |
| **Auditoría Post-Fase 8** | ✅ **Cerrada** | Saneamiento arquitectónico: unificación config, eliminación código muerto, actualización docs. Tag `v0.7.1-audit-fase8`. `docs/architecture/AUDIT_FASE8_CLOSEOUT.md` |
| **15** | ✅ **Cerrada** | Migración HTTP (Ollama) — `core/debate/debate_engine.py`, `core/ura_multi_agent.py`. Tag `v0.15.0-fase15` |
| **16** | ✅ **Cerrada** | Empaquetado y Deuda — eliminar dependencias rotas, tests actualizados. Tag `v0.16.0-fase16` |
| **17** | ✅ **Cerrada** | Configuración Unificada — UraConfig como vista de CONFIG. 0 new ruff, 0 pytest regressions. Tag `v0.17.0-fase17`. Ver `docs/architecture/FASE17_PROPOSAL.md` |
| **17.5** | ✅ **Cerrada** | Gestión de Secretos — `motor/core/secrets.py`, 15 consumidores migrados, auditoría automática. Tag `v0.17.5-f17.5`. Ver `docs/architecture/SECRETS.md` |

### Backlog Deuda Técnica (Cerrado Post-F29)

Todos los items T01-T09 fueron auditados/resueltos el 2026-07-19 (commits `c888dce`, `8ba50ca`).

| ID | Ítem | Prioridad | Estado |
|----|------|-----------|--------|
| T01 | `core/synonyms.json` con `chattr +i` en disco | Mínima | ✅ Resuelto — `sudo chattr +i` ejecutado en GX10 |
| T02 | `scripts/pro/sanear_codigo.py:50` syntax error | Baja | ✅ Resuelto (no había error real) |
| T03 | 12 archivos .py con caracteres no-ASCII en nombre | Baja | ✅ Resuelto (0 archivos encontrados) |
| T04 | 5 tests CLI fallan por dependencias del entorno | Baja | ✅ Resuelto (`test_unit.py` sys.exit envuelto en `__name__ == '__main__'`) |
| T05 | FTS schema verifier falso positivo (tablas extrañas) | Media | ✅ Resuelto (`sqlite_stat*` ignorados en `storage_verifier.py:57-59`) |
| T06 | ~2.356 lint errors pre-existentes (ruff all rules) | Baja | ✅ Resuelto — 0 errores (2356 → 0, commit `8ba50ca`) |
| T07 | `adapters/` directorio nunca creado | Informativa | ℹ️ Informativo — creado como `motor/platform/adapters/` |
| T08 | 14 bloques `except: pass` validados (degradación controlada) | Mínima | ✅ Resuelto (F28.1 añadió logging en `motor/platform/`) |
| T09 | ~80+ bloques `except: pass` sin auditar | Media | ✅ Resuelto (26 en `knowledge/engine/` auditados — 100% degradación controlada, `# noqa` añadido) |

### Regla Global de No Regresión

Ninguna fase podrá degradar rendimiento, calidad o funcionalidad respecto al
baseline de la fase anterior sin documentarlo y justificarlo en el Closeout.

### Regla Transversal (Fases 10–13)

No abrir una fase nueva sin haber cerrado la anterior mediante:

| Paso | Requisito |
|------|-----------|
| Validación completa | Checklist de cierre (compilación, lint, tests, smoke) |
| Actualización de documentación | AGENTS.md + propuesta de fase reflejan estado real |
| Comparación con baseline | 0 regresiones funcionales vs commit/tag de inicio |
| Tag de versión | `git tag -a vX.Y.Z-faseN` |
| Acta de cierre | `docs/architecture/FASEN_CLOSEOUT.md` actual |

### Fase 9 — Plan de Ejecución (Aprobado, v3.0)

Ver `docs/architecture/FASE9_PROPOSAL.md` para especificación completa.

**Orden de ejecución:** C → B → D → A → E (revisado: B antes que D, A al final)

| Stream | Descripción | Esfuerzo | Estado |
|--------|-------------|----------|--------|
| C | Modo degradado explícito (DegradedMode, /api/v1/status) | 2-3h | ✅ COMPLETADO |
| B | Modularidad: executor.py, plugin system via importlib, kill shell=True | 8-13h | ✅ COMPLETADO |
| D | Refactor CLI: extraer ura.py a motor/cli/, console_scripts | 3-5h | ✅ COMPLETADO |
| A | Calidad: unificar runners, reorganizar tests, Makefile | 2-3h | ✅ COMPLETADO |
| E | Validación final: baseline, benchmarks, smoke tests, tag | 1-2h | ✅ COMPLETADO |

**Regla:** `ura.py` se mantiene como wrapper durante Fase 9 (no se elimina).
**Cobertura:** No se fuerza umbral mínimo hasta que la cobertura real haya mejorado.
**Criterio:** Solo trabajo con impacto funcional o arquitectónico. Deuda técnica residual fuera.

### Stream E — Checklist de Validación Final (Obligatorio)

| # | Check | Criterio |
|---|-------|----------|
| E.1 | Compilación completa | `py_compile` 0 errores en todos los módulos tocados |
| E.2 | Ruff sin errores nuevos | `ruff check` — 0 errores nuevos vs baseline |
| E.3 | Pytest con nuevo recuento | `pytest -q` — mismo resultado que baseline (sin regresiones) |
| E.4 | Smoke tests CLI | `ura.py help/status/doctor/finalize --help` funcionan |
| E.5 | Smoke tests API | `ejecutor_api` endpoints /health, /api/v1/status responden |
| E.6 | Descubrimiento de plugins | `PluginRegistry.scan()` encuentra plugins sin errores |
| E.7 | Verificación de DegradedMode | `DegradedMode` inicializa, degrada, restaura correctamente |
| E.8 | Comparación con baseline | diff de tests vs baseline commit (`0d5aed7`) |
| E.9 | Working tree limpio | `git status` sin cambios sin commitear |
| E.10 | Documentación sincronizada | AGENTS.md + FASE9_PROPOSAL.md reflejan estado real |

### Pipeline Activo (scripts/pro/)
**~146 archivos** entre scripts Python, shell, servicios, configs y utilidades.
Organizados por función en las siguientes categorías:

| Categoría | Scripts | Propósito |
|-----------|---------|-----------|
| **Tuneladora** | `tuneladora_mantenimiento.py`, `tuneladora_mejora.py` | Pipeline de mejora continua (v2, motor compartido) |
| **Diagnóstico/Mantenimiento** | `token_screen.py`, `scanner_autoajuste.py`, `chunk_optimizer.py`, `poda_mecanica.py`, `watermark_aggregator.py`, `inspectores.py`, `compactadora.py`, `compactador_espacios.py`, `auto_reglas.py`, `reglas_loader.py`, `f821_watch.py`, `analizar_fallo_conciencia.py`, `master_conciencia.py`, `sincronizar_vocabulario.py`, `patch_timestamps.py`, `fix_masivo.py`, `hardening_audit.py`, `systemd_orphan_scanner.py` | Auditoría, reparación y optimización automática del código |
| **Refactor** | `refactor_large_functions.py`, `refactor_large_functions_v2.py`, `refactor_v2.py`, `refactor_4_motores.py`, `ajustar_contexto.py`, `sanear_codigo.py` | Refactorización con LLM + compactación |
| **Consciencia/Memoria** | `conciencia.py`, `auto_conciencia.py`, `analisis_completo.py`, `ura_self_modify.py` | Sistema de memoria, auto-conciencia y meta-mejora |
| **Model Router** | `auditor_router.py`, `router_rate_limiter.py`, `pareto_router.py`, `meta_mejora.py` | Gestión y auditoría del Model Router |
| **OpenClaw** | `openclaw_reviewer.py`, `openclaw_firmador.py`, `alineador.py`, `openclaw_netlock.sh` | Integración con OpenClaw (revisor, firmador, alineador) |
| **Ejecución/Servicios** | `ejecutor_api.py`, `pipeline_supremo.py`, `plugin_registry.py`, `PLUGIN_TEMPLATE.py`, `mcp_mochila.py`, `reglas_applier.py`, `reglas_generator.py` | APIs, pipeline y registro de plugins |
| **Sandbox** | `sandbox_industrial.py`, `jaulas_recursos.sh`, `deploy_sandbox_gx10.sh` | Sandbox de pruebas y límites de recursos |
| **Utilidades** | `utils.py`, `check_secrets.py`, `revisor.py`, `generate_arch_diagram.py`, `captura_virtual.py`, `compilador_opiniones.py`, `test_latencia_mac.py`, `ura_watch_asus.py`, `watch_inbox.py`, `knowledge_engine.py`, `benchmark_baseline.py`, `benchmark_qdrant.py`, `chaos_test.py`, `metrics_server.py`, `reindex_vectors.py` | Utilidades varias, benchmarks y monitoreo |
| **GPU/Sistema** | `gpu_health.py`, `gpu_recovery.sh`, `lock_manager.py`, `ura-system-health.sh`, `health_check.sh`, `health_check_router.sh`, `monitoreo_urgente.sh`, `watchdog_buffer.sh` | Health checks GPU y del sistema |
| **Red/Backup** | `ura_ojos.sh`, `ura-exit-node.sh`, `gx10_sync.sh`, `gx10_sync_final.sh`, `cross_trace.sh`, `sync_knowledge.sh`, `sync_ura.sh`, `notify_on_change.sh`, `backup_unified.sh`, `backup_gx10_configs.sh`, `safe_rollback.sh`, `shadow_git_rollback.sh` | Sincronización, backup y rollback |
| **Hetzner** | `deploy_to_hetzner.sh`, `asus_connect_hetzner.sh`, `heartbeat_hetzner.sh`, `hetzner_watchdog.sh`, `rescue_hetzner.sh`, `install_tailscale_hetzner.sh`, `orquestar_auditoria_hetzner.sh`, `pull-from-hetzner.sh`, `redirect_mejora_gx10.sh`, `backup_hetzner_to_asus.sh`, `uitars_hetzner.py` | Gestión del nodo Hetzner |
| **Auditoría** | `auditoria.sh`, `auditoria_pesada.sh`, `auditoria_qwen.sh`, `auditoria_comite.sh`, `phase1_diagnosis.sh`, `phase2_filter.sh`, `phase3_architecture.sh`, `phase4_rollback.sh`, `dr_test.sh`, `fpfn_report.sh`, `fn_scanner.sh`, `fp_scanner.sh`, `false_positive_baseline.sh`, `quality_metrics.sh`, `check_licenses.sh`, `audit_trail_check.sh` | Auditorías, quality metrics y disaster recovery |
| **RPA/Cámaras** | `bypass_linksys_gui.py`, `rpa_linksys.py`, `rpa_linksys_v2.py`, `rpa_zte_f6640.py`, `deploy_camaras.sh`, `desplegar_dahua_supervisor.sh`, `instalar_servidor_camaras.sh`, `guardian_tmpfs.sh`, `ura-telemetry-pos.ps1` | Automatización RPA, cámaras Dahua y telemetría POS |
| **Instalación/Deploy** | `instalar_gx10_circuit.sh`, `integracion_opencode.sh`, `conceder_permisos_accesibilidad.sh`, `mcp_config.sh`, `setup_logrotate_newsyslog.sh`, `patch_systemd_limits.sh`, `deploy_copilotos.sh`, `stage_hardening.sh`, `upgrade_pipeline.sh`, `detect_environment.sh`, `trampa_rm.sh` | Instalación, hardening y despliegue |
| **Pipeline Voz/Visión** | `demo_pipeline_voz.py`, `demo_pipeline_mac.py`, `com.ura.voice.plist`, `seed_correcciones_voz.py`, `daemon_procesamiento_lento.sh`, `supervisor_ciclo.sh` | Pipelines de voz y procesamiento lento |
| **Evolución/Ciclo** | `evolve.sh`, `ciclo_rapido.sh`, `filtro_cascada.sh`, `conflict_detector.sh`, `conectar_servidor_externo.sh`, `descubrir_puertos.sh`, `maquinas.sh`, `auto_export_context.sh` | Ciclos de evolución y detección de conflictos |
| **Config/Templates** | `tailscale-acls.json`, `crontab_gpu_health.txt`, `docker-compose.gx10-sandbox.yml`, `gx10-api.service`, `ura-mkdocs.service`, `DEPLOY_MAC.md`, `rotate_secrets.sh` | Configuraciones y templates |
| **ura-query** | `ura-query.py` | Consulta vectorial del grafo indexado |

### Scripts Archivados/Fusionados
- `ciclo_autonomo_gx10.py` → fusionado con `tuneladora_mantenimiento.py`
- `meta_mejora_real.py` → fusionado con `meta_mejora.py`
- `analisis_llm.py` + `meta_mejora_v2.py` + `reflexion_ura.py` → fusionado en `analisis_completo.py`
- `refactor_watchdog.py` → fusionado con `tuneladora_mejora.py`
- `auto_aplicar_mejoras.py` → fusionado en `ura_self_modify.py`
- `reflexion_profunda.py` → fusionado en `analizar_fallo_conciencia.py`
- `translate_to_english.py` → eliminado (código en inglés)
- `ia-flujo.service` → eliminado (app/flujo_constante.py nunca existió)
- 34 scripts huérfanos → `.nervioso/descarte/`

## GX10 (ASUS GB10) — Estado Real (2026-06-24)

### Hardware NVIDIA GB10 Grace Blackwell Superchip
- **CPU**: 20 núcleos ARM nativos de alto rendimiento
- **GPU**: NVIDIA Blackwell (FP4/FP8 dedicada para IA)
- **Memoria**: 128 GB Unificada (Unified Memory Architecture) vía NVLink-C2C
- **Optimización**: Aprovechamiento máximo de memoria unificada entre CPU y GPU

### Servicios systemd (REALES - Sistema)
| Servicio | Puerto | Estado | Tipo | Notas |
|---|---|---|---|---|
| `ollama` | 11434 | ✅ activo | systemd | Sistema base, 2 paralelas, keep-alive 1m |
| `ura-openclaw` | 18789 | ✅ activo | systemd | Gateway MCP (hardening: CPUQuota=40%, MemoryMax=2G) |
| `ura-api` | 8000 | ✅ activo | systemd | URA GX10 API — Remote endpoint with post-crash audit gate |
| `ura-audit-api` | 8080 | ✅ activo | systemd | URA Audit API (FastAPI) |
| `ura-contraste` | 8002 | ✅ activo | systemd | Proxy de Contraste + Telemetría POS (POST /api/v1/telemetry + GET /metrics) |
| `ura-go2rtc` | 1984 | ✅ activo | systemd | go2rtc Camera Stream Proxy |
| `ura-heartbeat` | - | ✅ activo | systemd | URA Mochila Heartbeat — reinicio automático si /health falla |
| `ura-metrics` | 8888 | ✅ activo | systemd | URA Metrics Server |
| `ura-mkdocs` | - | ✅ activo | systemd | URA MkDocs — Base de Conocimiento y Autopsias |
| `ura-mochila` | - | ✅ activo | systemd | Servicio Router Mochila - Servidor API FastAPI |
| `ura-ssh-guard` | - | ✅ activo | systemd | URA SSH Guard |
| `ura-voice` | - | ✅ activo | systemd | URA Voice Agent Pipeline (Anker S500 + Whisper GPU + Piper TTS) |
| `ura-watchdog-buffer` | - | ✅ activo | systemd | URA Watchdog de Buffer de 30GB |
| `ura-watcher` | - | ✅ activo | systemd | URA Watcher — Indexación sectorizada en tiempo real |
| `ura-watcher-auditoria` | - | ✅ activo | systemd | URA Watcher Auditoria — Dispara auditoria al recibir datos |
| `ura-xvfb` | - | ✅ activo | systemd | URA Xvfb Virtual Display |
| `ura-agent-hierarchy` | - | ❌ fallido | systemd | URA Agent Hierarchy System |
| `ura-aspirador` | - | ❌ fallido | systemd | URA Aspirador — vectorize downloaded files |
| `ura-detector` | - | ❌ fallido | systemd | URA YOLOv8 Detector + ByteTrack + Behavior Analysis |
| `ura-fix-x11-socket` | - | ❌ fallido | systemd | URA Fix X11 socket directory |
| `ura-hetzner-tunnel` | - | ❌ fallido | systemd | URA SSH Tunnel to Hetzner |
| `ura-historiador` | - | ❌ fallido | systemd | URA Historiador — registra acciones en Qdrant |
| `ura-procesamiento-lento` | - | ❌ fallido | systemd | URA Daemon de Procesamiento Lento (10% CPU) |
| `ura-router-health` | - | ❌ fallido | systemd | URA Model Router Health Check |

### Servicios systemd (REALES - Usuario)
| Servicio | Puerto | Estado | Tipo | Notas |
|---|---|---|---|---|
| `model-router` | 11435 | ✅ activo | systemd user | URA Model Router Enhanced (cache 5min, Connection: close) |
| `backend@qwen2.5-coder-32b` | - | ✅ activo | systemd user | Backend llama.cpp para modelo qwen2.5-coder-32b |
| `backend@qwen2.5-coder-q8_0` | - | ✅ activo | systemd user | Backend llama.cpp para modelo qwen2.5-coder-q8_0 |

### Ollama Optimizado (2026-06-03)
- **Configuración**:
  - `OLLAMA_NUM_PARALLEL=1` (serializado para modelos pesados)
  - `OLLAMA_MAX_LOADED_MODELS=1` (1 modelo en memoria)
  - `OLLAMA_MAX_QUEUE=2` (backpressure)
  - `OLLAMA_KEEP_ALIVE=5m` (persistencia en RAM)
  - `OLLAMA_FLASH_ATTENTION=1` (aceleración hardware)
  - `OLLAMA_NOPRUNE=1` (sin poda de modelos)
  - `OLLAMA_NUM_THREADS=20` (todos los cores)
  - `MemoryHigh=64G` (límite de RAM para modelos grandes)
- **Ubicación**: Sistema base Ubuntu (no en Docker)
- **Acceso GPU**: Memoria unificada 128 GB
- **Problema resuelto**: Model Router optimizado (cache 5min, Connection: close)

### Model Router Enhanced v2.0
- **Ubicación**: `/home/ramon/URA/core/model_router.py`
- **Features**: Prompt caching (2h TTL), Fallback system, Metrics
- **Configuración**: `THREADS = 20` (20 núcleos ARM)
- **Estado**: ✅ activo (arreglado para no crear zombies)
- **Optimizaciones**: Cache aumentado de 30s a 5min, header Connection: close
- **Endpoint métricas**: `http://10.164.1.99:11435/metrics`
- **Rutas configuradas**:
  - `razonamiento` → qwen3:32b-q8_0, qwen3:14b, llama3.3:70b, deepseek-coder:6.7b
  - `codigo_complejo` → qwen2.5-coder:32b, qwen2.5-coder:q8_0, qwen2.5-coder:14b
  - `codigo_rapido` → qwen2.5:7b, llama3.2:3b, deepseek-coder:6.7b
  - `respuesta_rapida` → qwen2.5:7b, llama3.2:3b, llama3.2:1b
  - `vision` → llama3.2-vision:11b, llava:34b, llava:13b
  - `embeddings` → nomic-embed-text:latest, mxbai-embed-large

### OpenClaw Integration (Systemd — 2026-06-20)
- Gateway: `http://10.164.1.99:18789`
- Servicio: **`ura-openclaw.service`** (systemd nativo con hardening)
  - `CPUQuota=40%`, `MemoryHigh=1.5G`, `MemoryMax=2G`
  - `PrivateTmp=true`, `ProtectSystem=full`
  - `Restart=on-failure` con `RestartSec=10`
  - `ExecStartPre`: curl retry 30x a Ollama (espera cold-boot de LLM, 42GB)
  - `TimeoutStartSec=180`: evita SIGKILL del systemd durante carga de pesos GPU
- Binario: `/usr/bin/node /usr/lib/node_modules/openclaw/dist/index.js gateway --port 18789`
- MCP: Configurado en OpenCode (Mac) como remote
- Skills habilitados: github, coding-agent
- CLI emergencia: `/usr/local/bin/openclaw-admin`
- Sandbox coding-agent: `/usr/local/bin/coding-agent-sandbox`
- **Orquestación visual**: n8n (Docker) consume API OpenClaw para tareas multi-agente
- **Métricas**: Prometheus (Docker) lee latencia/tokens de Open WebUI + ura-audit-api

### URA Contrast Proxy + Telemetría POS (Port 8002)
- **Servicio**: `ura-contraste.service` (systemd, tipo simple, User=ramon)
- **Binario**: `/home/ramon/.local/bin/uvicorn proxy_contraste:app --host 0.0.0.0 --port 8002`
- **⚠️ Prerrequisito externo**: `proxy_contraste.py` vive en `/opt/ura/agents/` fuera del repo. No está en el repositorio por contener tokens de acceso (Bearer). Instalación manual requerida.
- **Environment**: `/etc/ura/fix-path.conf` (PYTHONPATH=/opt/ura/agents, PATH con ~/.local/bin)
- **Endpoints**:
  - `GET /health` — Health check básico
  - `POST /v1/chat/completions` — Proxy de contraste (OpenAI/Anthropic, Bearer auth)
  - `POST /api/v1/telemetry` — Ingesta de telemetría POS (Bearer token, Pydantic validated)
  - `GET /metrics` — Exposición Prometheus OpenMetrics nativo
- **Autenticación**: Bearer token `URA_SECRET_NODE_TOKEN_HASH_XYZ` en cabecera Authorization
- **Flujo de datos**: `PowerShell (caja0) → Bearer → proxy_contraste:8002 → Prometheus scrape → alert.rules`
- **Dependencias**: `tailscaled.service` (resolución MagicDNS para caja0)
- **Deploy**: `scripts/deploy/ura-contraste.service` + `scripts/deploy/fix-path.conf` + `scripts/deploy/transition_contraste.sh`

### Prometheus + Alertas (Docker)
- **Servicio**: `ura-prometheus` (Docker, container `prom/prometheus:latest`)
- **Red**: bridge (172.17.0.0/16), mapeo puerto 127.0.0.1:9093:9090
- **Config**: `/home/ramon/docker/prometheus/prometheus.yml`
- **Reglas**: `/home/ramon/docker/prometheus/alert.rules`
- **Alertas activas**:
  - `NodoPerifericoDesconectado` (critical) — `time() - nodo_last_seen_timestamp_seconds > 90` por 1m
  - `ServiceDown` (critical) — detecta servicios URA caídos
- **UFW**: Regla `allow from 172.17.0.0/16 to any port 8002` para scrape desde Docker

### Pipeline de Visión por Computadora
```
Cámaras (RTSP/HTTP) → YOLOv8-Nano + ByteTrack → Qwen2-VL → Dashboard :9092
```
- `ura-detector.service` — YOLOv8-Nano + ByteTrack + Behavior Analysis
- `llama-vision.service` — llama.cpp Vision Model for URA (Qwen2-VL-7B)
- Crops enviados cada 10s a Qwen2-VL para clasificar
- Dashboard web en `http://GX10_IP:9092`

### Modelos en Ollama (REALES)
- `nomic-embed-text:latest` (embeddings) - 274 MB
- `llama3.3:70b` (tareas complejas) - 42 GB
- `qwen2.5-coder:14b` (código) - 9.0 GB
- `qwen2.5:7b` (código rápido, respuestas) - 4.7 GB
- `deepseek-coder:6.7b` (código alternativo) - 3.8 GB
- `llama3.2-vision:11b` (visión) - 7.8 GB
- `qwen3:32b-q8_0` (razonamiento profundo) - 34 GB
- `qwen2.5-coder:32b` (código complejo) - 19 GB
- `codestral:22b` (código alternativo) - 12 GB
- `qwen2.5-coder:q8_0` (código complejo) - 34 GB

### Red
- GX10: Ethernet 10.164.1.99, WiFi 10.164.1.247, Tailscale 100.72.103.12
- Mac: Ethernet 10.164.1.26, WiFi 10.164.1.0, Tailscale 100.123.81.101
- Linksys Velop MX4200: 10.164.1.1 (lighttpd+JNAP API, cloud-managed)
- Cámaras en 192.168.1.x/2.x/3.x — **no accesibles desde GX10** (router bloquea)

### Ubicaciones de Directorios
- **GX10**: `/home/ramon/URA/` (código principal)
- **GX10**: `/home/ramon/URA/ura_ia_1972/` (repositorio principal)
- **Mac**: `/Users/ramonesnaola/URA/` (sincronización, desarrollo ligero)
- **Mac**: `/Users/ramonesnaola/URA/backups_gx10/` (backups desde GX10)

### Tuneladora Unificada
- **Ubicación**: `/home/ramon/URA/ura_ia_1972/scripts/pro/tuneladora_mantenimiento.py`
- **Fases**: 6 fases unificadas (Diagnóstico, Mantenimiento, Auditoría Modelos, Mejora, Rollback, Backup)
- **Timer**: `ura-maintenance-v2.timer` - ejecuta cada 6 horas (00,06,12,18)
- **Rutas corregidas**: Usa `/home/ramon/URA/` (no `/opt/ura/`)
- **Sin teatro**: `|| true` eliminados de pasos críticos

### Sandbox Containers
| Container | Propósito | Estado |
|---|---|---|
| `sandbox-mejora-continua` | Ruff + pytest + bandit en `/workspace` | ✅ activo (python:3.11-slim) |
| `ura-sandbox-mantenimiento` | Mantenimiento del sistema | ⚠️ inactivo |
| `ura-sandbox-documentacion` | MkDocs :8087 | ⚠️ inactivo |
| `ura-sandbox-exploracion` | Exploración autónoma | ⚠️ inactivo |
| `ura-sandbox-aprendizaje` | Aprendizaje continuo | ⚠️ inactivo |
| `ura-sandbox-seguridad` | Auditoría de seguridad | ⚠️ inactivo |
| `ura-coding-agent-sandbox` | Aislamiento de coding-agent (Docker) | ⚠️ inactivo |

## Core Modification Rule (ADR-007)
The core (`core/`) is NOT frozen, but modifications require an ADR with:
- **Justification of necessity**: must demonstrate the change cannot be achieved via Protocol, EventBus subscriber, or external adapter
- **Migration + rollback plan**: every core change must be reversible
- **Degradation**: system must work without the modification
- **Mandatory second-party review**: no autonomous core modifications
- **Semantic freezing**: observable behavior of existing functions may not change, even if signature stays the same
- ✅ Allowed: Adding optional fields to `UraConfig`, new event topics, hooks/callbacks (backward-compatible, degradable)
- ❌ Prohibited: Refactoring/renaming existing symbols, changing method signatures, changing observable behavior, deleting functionality, modifications achievable via Protocol/EventBus instead
- See `docs/architecture/ADR-007-REGLA_NUCLEO.md` for the full policy

## Naming Conventions
- Files: kebab-case for new files (e.g., `ura-panel.py`, `buzo-academico.sh`)
- Directories: kebab-case (e.g., `agents/cocina/`, `knowledge/fragmentos/`)
- Dates: ISO 8601 (YYYY-MM-DD)
- Artifacts: SLUG prefix (e.g., `audit-report-2026-05-17.md`)

## Security Rules
- No `shell=True` in subprocess calls
- No hardcoded secrets (use Boveda or environment variables)
- All autonomous changes go through sandbox + rollback
- Network allowlist for sandbox containers
- **EXCEPCIÓN**: `allowInsecureAuth=true` en opencode para acceso HTTP desde Mac (documentado en SECURITY_EXCEPTIONS.md)
- **BACKUP**: Script `/opt/ura/scripts/backup_to_mac.sh` + cron job diario 03:00 (requiere configuración SSH manual)

## Code Style
- Ruff with ALL rules enabled
- Type hints required for all new functions
- Agent classes should inherit from existing base patterns
- Docstrings in Google style

## Key Files
- `AGENTS.md` — This file (AI instructions)
- `README.md` — Human-readable project overview
- `pyproject.toml` — Python project configuration
- `CLAUDE.md` — Symlink to AGENTS.md (Claude Code compatibility)
- `/home/ramon/URA/ura_ia_1972/scripts/pro/tuneladora_mantenimiento.py` — Tuneladora de mantenimiento (v2, motor compartido)
- `/home/ramon/URA/core/model_router.py` — Model Router Enhanced
- `docs/architecture/FASE8_DESIGN.md` — Fase 8 design document (live)
- `docs/architecture/PHASE7_CLOSEOUT.md` — Fase 7 closeout (v3.0)
- `/opt/ura/config/go2rtc.yaml` — 30 streams de 15 cámaras Dahua
- `SECURITY_EXCEPTIONS.md` — Documentación de excepciones de seguridad
- `core/config.py` — UraConfig (eliminado post-Fase 8; usar `motor/core/config.py`)
- `motor/core/config.py` — UraConfig único (fuente de verdad)
- `core/qdrant_client.py` — Proxy hacia motor.core.qdrant_client (regenerable)
- `scripts/pro/lock_manager.py` — Cerrojo GPU (flock/fcntl para colisión tuneladora/crontab)
- `scripts/pro/gpu_health.py` — Detector power cap GB10 (15W/650MHz)
- `scripts/pro/gpu_recovery.sh` — Recuperación automática de drivers NVIDIA (regex `^P(0|2|8|12)$`)
- `scripts/pro/tailscale-acls.json` — Política de aislamiento perimetral Tailscale
- `scripts/pro/ura-telemetry-pos.ps1` — Agente de telemetría para caja0 (Windows POS)
- `scripts/pro/crontab_gpu_health.txt` — Crontab de auditoría GPU cada 30 min
- `scripts/deploy/fix-path.conf` — Environment file para ura-contraste.service
- `scripts/deploy/ura-contraste.service` — Unidad systemd oficial del proxy de contraste
- `scripts/deploy/transition_contraste.sh` — Script de transición watchdog→systemd (auto-deploy)
- `deploy/ura-openclaw.service` — Unidad systemd oficial de OpenClaw (con hardening)
- `deploy/ura-router-health.service` — Health check del Model Router
- `deploy/rotate-logs.service` — Rotación de logs vía logrotate
- `deploy/rotate_logs.timer` — Timer semanal para rotate-logs.service
- `scripts/watchdog_contraste.py` — Watchdog temporal (fallback si systemd no disponible)
- `scripts/start_contraste.sh` — Arranque manual proxy_contraste + watchdog
- `/home/ramon/docker/prometheus/alert.rules` — Regla NodoPerifericoDesconectado
- `/etc/ura/fix-path.conf` — Environment file desplegado del servicio

## Problemas Conocidos (2026-07-19)
- **Backup a Mac**: Requiere configuración SSH manual (clave generada en GX10)
- **Backups en mismo disco**: `/opt/ura/backups/` está en NVMe del GX10 (no redundancia)
- **Model Router**: Arreglado para no crear zombies (cache 5min, Connection: close)
- **RAM**: 57GB/121GB (~47%, modelo grande descargado)
- **Rootfs montado RO**: ✅ **RESUELTO (2026-07-19)**. Causa: falta `rw` en fstab. Fijado: `rw,errors=remount-ro`. `systemctl daemon-reload` aplicado. Próximo reinicio arrancará RW automáticamente.
- **Zombies**: 0 (limpiados durante reparación)
- **F14-F01**: Flag `no new privileges` impide usar sudo y restart systemd services sin polkit interactivo.
- **F14-F02**: `MultiAgentRuntime.cancel()` requiere `workflow_id` obligatorio — API inconsistente.
- **F14-F03**: `EpisodeStore` no recrea BD SQLite automáticamente tras corrupción (R06 data loss).
- **F14-F04**: Qdrant recovery time ~30.2s excede umbral de 30s en R01/R09 — borderline.
- **F14-F05**: `HybridRetriever` retorna éxito sin Qdrant disponible — posible fallback a memoria no documentado.

## Roadmap (Fases 10–29)

| Fase | Objetivo | Resultado Clave | Estado |
|------|----------|-----------------|--------|
| **10** | Estabilización | CI verde, 0 tests fallidos, sin issues conocidos | ✅ Cerrada (v0.10.0) |
| **11** | Plataforma | Motor extensible: plugins instalables, hooks, eventos, pipelines dinámicos, observabilidad técnica | ✅ Cerrada (v0.11.0) |
| **12** | Inteligencia | KE 2.0, ranking híbrido, chunking semántico, memoria contextual, multiagente, consenso | ✅ Cerrada (v0.12.0) |
| **13** | Producción | Docker, pip install, Prometheus/Grafana, releases, docs para terceros | ✅ Cerrada (v0.13.0) |
| **14** | Robustez | Load & Stress, resiliencia, E2E, profiling, RC Audit | ✅ Cerrada (v0.14.8-b5) |
| **28.1** | Stabilization | Cerrar F28: 0 bugs críticos, ADRs Approved, tag stable | ✅ Cerrada (v0.28.3-stable) |
| **29** | Production Readiness | OBS + VAL + OPS + RES + COMPAT + GOV + RR1 | ✅ Cerrada (v0.29.0-fase29) |

### Detalle por Fase

**Fase 10 — Estabilización** ✅ Cerrada (v0.10.0)
- ✅ 19 tests fallidos → 0 (540 passed)
- ✅ `sys.exit(78)` movido a main()
- ✅ `guardian_logger.py` SyntaxError corregido
- ✅ 27 subprocess → SubprocessExecutor migrados
- ✅ 67 tests nuevos (DegradedMode, PluginRegistry, Executor)
- ✅ Deuda lint: DTZ005 0, invalid-syntax 0, S603/S607 producción 0
- ✅ Benchmarks: 0 degradaciones
- **Salida:** CI verde, 0 tests fallidos, 0 regresiones
- `docs/architecture/FASE10_CLOSEOUT.md`

**Fase 11 — Plataforma (Capacidades del Motor)** ✅ Cerrada (v0.11.0)

**Orden:** Contract-first (Bloque 0 → Bloque 1 → Bloque 2 → Bloque 3)

| Bloque | Contenido | Estado |
|--------|-----------|--------|
| **0** | Contratos: ADRs (4) + PLUGIN_API.md | ✅ Completado |
| **1** | Infraestructura: EventBus, plugin manifest, RegistryV2, hooks, tests | ✅ Completado |
| **2** | Pipelines dinámicos: engine YAML, etapas base, CLI | ✅ Completado |
| **3** | Observabilidad: /metrics, /health, /ready, métricas de plugins | ✅ Completado |

**ADRs activos:**
- `ADR-011-01`: Contrato de API de plugins (plugin.yaml, PluginBase mejorado)
- `ADR-011-02`: EventBus tipado (tópicos, payloads, sync/async, patrones)
- `ADR-011-03`: Hooks desacoplados vía EventBus (cadena, circuit breaker)
- `ADR-011-04`: Versionado SemVer y matriz de compatibilidad

**Documentación técnica:** `docs/plugins/PLUGIN_API.md`

- **Regla:** Todo módulo nuevo como plugin (no script suelto)
- **Salida:** Toda nueva funcionalidad extensible mediante plugins/eventos, sin modificar el núcleo
- Ver `docs/architecture/FASE11_CLOSEOUT.md`

**Fase 12 — Inteligencia** ✅ Cerrada (v0.12.0)

**Orden:** KE Core → Context Memory → Multi-Agent Runtime

| Bloque | Contenido | Estado |
|--------|-----------|--------|
| **0** | Contrato: ADR-012-01 (métricas, corpus, baseline KE 1.x) | ✅ Completado |
| **1** | KE Core: chunking semántico, retrieval híbrido, reranking | ✅ Completado (Hybrid: R@10=0.87, NoCtx=0.5%) |
| **2** | Context Memory: episódica, semántica, compresión, olvido | 🔮 Planificado |
| **3** | Multi-Agent: consenso, Planner, Researcher, Executor, Validator, Supervisor | 🔮 Planificado |

**Contrato de calidad:**
- `ADR-012-01` define métricas (Recall@k, Precision@k, MRR, nDCG, latencias)
- Corpus de ≥200 consultas como requisito de entrada
- Baseline KE 1.x medido antes de cualquier desarrollo
- Toda mejora validada contra el corpus antes de aceptarse

- **Salida:** KE 2.0 operativo con métricas objetivas de mejora documentadas
- Ver `docs/architecture/FASE12_PROPOSAL.md`

**Fase 13 — Producción** ✅ Cerrada (v0.13.0)

- ✅ Consensus Engine (4 sub-bloques: Voting, Weighted, Reflection, Parallel)
- ✅ Docker + docker-compose + install.sh + entrypoint.sh
- ✅ Observabilidad (JSON logging, Prometheus exporter, dashboards, alerts)
- ✅ CI/CD (GitHub Actions, pip package, release workflow)
- ✅ Documentación (README, QUICKSTART, CLI, PLUGIN_DEV, ARCHITECTURE)
- ✅ Deuda F12 (KE↔Memory, orchestrator, LLM extractor, feature flags)
- **1100 tests, 0 failures. Sin dependencias circulares.**
- Ver `docs/architecture/FASE13_CLOSEOUT.md`

**Fase 14 — Robustez** ✅ Cerrada (v0.14.8-b5)

**Objetivo:** Validación operativa para Release Candidate. No añadir nuevas funcionalidades.
Solo medir, validar, documentar.

**Orden:** Load & Stress → Resiliencia → E2E → Profiling → RC Audit

| Bloque | Contenido | Estado |
|--------|-----------|--------|
| **1** | Load & Stress Testing: runtime (10/100/1000 wf), retrieval, memory, consensus. CPU/RAM/latencias, throughput, punto de saturación. Datos CSV/JSON | ✅ COMPLETADO |
| **2** | Resiliencia: matriz 10 escenarios con fallo/expected/observed/auto_recovery/data_loss/recovery_time. Sin corregir fallos durante la fase | ✅ COMPLETADO |
| **3** | End-to-End: 8 casos con ≥70% componentes reales, sin mocks salvo externos inevitables. Cobertura funcional documentada | ✅ COMPLETADO |
| **4** | Profiling: 5 escenarios (3h total), RSS/CPU/threads/MemoryStore/timeseries. Detectar leaks y crecimiento anómalo | ✅ COMPLETADO |
| **5** | RC Audit: tabla 10 requisitos con PASS/FAIL/PARTIAL. Conclusión: RC Ready / RC Ready with Conditions / Not RC Ready | ✅ COMPLETADO |

- **Regla:** No modificar el sistema para que pase los tests. No corregir fallos durante la fase. Documentar fallos como hallazgos.
- **Esfuerzo estimado:** 33-50h
- **Salida:** Evidencia objetiva de robustez para decidir si el proyecto alcanza clasificación Release Candidate
- Ver `docs/architecture/FASE14_PROPOSAL.md`
- **Resultado:** `RC Ready with Conditions` — 7/10 PASS, 0 FAIL, 3 PARTIAL.
  5 condiciones no bloqueantes resueltas antes de versión estable. Esfuerzo estimado: 5.5-8.5h.
- **Tags:** `v0.14.6-b3` (Bloque 3), `v0.14.7-b4` (Bloque 4), `v0.14.8-b5` (Bloque 5)
- Ver `docs/architecture/RC_READINESS.md`

**Fase 15 — Migración HTTP (Ollama)** ✅ Cerrada (F16-B1..B4 → F16-B4.2)
- Migración de llamadas HTTP directas a Ollama hacia `generate()` + `health()` del motor
- `core/debate/debate_engine.py`, `core/ura_multi_agent.py` migrados
- 0 HTTP directo a Ollama en `core/`, `motor/`, `knowledge/`
**Fase 16 — Empaquetado y Deuda** ✅ Cerrada (F16-B5..B7)
- Eliminación de dependencias rotas (`import httpx`), tests actualizados
- Tag `v0.16.0-fase16`

**Fase 17 — Configuración Unificada** ✅ Cerrada (v0.17.0-fase17)
- Unificación de UraConfig como vista tipada de CONFIG (Opción A de convergencia)
- B1: Auditoría CONFIG_AUDIT.md (36 consumidores, 7 defectos)
- B2: Deprecación de `config.local.json`
- B3: Corrección de `get_ollama_urls()` y eliminación de duplicados
- B5.1: Refactor de `UraConfig.load()` con helpers y prioridad legacy→CONFIG→env
- B6-D04: Migración de `secretario_cache.py` a UraConfig
- B6.5: `scripts/pro/audit_config.py` con 3 comprobaciones automáticas
- 0 nuevos errores Ruff, 0 regresiones Pytest, audit 0 problemas
- Ver `docs/architecture/FASE17_PROPOSAL.md`

**Fase 17.5 — Gestión de Secretos** ✅ Cerrada (v0.17.5-f17.5)
- `motor/core/secrets.py` con `get_secret`, `require_secret`, `has_secret`, `list_available`
- Backends: env vars / `/etc/ura/secrets.env` / default (preparado para Secret Manager futuro)
- 15 consumidores migrados en 4 grupos: motor/, knowledge/, core/, scripts/
- `scripts/pro/audit_secrets.py` — detección automática de secretos hardcodeados
- `docs/architecture/SECRETS.md` y `docs/architecture/SECRETS_AUDIT.md`
- Ruff delta: -99 errores en archivos tocados (0 nuevos)
- Ver `docs/architecture/SECRETS.md`

**Fase 25 — Knowledge Fusion** ✅ Cerrada (v0.25.0-fase25)

| Bloque | Contenido | Estado |
|--------|-----------|--------|
| **B1** | Contratos: ABCs (8), modelos (12), enums, config, registry | ✅ Completado (v0.25.0-b3) |
| **B2** | PipelineStage implementations: 8 stages concretos + BaseStage | ✅ Completado (v0.25.0-b3) |
| **B3** | Entity Resolution Avanzado: ContextualEntityResolver con desambiguación contextual, LRU cache, n-gramas, polisemia (Apple empresa/fruta, Tesla empresa/persona, Amazon empresa/río, Washington estado/capital/persona) | ✅ Completado (v0.25.0-b3) |
| **B4** | Conflict Detection (pendiente) | 🔮 Planificado |
| **B5** | Knowledge Merge (pendiente) | 🔮 Planificado |
| **B6** | Source Scoring (pendiente) | 🔮 Planificado |

Ver `docs/architecture/F25_ARCHITECTURE_AUDIT.md` para auditoría completa y métricas de calidad.

**Fase 26 — Historical Memory** ✅ Cerrada (v0.26.0-rc1)

- Arquitectura de memoria: Timeline (proyección temporal), Journal (WAL con fsync+checksum), Snapshot (punto de recuperación)
- Health/Readiness/Liveness probes funcionales
- Graceful Shutdown con timeout (flushea journal antes de salir)
- Cifrado AES-256-CTR opcional en journal y snapshot vía PBKDF2 (cryptography)
- Ver `motor/memory/` para implementación completa

**Fase 27 — Autonomous Agents** ✅ Cerrada (v0.27.0-fase27)

- Arquitectura de agentes: ABCs + modelos frozen (ADR-027-01/02)
- CapabilityGate con 6 denial codes + mensajes descriptivos
- ToolRunner con 20 constraints (TR-01..20), backpressure vía Semaphore
- Scheduler: FIFO + aging (priority decay cada 30s) + GracefulShutdown
- Planner: rule-based determinista (sin LLM en hot path)
- AgentOrchestrator: 18 constraints, DI-based, CapabilityGate integrado
- 109 tests, 0 regresiones
- Ver `motor/agents/` para implementación

**Fase 28 — Platform Protocols** ⚠️ Pending stabilization (F28.1)

- ProtocolEnvelope con 5 headers: Version, Routing, Trace, Delivery, Security
- JSON canonical serializer/deserializer + ProtocolValidator
- VersionNegotiator por MessageKind + CompatibilityChecker
- ProtocolRegistry + Transport ABC + LocalTransport
- ErrorEnvelope con trace_id + causation_id
- Observabilidad: TraceId/SpanId/parent_span_id, TraceExporter (bounded queue + background flush), HealthAggregator, MetricsCollector (p50/p95/p99), Sampler (5 estrategias), validate_span_tree, sanitize_tags
- Structured JSON logging (motor/platform/logging.py)
- RateLimiter (token bucket, thread-safe), payload sanitization (8 patrones bloqueados)
- 63 tests tracing + 488 tests total en F25-F28+OBS, 0 regresiones
- Ver `motor/platform/` y `docs/architecture/GOVERNANCE.md`
- **⚠️ Bugs conocidos:** checksum nunca verificado, race condition en LocalTransport, ADRs en Draft. Ver `docs/architecture/F28_B2_CODE_AUDIT.md`

**Fase 28.1 — Stabilization** ✅ Cerrada (v0.28.3-stable)

Ver `docs/architecture/ADR-028-11-F28.1-STABILIZATION.md` y `docs/architecture/F29_PROPOSAL.md`.

**Fase 29 — Production Readiness** ✅ Cerrada (v0.29.0-fase29)

| Bloque | Contenido | Estado |
|--------|-----------|--------|
| **B1** | Observabilidad: health probes, métricas, logging estructurado, tracing | ✅ Completado |
| **B2** | Validación técnica: benchmarks públicos, throughput, latencia, memoria, estrés | ✅ Completado |
| **B3** | Validación funcional: 5 dominios reales | ✅ Completado |
| **B4** | Operación: graceful shutdown, health endpoints, backup/restore | ✅ Completado |
| **B5** | Resiliencia: circuit breakers, backpressure, 7 chaos tests | ✅ Completado |
| **B6** | Compatibilidad y evolución: rolling upgrade, mixed-version | ✅ Completado |
| **B7** | Gobernanza: ownership, runbooks, SLOs, release checklist | ✅ Completado |
| **RR1** | Production Readiness Review + tag v0.29.0-fase29 | ✅ Completado |
| **B8** | Post-F29: Experiencia (F2), Conocimiento (F4), Infra (F1), Herramientas (F3), CLI (F5), Calidad (F6) | ✅ Completado |
| **B9** | Auditoría Final 2026-07-20: closeouts F25-F29, tests evaluation/preferences/auth, mypy fix, ruff fix, eval() reemplazado | ✅ Completado |

**Estado del Repositorio (post-auditoría 2026-07-20):**

| Categoría | Antes | Después |
|-----------|-------|---------|
| Ruff errors | 313 | 93 (62 EXE001 cosmético, 31 pre-existentes) |
| Mypy (assistant) | No pasaba (core duplicado) | 0 errores |
| Tests assistant | 97/97 | 107/107 (+10 tests evaluation + preferences) |
| eval() en prod | CalculatorTool con eval() | _SafeCalculator (AST puro, sin builtins) |
| Closeouts F25-F29 | 0/5 | 5/5 creados |
| build/ duplicado | Causaba `duplicate module "core"` | Eliminado + .gitignore |
| Working tree | Sucio (4 archivos) | Compromised |

No hay F30+ definida. Ver `docs/architecture/F29_PROPOSAL.md` y `docs/architecture/F29_CLOSEOUT.md`.

## Protocolo de Contexto Vectorial (Knowledge Base)
Antes de iniciar cualquier refactorización compleja, el agente debe consultar el grafo indexado para mitigar alucinaciones de dependencias:
```bash
$ python3 /home/ramon/URA/ura_ia_1972/scripts/pro/ura-query.py "descripción del cambio"
```