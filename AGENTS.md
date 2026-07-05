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
- Full audit: `bash /home/ramon/URA/ura_ia_1972/tuneladora.sh`
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

### Backlog Deuda Técnica (No Bloqueante)

| ID | Ítem | Prioridad |
|----|------|-----------|
| T01 | `core/synonyms.json` con `chattr +i` en disco | Mínima |
| T02 | `scripts/pro/sanear_codigo.py:50` syntax error | Baja |
| T03 | 12 archivos .py con caracteres no-ASCII en nombre | Baja |
| T04 | 5 tests CLI fallan por dependencias del entorno | Baja |
| T05 | FTS schema verifier falso positivo (tablas extrañas) | Media |
| T06 | ~2.356 lint errors pre-existentes (ruff all rules) | Baja |
| T07 | `adapters/` directorio nunca creado | Informativa |
| T08 | 14 bloques `except: pass` validados (degradación controlada) | Mínima |
| T09 | ~80+ bloques `except: pass` sin auditar | Media |

### Fase 9 — Plan de Ejecución (Aprobado, v3.0)

Ver `docs/architecture/FASE9_PROPOSAL.md` para especificación completa.

**Orden de ejecución:** C → B → D → A → E (revisado: B antes que D, A al final)

| Stream | Descripción | Esfuerzo | Estado |
|--------|-------------|----------|--------|
| C | Modo degradado explícito (DegradedMode, /api/v1/status) | 2-3h | ✅ COMPLETADO |
| B | Modularidad: executor.py, plugin system via importlib, kill shell=True | 8-13h | ✅ COMPLETADO |
| D | Refactor CLI: extraer ura.py a motor/cli/, console_scripts | 3-5h | Pendiente |
| A | Calidad: unificar runners, reorganizar tests, Makefile | 2-3h | Pendiente |
| E | Validación final: baseline, benchmarks, smoke tests, tag | 1-2h | Pendiente |

**Regla:** `ura.py` se mantiene como wrapper durante Fase 9 (no se elimina).
**Cobertura:** No se fuerza umbral mínimo hasta que la cobertura real haya mejorado.
**Criterio:** Solo trabajo con impacto funcional o arquitectónico. Deuda técnica residual fuera.

### Pipeline Activo (scripts/pro/)
**~146 archivos** entre scripts Python, shell, servicios, configs y utilidades.
Organizados por función en las siguientes categorías:

| Categoría | Scripts | Propósito |
|-----------|---------|-----------|
| **Tuneladora** | `tuneladora_mantenimiento.py`, `tuneladora_mejora.py`, `tuneladora_master.py` | Pipeline de mejora continua (systemd timer cada 6h) |
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
| **Evolución/Ciclo** | `evolve.sh`, `ciclo_rapido.sh`, `filtro_cascada.sh`, `conflict_detector.sh`, `conectar_servidor_externo.sh`, `descubrir_puertos.sh`, `maquinas.sh`, `launch_refactor_gx10.sh`, `auto_export_context.sh` | Ciclos de evolución y detección de conflictos |
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
- 34 scripts huérfanos → `.nervioso/scripts_eliminados/`

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
| `opencode` | 8081 | ✅ activo | systemd | OpenCode Server |
| `ura-executor` | 4096 | ✅ activo | systemd | URA Executor API (renombrado de opencode-executor) |
| `agent-hierarchy` | - | ✅ activo | systemd | URA Agent Hierarchy System |
| `swarm-discovery` | - | ✅ activo | systemd | URA Swarm Auto-Discovery Service |
| `ura-agent-bus` | - | ✅ activo | systemd | URA Agent Message Bus |
| `ura-audit-api` | - | ✅ activo | systemd | URA Audit API (FastAPI) |
| `ura-contraste` | 8002 | ✅ activo | systemd | Proxy de Contraste + Telemetría POS (POST /api/v1/telemetry + GET /metrics) |
| `ura-detector` | - | ✅ activo | systemd | URA YOLOv8 Detector + ByteTrack + Behavior Analysis |
| `ura-go2rtc` | - | ✅ activo | systemd | go2rtc Camera Stream Proxy |
| `ura-mkdocs` | - | ✅ activo | systemd | URA MkDocs — Base de Conocimiento y Autopsias |
| `ura-ssh-guard` | - | ✅ activo | systemd | URA SSH Guard |
| `gx10-api` | - | ✅ activo | systemd | URA GX10 API — Remote endpoint with post-crash audit gate |
| `llama-vision` | - | ✅ activo | systemd | llama.cpp Vision Model for URA (Qwen2-VL-7B) |
| `tuneladora.timer` | - | ✅ activo | systemd | URA Tuneladora Timer - Every 6 hours |

### Servicios systemd (REALES - Usuario)
| Servicio | Puerto | Estado | Tipo | Notas |
|---|---|---|---|---|
| `model-router` | 11435 | ✅ activo | systemd user | URA Model Router Enhanced (cache 5min, Connection: close) |
| `start-router` | - | ✅ activo | systemd user | URA Router llama_router (usuario) |
| `backend@codestral-22b` | - | ✅ activo | systemd user | Backend llama.cpp para modelo codestral-22b |
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
- **Ubicación**: `/home/ramon/URA/ura_ia_1972/tuneladora.sh`
- **Fases**: 6 fases unificadas (Diagnóstico, Mantenimiento, Auditoría Modelos, Mejora, Rollback, Backup)
- **Timer**: `tuneladora.timer` - ejecuta cada 6 horas
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
- `/home/ramon/URA/ura_ia_1972/tuneladora.sh` — Tuneladora unificada (6 fases)
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

## Problemas Conocidos (2026-06-24)
- **Backup a Mac**: Requiere configuración SSH manual (clave generada en GX10)
- **Backups en mismo disco**: `/opt/ura/backups/` está en NVMe del GX10 (no redundancia)
- **Model Router**: Arreglado para no crear zombies (cache 5min, Connection: close)
- **RAM**: 105GB/121GB (modelo cargado en CUDA, no es fuga)
- **Zombies**: 0 (limpiados durante reparación)

## Protocolo de Contexto Vectorial (Knowledge Base)
Antes de iniciar cualquier refactorización compleja, el agente debe consultar el grafo indexado para mitigar alucinaciones de dependencias:
```bash
$ python3 /home/ramon/URA/ura_ia_1972/scripts/pro/ura-query.py "descripción del cambio"
```