# URA — Auditor de Sistemas de IA Aplicada

## Mapa Arquitectónico Completo del Ecosistema

**Versión:** 4.0  
**Fecha:** 2026-06-05  
**Hardware base:** NVIDIA GX10 (GB10 Grace Blackwell Superchip) — 20 núcleos ARM, GPU Blackwell, **128 GB RAM** unificada NVLink-C2C  
**Clúster complementario:** Mac Mini (M4) — Orquestación, interfaz, desarrollo  
**Infraestructura cloud:** Hetzner CX23 (Nuremberg) — Exit node, backup, contraste  
**Red privada:** Tailscale (cifrado extremo a extremo, malla WireGuard)

---

# ÍNDICE DE ESTRUCTURAS

1. [FUNDACIÓN — Hardware, SO, Red](#1-fundación)
2. [NÚCLEO — Core Domain](#2-núcleo-core-domain)
3. [MONITOREO — Sistema Nervioso Central](#3-monitoreo-sistema-nervioso-central)
4. [AGENTES — Especialistas Autónomos](#4-agentes)
5. [PIPELINE — Tuneladoras y scripts/pro](#5-pipeline-scriptspro)
6. [SERVICIOS — systemd y launchd](#6-servicios)
7. [SANDBOX — Aislamiento y Contenedores](#7-sandbox)
8. [CONFIGURACIÓN — Single Source of Truth](#8-configuración)
9. [MEMORIA — RAG y Base de Conocimiento](#9-memoria-rag)
10. [RED — Topología y Failover](#10-red)
11. [TESTS — Validación y Calidad](#11-tests)
12. [DEPLOY — Despliegue y Hardening](#12-deploy)
13. [MANIFIESTO — Reglas del Sistema](#13-manifiesto)
14. [ESTADO OPERATIVO — Métricas en Vivo](#14-estado-operativo)
15. [DIAGRAMA DE FLUJO GLOBAL](#15-diagrama-de-flujo-global)
16. [ÍNDICE CRUZADO — Todas las dependencias](#16-índice-cruzado)

---

# 1. FUNDACIÓN

## 1.1 Hardware

### NVIDIA GX10 (ASUS GB10) — Servidor principal
| Componente | Especificación | Propósito |
|---|---|---|
| CPU | **20 núcleos ARM** nativos alto rendimiento | Cómputo determinista, pipeline, monitoreo |
| GPU | **NVIDIA Blackwell** (FP4/FP8) | Inferencia LLM (Ollama), visión, revisión |
| RAM | **128 GB** unificada vía NVLink-C2C | Modelos LLM en memoria (10 modelos) |
| Almacenamiento | NVMe | Sistema, logs, snapshots, backups |

### Mac Mini (M4) — Orquestador
| Componente | Especificación | Propósito |
|---|---|---|
| CPU | Apple Silicon M4 | Desarrollo, interfaz, sincronización Git |
| RAM | Configurable | Compilación, tests, RAG local |
| Almacenamiento | SSD | Repositorio principal, backups locales |

### Hetzner CX23 — Nube
| Componente | Especificación | Propósito |
|---|---|---|
| CPU | **2 vCPU** AMD | Exit node Tailscale, backup, proxy de contraste |
| RAM | **4 GB** | Mínimo para servicios auxiliares |
| Ubicación | **Nuremberg, Alemania** | Latencia mínima ~30ms desde ASUS |

## 1.2 Software Base

| Componente | Versión | Puerto | Rol |
|---|---|---|---|
| **SO GX10** | Ubuntu 24.04.4 LTS (ARM64) | — | Plataforma principal |
| **SO Mac** | macOS 26.5.0 | — | Desarrollo y orquestación |
| **SO Hetzner** | Ubuntu 24.04 (AMD64) | — | Servicios cloud |
| **Python** | 3.12 | — | Lenguaje principal del sistema |
| **Ollama** | Última | **11434** | Gestión de modelos LLM locales |
| **Tailscale** | 1.98.4 (GX10), 1.96.5 (Mac) | 41641/UDP | Red privada mesh cifrada |
| **Docker** | Última | Socket | Contenedores sandbox |
| **systemd** | 255.4 | — | Gestión de servicios GX10 |
| **Node.js** | v22 | — | OpenCode server |

## 1.3 Red — Topología

```
INTERNET
    │
    ├── Linksys Velop MX4200 (10.164.1.1 / 192.168.1.1)
    │       ├── [CABLE 1 Gbps] ── GX10 (10.164.1.99 / eth0)
    │       │                       └── Tailscale: 100.72.103.12
    │       └── [WiFi 5GHz 80MHz] ── GX10 (192.168.1.139 / wlan0)
    │
    ├── Hetzner CX23 (178.105.81.83)
    │       └── Tailscale: 100.78.49.106 (Exit Node)
    │
    └── Mac Mini (10.164.1.26 / cable)
            └── Tailscale: 100.123.81.101
```

| Ruta | Prioridad | Tecnología | Ancho de banda real |
|---|---|---|---|
| GX10 → Internet (cable) | Primaria (métrica 50) | Ethernet 1 Gbps | **420/411 Mbps** (subida/bajada) |
| GX10 → Internet (WiFi) | Secundaria (métrica 600) | WiFi 5GHz 80MHz | 303/185 Mbps |
| GX10 → Mac (LAN) | Directa | Ethernet 1 Gbps | <1ms latencia |
| GX10 → Hetzner (Tailscale) | VPN directa | WireGuard cifrado | Directo vía cable |
| Mac → GX10 (Tailscale) | VPN directa | WireGuard cifrado | vía Tailscale IP `100.72.103.12` |

## 1.4 Algoritmo de Red — TCP BBR

| Parámetro | Antes | Ahora | Dónde |
|---|---|---|---|
| **Congestion control** | cubic | **bbr** | `/etc/sysctl.d/90-bbr.conf` |
| Mejora descarga | 185 Mbps | **411 Mbps** | +122% |
| Mejora subida | 303 Mbps | **420 Mbps** | +39% |
| Retransmisiones | 654 por test | **0** | Bufferbloat eliminado |

---

# 2. NÚCLEO (CORE)

## 2.1 core/config_manager.py (177 lines)

**Función:** Fuente única de configuración. Carga `config/system_config.json` y expande paths según el SO (Linux/Darwin).

| Función | Propósito |
|---|---|
| `load_config()` | Carga y valida `system_config.json` con detección de SO |
| `validate_schema()` | Valida contra `config/schema.json` |
| `get_base_dir()` | Retorna `~/URA` (Mac) o `/home/ramon/URA` (Linux) |
| `get_ollama_url()` | Retorna URL de Ollama según perfil |

**Dependencias:** `config/system_config.json`, `config/schema.json`  
**Tipo:** Librería pura (sin `__main__`)

## 2.2 core/model_router.py (485 lines)

**Función:** Microservicio HTTP en puerto **11435**. Clasifica peticiones por tipo y selecciona el mejor modelo Ollama.

| Ruta | Modelo primario | Fallback |
|---|---|---|
| `razonamiento` | `qwen3:32b-q8_0` | `qwen3:14b` → `llama3.3:70b` → `deepseek-coder:6.7b` |
| `codigo_complejo` | `qwen2.5-coder:32b` | `qwen2.5-coder:q8_0` → `qwen2.5-coder:14b` |
| `codigo_rapido` | `qwen2.5:7b` | `llama3.2:3b` → `deepseek-coder:6.7b` |
| `respuesta_rapida` | `qwen2.5:7b` | `llama3.2:3b` → `llama3.2:1b` |
| `vision` | `llama3.2-vision:11b` | `llava:34b` → `llava:13b` |
| `embeddings` | `nomic-embed-text` | `mxbai-embed-large` |

**Características:**
- Cache de prompts con **TTL 7200s** (2 horas)
- Sistema de **fallback** en cascada
- **Métricas** en `http://10.164.1.99:11435/metrics`
- Cabecera `Connection: close` (sin zombies)

**Tipo:** Servicio HTTP (systemd), ejecutable

## 2.3 core/ura_multi_agent.py (637 lines)

**Función:** Sistema multi-agente con bucle de auto-reparación. 3 agentes especializados.

### Agentes

| Agente | Modelo | Rol | Prompt |
|---|---|---|---|
| **Orquestador** | qwen2.5-coder:14b | Decide qué tarea delegar | Estado RAM, F821, funciones pendientes |
| **Ejecutor** | deepseek-coder:6.7b | Refactoriza funciones grandes | Prompt de 6 capas, temperatura 0.1 |
| **Reparador** | auto_reglas + LLM | Repara errores en 3 niveles | N1: determinista / N2: 6.7B / N3: 32B |

### Bucle Self-Healing (6 pasos)

```
① DETECTAR -> ② AISLAR -> ③ REPARAR (3 intentos) -> ④ VALIDAR -> ⑤ ACTUALIZAR -> ⑥ WATERMARK si falla
```

**Clases principales:** `Telemetria`, `Conciencia`, `AgenteOrquestador`, `AgenteEjecutor`, `AgenteReparador`, `SelfHealingLoop`

**Tipo:** Ejecutable con `__main__`

## 2.4 core/ingestador_red.py (217 lines)

**Función:** Distribuidor global de tareas vía Tailscale SSH. Enruta según carga: tareas pesadas -> ASUS, medianas -> Mac Mini, ligeras -> cualquier nodo.

**Tipo:** Ejecutable

## 2.5 core/resolver_red.py (230 lines)

**Función:** Resolución DNS + Failover de red. Prioriza cable (<1ms), fallback a Tailscale. Auto-switch si latencia >5ms.

**Tipo:** Ejecutable

## 2.6 core/memory_engine.py (260 lines)

**Función:** Motor RAG (Retrieval-Augmented Generation) con ChromaDB. Indexa documentos locales para enriquecer consultas LLM con contexto relevante.

**Clase:** `MemoryEngine` — `index_documents()`, `search()`, `enrich_query()`, `get_stats()`

**Tipo:** Librería (sin `__main__`)

## 2.7 core/sandbox.py (256 lines)

**Función:** Entorno aislado para ejecución segura de código Python. Importaciones dinámicas controladas, backup/restore de estado.

**Clase:** `Sandbox` — `run_code()`, `backup()`, `restore()`

**Tipo:** Librería + ejecutable

## 2.8 core/sandbox_orchestrator.py (395 lines)

**Función:** Orquestador de ejecuciones sandbox. Cola de tareas, registro de ejecución, rotación de entornos. Define **6 tipos de sandbox** con tiempos de ciclo.

**Clase:** `SandboxOrchestrator` — `start()`, `stop()`, `schedule_task()`

**Tipos de sandbox gestionados:**
- Seguridad
- Mantenimiento
- Documentación
- Aprendizaje
- Exploración
- Mejora Continua

**Tipo:** Librería

## 2.9 core/error_sandbox.py (295 lines)

**Función:** Sandbox de análisis de errores. Cuando un error no puede auto-repararse: análisis profundo, búsqueda en base de conocimiento, soluciones alternativas, reporte de intervención manual.

**Clase:** `ErrorSandbox` — `analyze()`, `search_knowledge_base()`, `execute_solution()`

**Tipo:** Librería + ejecutable

## 2.10 core/guardián_disco.py (213 lines)

**Función:** Guardian de Disco. Detección de cambios SHA-256 con verificación post-escritura. Escanea `.py`, `.json`, `.sh`, `.yaml`, `.yml`, `.md`. Detecta archivos fantasma (ghost files).

**Funciones:** `scan()`, `verify()`, `init_snapshot()`, `detect_changes()`

**Tipo:** Ejecutable

## 2.11 core/ura_sandbox_bridge.py (250 lines)

**Función:** Capa de seguridad para todo I/O a internet. 3 modos: `passthrough` (actual), `ssh` (VM remota), `lima` (Lima VM).

**Clase:** `SandboxBridge` — `fetch_page()`, `run_command()`, `run_openclaw()`

**Tipo:** Librería

---

# 3. MONITOREO (SISTEMA NERVIOSO CENTRAL)

## 3.1 monitor/snc.py (301 lines) — SNC

**Función:** Sistema Nervioso Central. Sondeo cada **10 segundos**. Monitorea procesos vía HTTP/socket. Estado en `/tmp/ura_snc_state.json`. Ejecuta `emergency_runbook.json` ante fallos.

| Modo | Descripción |
|---|---|
| NORMAL | Sondeo cada 10s, todo OK |
| ALERTA | Fallo detectado, primer intento de reparación |
| EMERGENCIA | Múltiples fallos, ejecuta runbook, activa OpenClaw |
| CRÍTICO | 3 intentos fallidos, notificación humana requerida |

**Funciones:** `check_processes()`, `emergency_loop()`, `health_check()`

**Servicios monitoreados:**
- ollama (11434)
- model_router (11435)
- openclaw (18789)
- opencode (8081)
- ura-executor (4096)
- tailscale
- Conexión Mac (heartbeat)

**Tipo:** Servicio systemd (`snc.service`), ejecutable

## 3.2 monitor/openclaw.py (262 lines) — Brazo de Emergencia

**Función:** Brazo de ejecución de emergencia controlado por SNC. Solo se activa en estado **EMERGENCY**. Protocolo Dead Man: **60 segundos** sin confirmación humana = bloquea acciones destructivas.

**Funciones:** `load_runbook()`, `execute_runbook_action()`, `process_emergency()`

**Tipo:** Ejecutable

## 3.3 monitor/health_check.py (237 lines)

**Función:** Diagnóstico completo de GX10. Mide: disco, RAM, carga CPU, VRAM Ollama, latencia SSH/HTTP.

**Funciones:** `check_disk()`, `check_ram()`, `check_cpu()`, `check_vram()`, `check_latency()`

**Tipo:** Ejecutable

## 3.4 monitor/snc_remote.py (104 lines)

**Función:** Observador Mac del SNC de GX10. Sincroniza estado cada 10s. Alerta si GX10 está OFFLINE o CRITICAL.

**Tipo:** Ejecutable

## 3.5 monitor/error_logger.py (150 lines)

**Función:** Log circular de errores (JSON Lines, máximo **1000 entradas**). Cada entrada: timestamp, error_id, contexto, gateway_status, severidad, mensaje. Auto-detecta Mac vs ASUS.

**Clase:** `ErrorLogger`

**Tipo:** Librería

## 3.6 monitor/mac_heartbeat.py (133 lines)

**Función:** Detección de presencia del Mac vía ping cada **30 segundos**. 3 fallos consecutivos = alerta. Persiste en `/tmp/ura_mac_heartbeat.json`.

**Clase:** `MacHeartbeat`

**Tipo:** Librería

## 3.7 monitor/log_alerts.py (140 lines)

**Función:** Centraliza y desduplica errores críticos de GX10. Hash de contenido evita reportes duplicados. Escanea logs SSH buscando patrones ERROR/CRITICAL/FATAL/CRASH/Traceback.

**Tipo:** Ejecutable

---

# 4. AGENTES

## 4.1 agents/agente_sandbox_codigo.py (289 lines)

**Función:** Vigilante del sandbox de código en **modo mixto**:
- **AUTÓNOMO** para tareas rutinarias (mover, testear, documentar)
- **MANUAL** para tareas críticas (Ramon debe aprobar antes de producción)

Gestiona **6 directorios de pipeline**:

```
pendientes/ -> en_pruebas/ -> espera_aprobacion/ -> { aprobados/ , rechazados/ }
```

**Funciones:** `process_queue()`, `test_code()`, `approve_pending()`

**Tipo:** Ejecutable

---

# 5. PIPELINE (scripts/pro)

## 5.1 Las Dos Tuneladoras (Orquestadores)

### tuneladora_mantenimiento.py (396 lines)
**Función:** Tuneladora que **REVISA** — nunca modifica código. 3 niveles de profundidad:

| Nivel | Frecuencia | Acciones |
|---|---|---|
| **Ligero** | Cada 6h | token_screen + scanner + ruff + auto_reglas |
| **Medio** | Cada 24h | + poda + refactor_v2 + compactadora + scanner_salida + inspectores |
| **Profundo** | Lunes 03:00 | + refactor 4 workers + watermarks + backup + commit/rollback |

**Tipo:** Ejecutable + systemd timer

### tuneladora_mejora.py (109 lines)
**Función:** Tuneladora que **MODIFICA** código. Usa `plugin_registry.py` para auto-descubrir plugins. Fases: **pre -> refactor -> post**.

**Tipo:** Ejecutable (Docker sandbox, OpenCode)

### tuneladora_master.py (249 lines)
**Función:** Orquestador maestro de excavación autónoma (AEA). Modos: delta check, force-all, intensive-audit.

**Tipo:** Ejecutable

## 5.2 Pipeline Secuencial (12 Rodillos)

```
CADA 1H — Health Check
- RAM, CPU, zombies, procesos clave
- Model Router heartbeat (11435)
- Log rotación si >100MB

CADA 6H (00:00, 06:00, 12:00, 18:00) — 5 Rodillos
- R1: DIAGNÓSTICO (300s)
  - Ruff fix (F841, F401, F811)
  - Poda Mecánica -> mapa cromático
  - Test unitarios (127) + OpenClaw (12)
  - F821 count vs baseline

- R2: REFACTOR (3600s)
  - 0. Contexto Dinámico (ajustar_contexto.py)
  - 1. Poda Mecánica (poda_mecanica.py)
  - 2. LLM Principal (deepseek-coder:6.7b, 4 workers, ~12min)
  - 3. Fallback (qwen2.5-coder:14b, ~8min)
  - 4. Compactadora (compactadora.py)
  - 5. Auto-Reglas (auto_reglas.py, 9 built-in)
  - 6. Inspectores (inspectores.py, 120 checks)
  - 7. Watermarks (watermark_aggregator.py)

- R3: AUDITORÍA MODELOS (120s)
  - Verificar Ollama + modelos disponibles
  - Model Router health + métricas

- R4: MEJORA CONTINUA (600s)
  - Sandbox Docker (ruff + pytest + bandit)
  - Watermark Aggregator
  - Generar reglas auto desde patrones
  - Detectar patrones sistémicos (>=3 ciclos)

- R5: BACKUP + REPORTE (300s)
  - Snapshot .nervioso/
  - Reporte JSON
  - Delta snapshot para siguiente ciclo

CADA 24H (03:00) — 4 Rodillos
- R6: MANTENIMIENTO PROFUNDO (600s)
  - Docker system prune
  - Pip cache purge
  - Log rotación + compresión
  - __pycache__ + .mypy_cache cleanup

- R7: BACKUP COMPLETO (900s)
  - Backup a Mac (rsync)
  - Tar.gz del repo
  - Backup configs systemd + watermarks

- R8: MÉTRICAS DIARIAS (120s)
  - F821 vs baseline
  - Funciones grandes restantes (>80 líneas)
  - Tasa éxito vs error

- R9: AUTO-LIMPIEZA (60s)
  - Watermarks reparados >7 días -> eliminar
  - Reglas con confianza <0.3 -> eliminar
  - Recalcular baseline F821

BAJO DEMANDA — 3 Rodillos
- R10: REPARACIÓN EMERGENCIA (300s)
  - Reparar zombies, RAM, servicios
  - Restart Model Router si caído
  - Rollback a último snapshot

- R11: REFACTOR EXPLÍCITO (7200s)
  - Refactor con parámetros específicos

- R12: DASHBOARD
  - Métricas en :11435/metrics
  - Estado en .nervioso/estado.json
```

## 5.3 Scripts de Pipeline (26 activos)

| Script | Líneas | Fase | Función | Tipo |
|---|---|---|---|---|
| token_screen.py | 228 | PRE | RAM guardian + ajuste contexto | PLUGIN |
| scanner_autoajuste.py | 422 | PRE | Snapshot AST + chunk optimizer | PLUGIN |
| chunk_optimizer.py | 289 | PRE | Recomienda chunk dinámico | PLUGIN |
| conciencia.py | 280 | PRE | Memoria unificada del sistema | PLUGIN |
| poda_mecanica.py | 359 | REFACTOR | Dead code + mapa cromático | PLUGIN |
| compactadora.py | 327 | REFACTOR | Reensamblaje post-LLM | PLUGIN |
| ajustar_contexto.py | 121 | REFACTOR | Ajusta contexto del LLM | PLUGIN |
| refactor_large_functions_v2.py | 355 | REFACTOR | Refactor con LLM + compactación | PLUGIN |
| compactador_espacios.py | 178 | (library) | Compactación pre-LLM | importado |
| refactor_large_functions.py | 297 | REFACTOR | Refactor original (fallback) | standalone |
| refactor_v2.py | 202 | REFACTOR | Refactor v2 entry | standalone |
| auto_reglas.py | 168 | POST | Reparación F821 determinista | PLUGIN |
| inspectores.py | 664 | POST | 10 inspectores x 12 checks | PLUGIN |
| openclaw_reviewer.py | 187 | POST | Revisor LLM (GPU) | PLUGIN |
| alineador.py | 120 | POST | Valida respuestas URA/OpenClaw | PLUGIN |
| watermark_aggregator.py | 212 | POST | Watermark + auto-reglas | PLUGIN |
| f821_watch.py | 184 | POST | Watchdog F821 | PLUGIN |
| meta_mejora.py | 185 | POST | Meta-mejora con medición | PLUGIN |
| analisis_completo.py | 238 | POST | Análisis integral | PLUGIN |
| pareto_router.py | 242 | POST | Distribución 20/80 datos | PLUGIN |
| openclaw_firmador.py | 411 | (library) | Firma de código BLAKE2b | librería |
| reglas_loader.py | 41 | (library) | Carga reglas desde JSON | importado |
| reglas_applier.py | 118 | (library) | Aplica reparaciones | importado |
| reglas_generator.py | 106 | (library) | Genera reglas de patrones | importado |
| plugin_registry.py | 136 | infra | Auto-descubrimiento de plugins | infra |
| pipeline_supremo.py | 288 | infra | Orquestador 11 pasos | standalone |
| sandbox_industrial.py | 676 | infra | Sandbox industrial masivo | standalone |
| ejecutor_api.py | 144 | infra | API REST puerto 4096 | systemd |
| auto_conciencia.py | 145 | manual | Auto-evaluación MCP | standalone |
| analizar_fallo_conciencia.py | 137 | manual | Diagnóstico de conciencia | standalone |
| master_conciencia.py | 103 | manual | Testing de acciones URA | standalone |
| ura_self_modify.py | 149 | manual | Auto-mejora del prompt | standalone |
| auditor_router.py | 240 | manual | Auditor del Model Router | standalone |
| bypass_linksys_gui.py | 224 | one-shot | Playwright port forwarding | standalone |

### Plugins Registrados (17)

El sistema `plugin_registry.py` descubre automáticamente scripts con `PLUGIN = {...}`:

**PRE:** chunk_optimizer, conciencia (blocking), scanner_autoajuste (blocking), token_screen (blocking)

**REFACTOR:** ajustar_contexto, compactadora, poda_mecanica, refactor_large_functions_v2

**POST:** alineador, analisis_completo, auto_reglas, f821_watch, inspectores, meta_mejora, openclaw_reviewer, pareto_router, watermark_aggregator

*Pipeline completo: 17/17 plugins, 5.3s*

## 5.4 Shell Scripts (41 activos en scripts/pro/)

| Script | Líneas | Propósito |
|---|---|---|
| phase1_diagnosis.sh | 48 | ruff + radon + pytest |
| phase2_filter.sh | 48 | ruff --fix + autoflake + ruff format |
| phase3_architecture.sh | 48 | radon + vulture + pytest |
| phase4_rollback.sh | 47 | Restore snapshot if failure |
| ciclo_rapido.sh | 14 | Auto-consciousness cada 5 min |
| deploy_camaras.sh | 154 | Despliegue sistema de cámaras (go2rtc) |
| deploy_copilotos.sh | 166 | Despliegue Copilot agents en Tailscale |
| deploy_sandbox_gx10.sh | 44 | Despliegue sandbox en GX10 |
| instalar_gx10_circuit.sh | 174 | Circuit breaker + maintenance en GX10 |
| integracion_opencode.sh | 99 | Integración OpenCode en pipeline |
| launch_refactor_gx10.sh | 129 | Lanzar refactor en GX10 |
| redirect_mejora_gx10.sh | 79 | Redirigir mejora continua Mac->GX10 |
| gx10_sync.sh | 33 | Sincronización Mac->GX10 |
| gx10_sync_final.sh | 21 | Sync final |
| safe_rollback.sh | 22 | Rollback seguro |
| shadow_git_rollback.sh | 17 | Rollback git a /tmp |
| supervisor_ciclo.sh | 53 | Supervisor Mac (cada 5 min, crontab) |
| instalar_servidor_camaras.sh | 51 | Instalar servidor de cámaras en cloud |
| descubrir_puertos.sh | 44 | Escaneo de puertos en Tailscale |
| detect_environment.sh | 24 | Detectar Docker vs nativo |
| check_licenses.sh | 58 | Auditoría licencias Python |
| conflict_detector.sh | 6 | Detectar conflictos de fase |
| cross_trace.sh | 20 | Documentar paso de código Mac<->GX10 |
| evolve.sh | 48 | Analizar tendencias y auto-ajustar |
| false_positive_baseline.sh | 9 | Línea base falsos positivos |
| fn_scanner.sh | 48 | Detectar servicios faltantes |
| fp_scanner.sh | 36 | Identificar falsos positivos conocidos |
| fpfn_report.sh | 22 | Reporte FN/FP combinado |
| quality_metrics.sh | 18 | Medición de salud de código |
| refactor_preflight.sh | 99 | Verificaciones pre-refactor |
| setup_logrotate_newsyslog.sh | 15 | Config rotación logs macOS |
| trampa_rm.sh | 18 | Trampa rm -> cuarentena |
| upgrade_pipeline.sh | 31 | Upgrade combinado pipeline |
| ura-exit-node.sh | 55 | Gestión exit node Tailscale |
| asus_connect_hetzner.sh | 68 | Conectar ASUS->Hetzner exit node |
| conectar_servidor_externo.sh | 70 | Proxy de contraste en cloud |
| conceder_permisos_accesibilidad.sh | 23 | Permisos accesibilidad macOS |
| desplegar_dahua_supervisor.sh | 60 | Supervisor cámaras Dahua |
| install_tailscale_hetzner.sh | 112 | Instalar Tailscale en Hetzner |
| maquinas.sh | 26 | Nombres normalizados URA |
| notify_on_change.sh | 33 | Notificación de cambios Git |

---

# 6. SERVICIOS

## 6.1 Servicios systemd (GX10) — 15 activos

| Servicio | Puerto | Estado | Depende de |
|---|---|---|---|
| ollama | 11434 | OK | Sistema base |
| openclaw | 18789 | OK | Ollama |
| opencode | 8081 | OK | Ollama |
| ura-executor | 4096 | OK | — |
| agent-hierarchy | — | OK | ura-agent-bus |
| swarm-discovery | — | OK | ura-agent-bus |
| ura-agent-bus | — | OK | — |
| ura-audit-api | — | OK | ura-agent-bus |
| ura-contraste | — | OK | — |
| ura-detector | — | OK | Ollama, go2rtc |
| ura-go2rtc | — | OK | Cámaras |
| ura-mkdocs | — | OK | — |
| ura-ssh-guard | — | OK | — |
| gx10-api | — | OK | — |
| llama-vision | — | OK | Ollama |
| snc | — | OK | — |
| tuneladora-mantenimiento.timer | — | OK | tuneladora_mantenimiento |
| tuneladora-maintenimiento-semanal.timer | — | OK | tuneladora_mantenimiento |

## 6.2 Servicios systemd user (GX10) — 4 activos

| Servicio | Puerto | Estado |
|---|---|---|
| model-router | 11435 | OK |
| start-router | — | OK |
| backend@codestral-22b | — | OK |
| backend@qwen2.5-coder-32b | — | OK |

## 6.3 LaunchAgents (Mac) — 12 activos

| Servicio | Propósito |
|---|---|
| com.ura.agente-voz | Agente de voz |
| Model Router plist | Enrutamiento de modelos |

---

# 7. SANDBOX

## 7.1 Contenedores Docker

| Contenedor | Estado | Propósito |
|---|---|---|
| ura-mejora-continua | OK Activo | Sandbox de desarrollo principal |
| ura-sandbox-mantenimiento | Inactivo | Validación |
| ura-sandbox-documentacion | Inactivo | MkDocs :8087 |
| ura-sandbox-exploracion | Inactivo | Exploración autónoma |
| ura-sandbox-aprendizaje | Inactivo | Aprendizaje continuo |
| ura-sandbox-seguridad | Inactivo | Auditoría de seguridad |

## 7.2 Infraestructura Docker

| Archivo | Propósito |
|---|---|
| deploy/docker/Dockerfile | Imagen base Python 3.12-slim |
| deploy/docker/docker-compose.yml | GX10: open-webui, n8n, mosquitto, nodered, postgres, uptime-kuma, homer |
| deploy/docker/docker-compose.sandbox.yml | 5 sandboxes + redes aisladas |
| deploy/docker/sandbox/*/Dockerfile | Imágenes especializadas por sandbox |

---

# 8. CONFIGURACIÓN

## 8.1 config/system_config.json (295 lines)

**Fuente única de verdad (SSOT).** Perfiles por SO.

## 8.2 config/dispositivos.json (103 lines)

Inventario dinámico de dispositivos con IP Tailscale, rol y prioridad.

## 8.3 config/reglas_builtin.json (722 lines)

**722 líneas** de reglas de reparación deterministas con confianza y severidad.

## 8.4 config/infra_config.json (28 lines)

Configuración de infraestructura: hostname, rutas, puertos, contacto, licencia.

## 8.5 config/schema.json (117 lines)

Esquema JSON Schema para validar system_config.json.

---

# 9. MEMORIA (RAG)

## 9.1 Base de Conocimiento

| Archivo | Contenido |
|---|---|
| data/documentos/arquitectura.md | Visión general de la arquitectura |
| data/documentos/faq.md | Preguntas frecuentes |
| data/documentos/reglas.md | Reglas del sistema |

## 9.2 ChromaDB

Motor RAG: `core/memory_engine.py` indexa documentos y enriquece consultas LLM.

## 9.3 .nervioso/ — Estado Operativo

| Archivo | Propósito |
|---|---|
| conciencia.json | Estado compartido de todos los procesos |
| reglas_auto.json | Reglas aprendidas automáticamente |
| chunk_config.json | Configuración dinámica de chunk |
| watermarks.json | Errores pendientes de reparar |
| snapshots/ | Rollback safety snapshots |
| scripts_eliminados/ | Backup de scripts obsoletos |

---

# 10. RED

## 10.1 Topología

| Ruta | Métrica | Latencia | Ancho de banda |
|---|---|---|---|
| GX10 (cable) -> Linksys -> Internet | 50 | ~56ms | 420/411 Mbps |
| GX10 (WiFi) -> Linksys -> Internet | 600 | ~60ms | 303/185 Mbps |
| GX10 (cable) -> Mac Mini | directa | <1ms | 1 Gbps |

## 10.2 Failover

El sistema tiene 3 rutas de red: cable (métrica 50, primaria), WiFi (métrica 600, secundaria), Tailscale (failover lógico). `core/resolver_red.py` detecta latencia >5ms y cambia automáticamente.

## 10.3 Puertos Críticos

| Puerto | Servicio | Host |
|---|---|---|
| 11434 | Ollama | GX10 |
| 11435 | Model Router | GX10 |
| 18789 | OpenClaw Gateway | GX10 |
| 8081 | OpenCode | GX10 |
| 4096 | URA Executor API | GX10 |
| 22 | SSH | GX10 |

---

# 11. TESTS

| Suite | Archivo | Tipo |
|---|---|---|
| Unitarios | tests/test_unit.py (455 lines) | Funcional |
| Integración | tests/test_integration.py (148 lines) | Contra GX10 |
| OpenClaw | tests/test_openclaw.py (264 lines) | unittest |
| Smoke | deploy/docker/scripts/pro/integration_smoke.sh | Shell |
| Pre-commit | .pre-commit-config.yaml | Automático |

---

# 12. DEPLOY

Pipeline de despliegue: Mac (desarrollo) -> git commit+push -> Git -> GX10 (auto_pull.sh cada min) -> validate_change.sh -> systemctl restart.

Scripts de deploy (11): auto_pull.sh, claw_listener.sh, gx10_bootstrap.sh, immutable_mac.sh, lock_mac_folder.sh, network_failover.sh, panic_handler.sh, sync_to_asus.sh, test_proteccion.sh, ura_watcher.sh, validate_change.sh.

---

# 13. MANIFIESTO

## Las 5 Reglas del Sistema

1. **Single Source of Truth** — Toda la configuración en `config/system_config.json`
2. **Idempotencia** — Ejecutar 10 veces seguidas da el mismo resultado
3. **Prohibición de Cambios Manuales** — Todo vía Git, nada en servidor directo
4. **Conciencia de Plataforma** — El sistema detecta SO y carga perfil correcto
5. **Validación Idempotente** — Verifica directorios al arrancar, no los crea automáticamente

## Reglas Operativas

1. Nunca modificar código fuente directamente en GX10
2. Siempre ejecutar tests antes de commit
3. Nunca exponer Ollama a la red externa

## Reglas de Desarrollo (.windsurfrules) — 14 reglas

Exhaustividad en búsquedas, no duplicar lógica, Single Responsibility, Singleton enforcement, sincronización obligatoria Mac->ASUS, commits honestos, inyección de dependencias.

---

# 14. ESTADO OPERATIVO

## Métricas Clave

| Indicador | Valor | Tendencia |
|---|---|---|
| F821 total | 0 (de 314) | Estable |
| Funciones >80 líneas | 107 (63% refactorizadas) | En descenso |
| Pipeline completo | 17/17 plugins, 5.3s | Óptimo |
| Tasa éxito refactor (6.7B) | 62,5% | Estable |
| Tasa éxito refactor (14B) | 40% | Baja |
| RAM GX10 | 73 GB / 128 GB | 57% libre |
| Zombies | 0 | OK |
| Reglas auto-aprendidas | 9 built-in | OK |
| Modelos Ollama | 10 | OK |
| Model Router | OK en :11435 | OK |
| Velocidad internet | 420/411 Mbps | Óptimo (BBR) |
| Latencia GX10->Internet | ~56ms | Estable |
| Latencia GX10->Mac | <1ms | OK |
| Cobertura tests | 3 suites + smoke | OK |
| SNC | Polling cada 10s | OK |

## Alertas

| Alerta | Estado | Acción |
|---|---|---|
| 107 funciones >80 líneas | En proceso | Continuar refactor (63%) |
| docker.sock en sandbox | Riesgo seguridad | Aplicar hardening D3 |
| Volumen RW en mejora-continua | Riesgo seguridad | Aplicar hardening D1 |
| Backups en mismo disco | Sin redundancia | Configurar backup externo |

---

# 15. DIAGRAMA DE FLUJO GLOBAL

```
URA — AUDITOR DE SISTEMAS DE IA
NVIDIA GX10 · 128GB · 20 núcleos · GPU Blackwell
        |
    CLI (ura.py) ----- Model Router (:11435, 10 modelos)
        |
    MULTI-AGENT SYSTEM (core/ura_multi_agent)
    - ORQUESTADOR (qwen14b): decide qué delegar
    - EJECUTOR (deepseek 6.7b): refactoriza código
    - REPARADOR (auto_reglas + LLM): 3 niveles de reparación
    - SELF-HEALING: Detectar -> Aislar -> Reparar -> Validar -> Actualizar -> Watermark
        |
    PIPELINE (scripts/pro/)
    - PRE (4 plugins): token_screen, scanner, chunk_optimizer, conciencia
    - REFACTOR (4 plugins): ajustar_contexto, poda, compactadora, refactor_v2
    - POST (9 plugins): auto_reglas, inspectores, openclaw_reviewer, alineador, ...
        |
    SNC (monitor/snc) --- SANDBOX (core/sandbox*) --- MANTENIMIENTO (mantenimiento/)
    Polling 10s           6 contenedores            Cleanup Docker
    Emergency runbook     Aislamiento               Logs + cache
        |
    INFRAESTRUCTURA: GX10 + Mac Mini + Hetzner + Tailscale + Linksys + Cámaras
```

---

# 16. ÍNDICE CRUZADO

## Por directorio

| Directorio | Python | Líneas | Propósito |
|---|---|---|---|
| raíz | 3 | 659 | Entry points |
| core/ | 11 | 3.414 | Lógica de dominio |
| agents/ | 1 | 289 | Agentes |
| monitor/ | 7 | 1.327 | Monitoreo |
| mantenimiento/ | 4 | 941 | Mantenimiento |
| scripts/pro/ | 37 | 8.469 | Pipeline |
| tests/ | 4 | 982 | Tests |
| config/ | 0 (JSON) | 1.315 | Configuración |
| docs/ | 0 (MD) | 1.674 | Documentación |

## Totales del sistema

| Métrica | Valor |
|---|---|
| Python activos | 64 archivos |
| Shell scripts | 52 archivos |
| Config JSON | 11 archivos |
| Documentación | 12 archivos MD |
| Servicios systemd | 15 + 4 user |
| Dockerfiles | 8 |
| Total líneas Python | ~16.865 |
| Total líneas Shell | ~3.191 |
| Líneas totales (todo) | ~23.000+ |
| Archivos totales | ~160 |

---

*Documento generado el 2026-06-05. Refleja el estado completo del ecosistema URA v4.0.*
*Archivo: docs/URA_AUDITOR_SISTEMAS_IA.md — No eliminar.*
