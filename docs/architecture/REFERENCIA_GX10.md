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
| `opencode` | 8081 | ⏸️ parado | systemd | OpenCode Web Server — unit corregida desplegada (`EnvironmentFile=/etc/ura/secrets.env`, vars ya presentes). Parado: el proceso paralelo mantiene su opencode manual en 8081 (PID en `pts/1`, se re-lanza solo). Arrancar con `systemctl start opencode.service` cuando el manual cierre |
| `ura-openclaw` | 18789 | ⏸️ **disabled + inactive** (2026-08-08) | systemd | RETIRADO del repo (`c6d60c8c`). Unit borrada + daemon-reload ✅. Pendiente solo: `sudo rm /usr/local/bin/opencode` (wrapper del servicio ya inexistente) — incluido en `scripts/pro/cerrar_pendientes_sistema.sh` |
| `ura-api` | 8000 | ✅ activo | systemd | URA GX10 API — Remote endpoint with post-crash audit gate |
| `ura-audit-api` | 8080 | ✅ activo | systemd | URA Audit API (FastAPI) |
| `ura-consolidate` | - | ✅ activo | systemd | Consolidación de código (último run SUCCESS 2026-08-07) |
| `ura-contraste` | 8002 | ✅ activo | systemd | Proxy de Contraste + Telemetría POS (POST /api/v1/telemetry + GET /metrics) |
| `ura-fix` | - | ❌ fallido | systemd | auto-fix de ruff — `FileNotFoundError: 'ruff'` (PATH sin venv) — pendiente drop-in PATH (Tramo B F7) |
| `ura-go2rtc` | 1984 | ✅ activo | systemd | go2rtc Camera Stream Proxy |
| `ura-heartbeat` | - | ✅ activo | systemd | URA Mochila Heartbeat — reinicio automático si /health falla |
| `ura-metrics` | 8888 | ✅ activo | systemd | URA Metrics Server |
| `ura-mkdocs` | - | ✅ activo | systemd | URA MkDocs — Base de Conocimiento y Autopsias |
| `ura-mochila` | - | ✅ activo | systemd | Servicio Router Mochila - Servidor API FastAPI |
| `ura-ssh-guard` | - | ✅ activo | systemd | URA SSH Guard |
| `ura-voice` | - | ✅ activo | systemd | URA Voice Agent Pipeline (Anker S500 + Whisper GPU + Piper TTS) — restaurado 2026-08-07 (Tramo B F7): daemon `scripts/pro/pipeline_voz.py` (adaptado a `motor.core.voice`), modelo Piper `es_ES-davefx-medium.onnx` instalado, unit con `StartLimit*` en `[Unit]` |
| `ura-watchdog-buffer` | - | ✅ activo | systemd | URA Watchdog de Buffer de 30GB |
| `ura-watcher` | - | ✅ activo | systemd | URA Watcher — Indexación sectorizada en tiempo real |
| `ura-watcher-auditoria` | - | ✅ activo | systemd | URA Watcher Auditoria — Dispara auditoria al recibir datos |
| `ura-xvfb` | - | ✅ activo | systemd | URA Xvfb Virtual Display |
| `ura-agent-hierarchy` | - | ❌ fallido → **disabled** | systemd | URA Agent Hierarchy System — unit presente pero disabled+inactive (2026-08-11) |
| `ura-aspirador` | - | ❌ fallido → **disabled** | systemd | URA Aspirador — vectorize downloaded files — disabled+inactive (2026-08-11) |
| `ura-capturador` | - | ✅ **cerrado (2026-08-11)** | systemd | URA Capturador Tiempo Real — ExecStart apuntaba a `app/capturador.py` (retirado en F3, solo `.attic/`). Unit huérfana retirada vía `scripts/pro/cerrar_pendientes_sistema.sh` (stop+disable+rm, backup en `backups/pendientes_sistema_20260811_200730`) |
| `ura-detector` | - | ✅ activo | systemd | URA YOLOv8 Detector + ByteTrack + Behavior Analysis (running 2026-08-11) |
| `ura-fix-x11-socket` | - | ❌ fallido → **disabled** | systemd | URA Fix X11 socket directory — disabled+inactive (2026-08-11) |
| `ura-hetzner-tunnel` | - | ⏸️ parado | systemd | URA SSH Tunnel to Hetzner — unit corregida (puerto 2222 + `id_rsa` según `~/.ssh/config`) y parada hasta que la infra 178.105.81.83:2222 vuelva (host pingea, sshd caído). Backup: `/etc/systemd/system/ura-hetzner-tunnel.service.bak-20260807` |
| `ura-historiador` | - | ✅ **cerrado (2026-08-11)** | systemd | URA Historiador — ExecStart apuntaba a `scripts/pro/historiador.py` (**no existe**). Unit huérfana retirada vía `scripts/pro/cerrar_pendientes_sistema.sh` (stop+rm, backup en `backups/pendientes_sistema_20260811_200730`) |
| `ura-procesamiento-lento` | - | ❌ fallido → **disabled** | systemd | URA Daemon de Procesamiento Lento (10% CPU) — disabled+inactive (2026-08-11) |
| `ura-router-health` | - | ❌ fallido → **unit eliminada** | systemd | URA Model Router Health Check — unit not-found (2026-08-11) |

