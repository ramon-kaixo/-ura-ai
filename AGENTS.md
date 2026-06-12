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
- `core/` — Domain logic (consciousness, values, forensic scribe, rollback)
- `agents/` — Specialized agents (organized by domain in subdirectories for new additions)
- `adapters/` — External connectors (Ollama, messaging platforms)
- `knowledge/` — Long-term memory, document fragments, knowledge base, vectorizar_docs
- `scripts/pro/` — Pipeline activo (solo scripts esenciales)

### Pipeline Activo (scripts/pro/)
**Solo 26 scripts** — los demás fueron eliminados o fusionados:

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
| `inspectores.py` | 10 inspectores (120 checks) | ambas tuneladoras |
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
| `bypass_linksys_gui.py` | Playwright port forwarding | manual (one-shot) |
| `alineador.py` | Valida respuestas URA/OpenClaw | pipeline_supremo |
| `analizar_fallo_conciencia.py` | Diagnóstico de conciencia | tuneladora_mantenimiento |
| `master_conciencia.py` | Testing de acciones URA | tuneladora_mantenimiento |
| `pareto_router.py` | Distribución 20/80 datos | tuneladora_mantenimiento |
| `ura_self_modify.py` | Auto-mejora del prompt | tuneladora_mantenimiento |

### Scripts Eliminados/Fusionados (2026-06-04)
- `ciclo_autonomo_gx10.py` → fusionado con `tuneladora_mantenimiento.py` (commit/rollback)
- `meta_mejora_real.py` → fusionado con `meta_mejora.py` (medición de impacto)
- `analisis_llm.py` + `meta_mejora_v2.py` + `reflexion_ura.py` → fusionado en `analisis_completo.py`
- `refactor_watchdog.py` → fusionado con `tuneladora_mejora.py` (watchdog integrado)
- `rpa_linksys.py` → eliminado (bypass_linksys_gui.py lo hace mejor)
- `auto_aplicar_mejoras.py` → eliminado (ura_self_modify.py lo hace todo)
- `reflexion_profunda.py` → eliminado (analizar_fallo_conciencia.py lo reemplaza)
- `translate_to_english.py` → eliminado (código ya está en inglés)
- 34 scripts huérfanos → movidos a `.nervioso/scripts_eliminados/`

## GX10 (ASUS GB10) — Estado Real (2026-06-03)

### Hardware NVIDIA GB10 Grace Blackwell Superchip
- **CPU**: 20 núcleos ARM nativos de alto rendimiento
- **GPU**: NVIDIA Blackwell (FP4/FP8 dedicada para IA)
- **Memoria**: 128 GB Unificada (Unified Memory Architecture) vía NVLink-C2C
- **Optimización**: Aprovechamiento máximo de memoria unificada entre CPU y GPU

### Servicios systemd (REALES - Sistema)
| Servicio | Puerto | Estado | Tipo | Notas |
|---|---|---|---|---|
| `ollama` | 11434 | ✅ activo | systemd | Sistema base, 2 paralelas, keep-alive 1m |
| `openclaw` | 18789 | ✅ activo | systemd | Gateway MCP |
| `opencode` | 8081 | ✅ activo | systemd | OpenCode Server |
| `ura-executor` | 4096 | ✅ activo | systemd | URA Executor API (renombrado de opencode-executor) |
| `agent-hierarchy` | - | ✅ activo | systemd | URA Agent Hierarchy System |
| `swarm-discovery` | - | ✅ activo | systemd | URA Swarm Auto-Discovery Service |
| `ura-agent-bus` | - | ✅ activo | systemd | URA Agent Message Bus |
| `ura-audit-api` | - | ✅ activo | systemd | URA Audit API (FastAPI) |
| `ura-contraste` | - | ✅ activo | systemd | Servidor API Proxy de Contraste URA |
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
  - `OLLAMA_NUM_PARALLEL=2` (reducido de 8)
  - `OLLAMA_MAX_LOADED_MODELS=2` (2 modelos en memoria)
  - `OLLAMA_KEEP_ALIVE=1m` (nuevo - reduce trasiego)
  - `OLLAMA_FLASH_ATTENTION=1` (aceleración hardware)
  - `OLLAMA_NOPRUNE=1` (sin poda de modelos)
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

### OpenClaw Integration
- Gateway: `http://10.164.1.99:18789`
- Servicio: `openclaw.service` (no openclaw-gateway.service)
- MCP: Configurado en OpenCode (Mac) como remote
- Skills habilitados: github, coding-agent
- CLI emergencia: `/usr/local/bin/openclaw-admin`
- Sandbox coding-agent: `/usr/local/bin/coding-agent-sandbox`

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
- GX10: Ethernet 10.164.1.99, WiFi 10.164.1.247, Tailscale 100.127.206.86
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

## Tone & Identity
- Peer-to-peer, direct, critical — no unnecessary theory, no agreeing by default
- Look for flaws and improvements, don't rubber-stamp
- Use "tú" (informal), concise responses (<4 lines unless detail requested)
- After task completion: present metricas reales + resumen sencillo

## Audit Format (obligatorio al final de respuestas a fases completas)
Al finalizar una tarea o responder a una solicitud completa, incluye:

<details><summary><b>⚙️ Ver/Modificar Normas Activas</b></summary>

`IDENTIDAD`: Compañero de trabajo, directo, crítico
`TONO`: Peer-to-peer, sin rodeos, busca fallos
`REGLA_GB10`: NO panic_on_oom=1, NO MemoryHigh=75G irreales
`REGLA_SESSION`: Guardar siempre en /home/ramon/URA/sesiones/ + commit
`REGLA_HOOKS`: git add antes de commit, --no-verify para cambios propios

Para modificar: edita AGENTS.md directamente.
</details>

### ACTUALIZAR_PROMPT
Cuando recibas un bloque de texto precedido de `ACTUALIZAR_PROMPT:`, debes:
  1. Leer el bloque
  2. Validar que no contenga comandos destructivos (rm, git clean -fd, chattr -i)
  3. Guardar el contenido ACTUAL como `/home/ramon/URA/prompt_backups/AGENTS_$(date +%Y%m%d_%H%M%S).md`
  4. Sobrescribir `/home/ramon/URA/ura_ia_1972/AGENTS.md` con el nuevo contenido (elevando privilegios con sudo si es necesario)
  5. Hacer `git add AGENTS.md && git commit --no-verify -m "prompt: actualizacion via ACTUALIZAR_PROMPT"`
  6. Confirmar la actualización al usuario mostrando el hash SHA-256 del nuevo archivo y el diff resumido

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
- `/opt/ura/config/go2rtc.yaml` — 30 streams de 15 cámaras Dahua
- `SECURITY_EXCEPTIONS.md` — Documentación de excepciones de seguridad

## Problemas Conocidos (2026-06-03)
- **Backup a Mac**: Reparado — usa Tailscale 100.123.81.101 + id_backup_mac, cron 03:00 ✅
- **Backups en mismo disco**: `/opt/ura/backups/` está en NVMe del GX10 (no redundancia)
- **Model Router**: Arreglado para no crear zombies (cache 5min, Connection: close)
- **RAM**: 38GB/121GB (53 GB liberados — codestral-22b + qwen2.5-coder-q8_0 eliminados) ✅
- **Zombies**: 0 (limpiados con la estabilización) ✅
- **post-commit hook**: No se modifica (chattr +i), auditoria_comite.sh es read-only — no borra archivos