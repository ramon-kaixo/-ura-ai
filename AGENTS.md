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
- `core/` — Domain logic (consciousness, values, forensic scribe, rollback) + `config.py` (UraConfig) + `qdrant_client.py` (proxy hacia motor/)
- `agents/` — Specialized agents (organized by domain in subdirectories for new additions)
- `adapters/` — External connectors (Ollama, messaging platforms)
- `knowledge/` — Long-term memory, document fragments, knowledge base, vectorizar_docs
- `knowledge/engine/` — Knowledge Engine (Fases 0-7). Almacenamiento, indexado, lineage, memoria, vectorial, FTS5
- `scripts/pro/` — Pipeline activo (solo scripts esenciales)

## Fases

| Fase | Estado | Entrega |
|------|--------|---------|
| 0–6 | ✅ Cerradas | FTS5, edges, background queue, autorecuperación, reconcile |
| **7** | ✅ **Cerrada** (v3.0) | Optimizaciones Producción. Tag `v0.6.0-fase7`. 16 correcciones. PHASE7_CLOSEOUT.md |
| **8** | ✅ **Cerrada** | Hardening, Cobertura y Documentación. 10 correcciones. `docs/architecture/FASE8_DESIGN.md` |

### Backlog Fase 8 (desde PHASE7_CLOSEOUT.md v3.0)

| Stream | Items | Prioridad | Estado |
|--------|-------|-----------|--------|
| Cobertura tests | B02, B03, B04, B08 | Alta | ✅ Cerrado |
| Defensas | M04, M05, M06 | Alta/Media | ✅ Cerrado |
| Documentación | M02, M07, M08, M09 | Baja | ✅ Cerrado |

Ver `docs/architecture/FASE8_DESIGN.md` para diseño, plan de pruebas y criterios de aceptación.

### Pipeline Activo (scripts/pro/)
**Solo 27 scripts** — los demás fueron eliminados o fusionados:

| Script | Propósito | Llamado por |
|--------|-----------|-------------|
| `tuneladora_mantenimiento.py` | Diario/semanal + commit/rollback | systemd timer |
| `tuneladora_mejora.py` | Desarrollo + watchdog workers | OpenCode/docker |
| `token_screen.py` | RAM check antes de cada paso | ambas tuneladoras |
| `scanner_autoajuste.py` | Snapshot AST + chunk_optimizer | ambas tuneladoras |
| `poda_mecanica.py` | Dead code removal + chromatic map | tuneladora_mantenimiento |
| `refactor_large_functions_v2.py` | Refactor con LLM + compactación | ambas tuneladoras |
| `compactadora.py` | Reensamblaje post-LLM | tuneladora_mantenimiento |
| `compactador_espacios.py` | Compactación pre-LLM | importado por refactor_v2 |
| `auto_reglas.py` | Deterministic F821 repairs | ambas tuneladoras |
| `inspectores.py` | 10 inspectores (120 checks), blocking mode | ambas tuneladoras |
| `watermark_aggregator.py` | Watermark + auto-reglas | tuneladora_mantenimiento |
| `chunk_optimizer.py` | Recomienda chunk size dinámicamente | scanner_autoajuste |
| `conciencia.py` | Memory system | pipeline_supremo |
| `meta_mejora.py` | Meta-mejora con medición de impacto | manual |
| `analisis_completo.py` | Análisis integral (estado + monólogo + acciones) | manual |
| `openclaw_reviewer.py` | LLM reviewer (GPU) | pipeline_supremo |
| `openclaw_firmador.py` | Firma de código | manual |
| `ajustar_contexto.py` | Ajusta contexto del LLM | refactor_v2 |
| `auditor_router.py` | Auditor del Model Router | manual |
| `auto_conciencia.py` | Auto-conciencia | manual |
| `f821_watch.py` | Watchdog de F821 | ciclo_autonomo |
| `reglas_loader.py` | Carga reglas | auto_reglas |
| `sandbox_industrial.py` | Sandbox industrial | manual |
| `ejecutor_api.py` | API REST puerto 4096 | systemd |
| `alineador.py` | Valida respuestas URA/OpenClaw | pipeline_supremo |
| `analizar_fallo_conciencia.py` | Diagnóstico de conciencia | tuneladora_mantenimiento |
| `master_conciencia.py` | Testing de acciones URA | tuneladora_mantenimiento |
| `pareto_router.py` | Distribución 20/80 datos | tuneladora_mantenimiento |
| `ura_self_modify.py` | Auto-mejora del prompt | tuneladora_mantenimiento |

### Scripts Eliminados/Fusionados (2026-06-24)
- `ciclo_autonomo_gx10.py` → fusionado con `tuneladora_mantenimiento.py` (commit/rollback)
- `meta_mejora_real.py` → fusionado con `meta_mejora.py` (medición de impacto)
- `analisis_llm.py` + `meta_mejora_v2.py` + `reflexion_ura.py` → fusionado en `analisis_completo.py`
- `refactor_watchdog.py` → fusionado con `tuneladora_mejora.py` (watchdog integrado)
- `rpa_linksys.py` → eliminado (bypass_linksys_gui.py lo hace mejor)
- `auto_aplicar_mejoras.py` → eliminado (ura_self_modify.py lo hace todo)
- `reflexion_profunda.py` → eliminado (analizar_fallo_conciencia.py lo reemplaza)
- `translate_to_english.py` → eliminado (código ya está en inglés)
- `ia-flujo.service` → eliminado (app/flujo_constante.py nunca existió)
- 34 scripts huérfanos → movidos a `.nervioso/scripts_eliminados/`

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
- `core/config.py` — UraConfig (copia local para romper dependencia circular con motor/)
- `core/qdrant_client.py` — Proxy hacia motor.core.qdrant_client (misma razón)
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
- **ia-flujo.service**: Archivo con flag immutable (`chattr +i`) en deploy/. Pendiente: `sudo chattr -i deploy/ia-flujo.service && rm $_`
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