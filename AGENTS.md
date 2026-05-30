# URA — AI Agent Instructions

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
- `knowledge/` — Long-term memory, document fragments, knowledge base
- `scripts/pro/` — Pro maintenance module (6 phases with snapshot + rollback)

## GX10 (ASUS GB10) — Estado Real (2026-05-29 23:05)

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

### Ollama Optimizado (2026-05-29)
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

## Problemas Conocidos (2026-05-29)
- **Backup a Mac**: Requiere configuración SSH manual (clave generada en GX10)
- **Backups en mismo disco**: `/opt/ura/backups/` está en NVMe del GX10 (no redundancia)
- **Model Router**: Arreglado para no crear zombies (cache 5min, Connection: close)
- **RAM**: 105GB/121GB (modelo cargado en CUDA, no es fuga)
- **Zombies**: 3 (residuales del reboot, no crecen)