### Servicios systemd (REALES - Usuario)
| Servicio | Puerto | Estado | Tipo | Notas |
|---|---|---|---|---|
| `model-router` | 11435 | ✅ **activo (restaurado 2026-08-11)** | systemd system | URA Model Router Enhanced — estaba caído (48.445 reinicios): ExecStart apuntaba a `core/model_router.py` (archivo plano eliminado) + drop-ins rotos + token faltante. **Fix aplicado** vía `scripts/pro/cerrar_pendientes_sistema.sh`: unit oficial `deploy/model-router.service` (`-m core.model_router`), drop-ins rotos retirados, `OPENCLAW_GATEWAY_TOKEN` regenerado en `/etc/ura/secrets.env`. Verificado: /health `{"status":"ok","ollama":"reachable","models_available":13}` |
| `backend@qwen2.5-coder-32b` | - | ⚠️ NO VERIFICADO | systemd user | Backend llama.cpp para modelo qwen2.5-coder-32b — bus user OK pero sin unidades cargadas en esta sesión |
| `backend@qwen2.5-coder-q8_0` | - | ⚠️ NO VERIFICADO | systemd user | Backend llama.cpp para modelo qwen2.5-coder-q8_0 — idem |

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

### OpenClaw — RETIRADO (2026-08-08, commit `c6d60c8c`)
- Código eliminado del repo (criterio: `grep openclaw` en scripts/core/motor/deploy → 0).
- Excepciones intencionales: `monitor/` (SNC — brazo de emergencia, decisión Ramón) y `core/model_router/cli.py`
  (usa `OPENCLAW_GATEWAY_TOKEN` como auth de arranque — ADR-007 semantic freezing).
- Pendiente Ramón (sudo, 2026-08-08): `systemctl stop + disable` **aplicado** (disabled+inactive) y unit `/etc/systemd/system/ura-openclaw.service` **borrada + daemon-reload** ✅. `/home/ramon/.openclaw/` ya no existe. Queda solo el wrapper `/usr/local/bin/opencode` (gestor start/stop del servicio ya inexistente) — **eliminable con seguridad**: el servicio real `opencode.service` usa ruta absoluta `~/.opencode/bin/opencode` (v1.17.7), no depende del wrapper. Borrar con: `sudo rm /usr/local/bin/opencode`
- Si OpenClaw se usara en el futuro: solo como agente externo vía API HTTP :18789, sin imports desde core/motor.

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

### Ollama Native (actualizado 2026-08-10, v0.32.7)
- **OLLAMA_CONTEXT_LENGTH=65536** aplicado el 2026-08-10 (Ramón, sudo). Verificado: qwen3-coder:30b procesó prompt de 22K tokens junto con contexto 64K; RAM OK (78G libres de 121G). Anterior: 32768
- Backup `ollama-models-qwen3-only` eliminado (sudo rm -rf, Ramón, 2026-08-10) — liberó espacio

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
- **Mapa completo**: `docs/architecture/ESTRUCTURA_REPOSITORIO.md` (Fase 3 — v1)
- **Criterios de tests**: `tests/README.md`
- **`.attic/`** (gitignored): código retirado en Fase 3 (app/, cli/, sandbox/). Recuperable vía `git log` de las rutas originales
- **`ura.service`**: movido a `deploy/ura.service` (Fase 3)
- **`ura-audit`, `ura-contexto`**: movidos a `scripts/` (Fase 3)
- **`configs/`**: congelado por `chattr +i` — consolidación pendiente en `config/`

### Tuneladora Unificada
- **Ubicación**: `/home/ramon/URA/ura_ia_1972/scripts/pro/tuneladora_mantenimiento.py`
- **Fases**: 6 fases unificadas (Diagnóstico, Mantenimiento, Auditoría Modelos, Mejora, Rollback, Backup)
- **Timer**: `ura-maintenance-v2.timer` - ejecuta cada 6 horas (00,06,12,18)
- **Rutas corregidas**: Usa `/home/ramon/URA/` (no `/opt/ura/`)
- **Sin teatro**: `|| true` eliminados de pasos críticos

### Timers reales activos (verificado 2026-08-07)
- `ura-maintenance-v2.timer` (6h — tuneladora)
- `ura-pipeline.timer` → `ura-pipeline.service` (`/usr/local/bin/ura-motor pipeline`)
- `ura-auditd-watchdog.timer` → `ura-auditd-watchdog.service`
- `ura-memory-watchdog.timer` → `ura-memory-watchdog.service`
- `ura-mochila-guard.timer` → `ura-mochila-guard.service`
- `ura-watchdog.timer` → `ura-watchdog.service`
- `ura-backup.timer`, `ura-audit-extra.timer`, `ura-harden.timer`, `ura-cleanup.timer`,
  `ura-consolidate.timer`, `ura-fix.timer`
- `ura-cleanup-auto.timer` → `ura-cleanup-auto.service` (diario, último SUCCESS)
- ⚠️ `ura-consolidate.timer` está enabled pero su servicio está failed (falso servicio — Tramo B F7)
- ✅ `ura-fix.timer` **DESACTIVADO** (2026-08-07) — ejecutaba `sanear_codigo.py` que corrompía strings (`;`→`\n`); culpable neutralizado y script tokenizado (commit `e83dbd4f`)
- ⚠️ `deploy/timers/ura-mutmut.*` existe en repo pero NO está instalado (decisión: integrar o retirar)

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

