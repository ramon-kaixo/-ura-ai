# AUDITORÍA FORENSE COMPLETA v1.0.0

**Fecha:** 2026-07-20  
**Repositorio:** `ramon-kaixo/-ura-ai` (714 .py files, 66.279 líneas)  
**Hash HEAD:** `2d4087a`  
**Auditor:** opencode (forensic audit, multi-agent)

---

## 1. ARQUITECTURA

### 1.1 Dependencias circulares core↔motor

**Estado:** La circularidad conceptual existe pero no causa fallos en tiempo de importación.

| Dirección | Archivos | Líneas | Tipo |
|-----------|----------|--------|------|
| `motor/` → `core/` | 2 | 7 imports | ✅ Lazy (dentro de funciones) |
| `core/` → `motor/` | 13 | 21 imports | 🔴 Module-level |
| `knowledge/` → `motor/` | 5 | 8 imports | ✅ Lazy |
| `core/` → `knowledge/` | 0 | 0 | ✅ |

**Evidencia:**
- `motor/cli/cmd_ura.py` importa `validate_schema`, `validate_config`, `index_documents`, `ask`, `load_manifest` de `core/` (5 imports lazy)
- `motor/core/config.py:95` importa `CONFIG` de `core.config_manager` (lazy, dentro de `_load_config_dict`)
- `core/memory_engine.py:19-21` importa `UraConfig`, `generate`, `QdrantClient` de `motor/` (module-level)
- `core/mochila/providers/*.py` (5 providers) importan `DegradedMode` y `get_secret` de `motor/`

### 1.2 Capas invertidas

| Archivo | Línea | Problema |
|---------|-------|----------|
| `core/memory_engine.py` | 19-21 | Domain logic (core) importa framework (motor) a nivel de módulo |
| `core/debate/debate_engine.py` | 26 | Igual |
| `core/ura_multi_agent.py` | 35-36 | Igual |
| `core/auto_reindex.py` | 30-31 | Igual |
| `core/mochila/providers/ollama.py` | 6 | Provider legacy importa DegradedMode de motor/ |

**Riesgo:** `core/` (204 archivos originalmente) debería ser independiente de `motor/` (266 archivos). La dependencia está al revés de lo que describe la arquitectura.

### 1.3 Módulos sin consumidores (código muerto estructural)

**107 archivos con 0 importadores externos.** Resumen por paquete:

| Paquete | Archivos sin consumidores |
|---------|--------------------------|
| `core/` | 50 |
| `motor/` | 37 |
| `knowledge/` | 11 |
| `scripts/pro/` | 2 |
| `__init__.py` vacíos | 22 |

### 1.4 Archivos demasiado grandes

| Líneas | Archivo | Problema |
|--------|---------|----------|
| **1274** | `core/model_router.py` | 5 clases, 25+ funciones, mezcla HTTP server + VRAM + dashboard HTML |
| **730** | `core/mochila/mochila_server.py` | Monolítico: proxy streaming, guardian, health |
| **636** | `core/ura_multi_agent.py` | 5+ clases de agente en un solo archivo |
| **604** | `knowledge/engine/api.py` | FastAPI monolítico |
| **597** | `motor/core/qdrant_client.py` | 358 statements, 0% cobertura |
| **535** | `motor/core/llm/router.py` | Router monolítico |

### 1.5 Código duplicado severo

| Patrón | Duplicaciones | Archivos |
|--------|--------------|----------|
| `CircuitBreaker` | **4 implementaciones** | `core/mochila/`, `motor/core/llm/`, `motor/diagnostico/`, `motor/platform/` |
| `OllamaProvider` | **2 implementaciones** | `core/mochila/providers/`, `motor/core/llm/` |
| `GeminiProvider` | **2 implementaciones** | `core/mochila/providers/`, `motor/core/llm/` |
| `OpenRouterProvider` | **2 implementaciones** | `core/mochila/providers/`, `motor/core/llm/` |
| Providers OpenAI-compat | **~95% idénticos** | `deepseek.py`, `groq.py`, `gemini.py`, `openrouter.py` |
| `EventBus` | **2 implementaciones** | `motor/events/`, `knowledge/engine/eventbus.py` |
| Logging estructurado | **4 implementaciones** | `motor/observability/`, `motor/platform/`, `knowledge/engine/`, `core/` |

### 1.6 Violaciones ADR

| ADR | Violación | Archivo/Línea |
|-----|-----------|---------------|
| ADR-007 (Regla Núcleo) | `config.local.json` eliminado sin ADR específico | `core/config_manager.py` (commit F17) |
| ADR-007 | core→motor sin ADR de dependencia | 21 imports en core/ |
| ADR-007 | Funcionalidad removida (config.local.json) sin documento de degradación | No hay degradación documentada |

---

## 2. CÓDIGO MUERTO

### 2.1 Archivos nunca importados

| Archivo | Líneas | Notas |
|---------|--------|-------|
| `scripts/pro/backup_assistant.py` | 46 | Nunca referenciado |
| `scripts/pro/chaos_f29_b5.py` | 194 | Nunca referenciado |
| `core/seguridad/rollback_manager.py` | 52 | 0 cross-refs |
| `core/memoria/qdrant_store.py:190` | `MemoryPipelineStore` | 0 cross-refs |
| `core/memoria/consulta.py:113` | `PipelineConsultaRAG` | 0 cross-refs |
| `knowledge/engine/api.py:87-131` | 5 modelos Pydantic (SearchRequest, CompileResponse, etc.) | Nunca importados externamente |
| `knowledge/engine/rollback.py:28,64,101` | 3 clases (Savepoint, TransactionManager, CompileRollback) | Solo uso interno |
| `knowledge/engine/eventbus.py:47-65` | 3 eventos (MemoryCreated, MemoryUpdated, MemoryLinked) | 0 cross-refs |

**Total clases no instanciadas:** ~50

### 2.2 Archivos fantasma (`.nervioso/descarte/` aún importados)

| Archivo en descarte | Aún importado por |
|---------------------|-------------------|
| `assistant/learning.py` | 7 referencias activas |
| `assistant/management.py` | 5 referencias |
| `assistant/planner.py` | 9 referencias |
| `assistant/tools.py` | **37 referencias** |
| `assistant/web_search.py` | 7 referencias |

### 2.3 Config nunca cargada

| Archivo | Estado |
|---------|--------|
| `config/settings.json` | Config completo abandonado (Ollama URL, dashboard, security) |
| `deploy/lildax_config.json` | Solo referenciado en SECRETS_AUDIT.md, nunca cargado |

### 2.4 TODO/FIXME olvidados

**0 encontrados.** ✅ El código fue limpiado durante F29.

---

## 3. CALIDAD

### 3.1 Complejidad ciclomática

| Archivo | Anidamiento máx | Detalle |
|---------|----------------|---------|
| `core/mochila/mochila_server.py` | **10 niveles** | proxy_stream → try → if → def → async with → async with → async for → if → try → if → if |
| `core/model_router.py` | **7 niveles** | proxy_request con múltiples try/except |
| `motor/platform/tracing.py` | **6 niveles** | Varias funciones con anidamiento medio |

### 3.2 Funciones >100 líneas

| Líneas | Archivo | Función |
|--------|---------|---------|
| 118 | `motor/intelligence/agents/reflection.py:139` | `ReflectionAgent._reflect` |

### 3.3 Strings hardcodeados

| Tipo | Ocurrencias | Peligro |
|------|-------------|---------|
| IPs `10.164.1.99` | 6 archivos | No portátil fuera de GX10 |
| IPs `127.0.0.1` | **22+ archivos** | Puerto y host fijos |
| Paths `/home/ramon/` | **12 archivos** | No funciona en Mac u otros usuarios |
| Puertos mágicos | **30+** | 11434, 4096, 8192, 8000 esparcidos sin constantes |

### 3.4 `except: pass` sin logging

**36 ocurrencias** en 18+ archivos. Las más críticas:

| Archivo | Líneas | Contexto |
|---------|--------|----------|
| `motor/core/llm/__init__.py` | 28,34,40,46,52,58 | 6 bare excepts en bloque de registro de providers |
| `motor/cli/cmd_ura.py` | 173,185,255,273,284 | CLI silencia errores |
| `core/voice/tts_piper.py` | 67,100 | TTS playback silencia fallos |
| `core/mochila/status_endpoint.py` | 29,83,90 | Health check silencia errores |
| `knowledge/engine/archiver.py` | 231,238 | Archivado silencia fallos |

### 3.5 Archivos >1000 líneas (producción)

| Archivo | Líneas | Recomendación |
|---------|--------|---------------|
| `core/model_router.py` | 1274 | Dividir en package: routing/VRAM/dashboard/metrics |

---

## 4. CONCURRENCIA

### 4.1 Race conditions confirmadas

| Archivo | Línea | Problema |
|---------|-------|----------|
| `knowledge/engine/reader.py` | 30-66 | **🔴 RACE CONDITION**: `_READER_POOL` dict compartido sin lock. Dos hilos pueden entrar simultáneamente en `if spath not in _READER_POOL`. |
| `knowledge/engine/sqlite_writer.py` | 50 | **🔴 RACE CONDITION**: `_SHOULD_CANCEL` flag escrito desde signal handler y leído sin lock |

### 4.2 Async bloqueante

| Archivo | Línea | Problema |
|---------|-------|----------|
| `motor/assistant/executor.py` | 312-334 | `execute()` llama handlers síncronos (`git_status`, `docker_ps`, `python`, `read_file`) desde `async def`, bloqueando el event loop |
| `motor/assistant/api.py` | 53 | `threading.Lock()` en contexto FastAPI async (debería ser `asyncio.Lock()`) |

### 4.3 Thread pool leak

| Archivo | Línea | Problema |
|---------|-------|----------|
| `motor/events/bus.py` | 53 | `publish_async()` crea un `threading.Thread` **por llamada** sin pool ni límite |

### 4.4 SQLite concurrente en async

| Archivo | Línea | Patrón |
|---------|-------|--------|
| `motor/assistant/preferences.py` | 30 | `check_same_thread=False` con `threading.Lock()` — bloquea event loop |
| `motor/assistant/proactive_memory.py` | 54 | Mismo patrón |
| `motor/intelligence/memory/episodic.py` | 113 | Mismo patrón con `RLock` |

---

## 5. MEMORIA

### 5.1 Fugas de memoria confirmadas

| Archivo | Línea | Objeto | Crecimiento |
|---------|-------|--------|-------------|
| `motor/platform/tracing.py` | 567,572 | `SpanEventEmitter.events: list[SpanEvent]` | **🔴 SIN LÍMITE** — `emit()` acumula eventos. `clear()` nunca se llama automáticamente. |
| `motor/platform/tracing.py` | 808,813 | `DurationHistogram.durations_ns: list[int]` | **🔴 SIN LÍMITE** — percentiles computados pero lista nunca se trima |
| `motor/core/llm/observability.py` | 22,42 | `LLMMetrics._calls: dict[str, list[float]]` | **🔴 SIN LÍMITE** — latencias acumuladas indefinidamente |
| `motor/core/llm/observability.py` | 24,51 | `LLMMetrics._tokens: dict[str, list[float]]` | **🔴 SIN LÍMITE** — token tracking sin evicción |

### 5.2 Caches sin límite de tamaño

| Archivo | Línea | Cache | Problema |
|---------|-------|-------|----------|
| `core/model_router.py` | 482-504 | `PromptCache.cache` dict | TTL sí, max-size no |
| `motor/assistant/preferences.py` | 24 | `self._cache` | Sin límite de tamaño |

### 5.3 Listas acotadas correctamente ✅

| Archivo | Línea | Límite |
|---------|-------|--------|
| `core/model_router.py:447` | `metrics_history` | 1000 (pop) |
| `motor/core/llm/baseline.py:160-161` | `samples` | pop(0) |
| `motor/core/llm/monitor.py:183-185` | `_history` | pop(0) |
| `motor/core/llm/profiler.py:91` | `_profiles` | 1000 |
| `motor/platform/audit.py:64-65` | eventos | _trim |

---

## 6. RENDIMIENTO

### 6.1 Lecturas duplicadas

| Archivo | Línea | Problema |
|---------|-------|----------|
| `motor/memory/journal.py:69` | `f.read()` | Archivo entero en memoria en `read_all()` |
| `motor/memory/snapshot.py:83` | `f.read()` | Snapshot entero en memoria |

### 6.2 Imports pesados no optimizados

| Import | Paquete | Tamaño estimado |
|--------|---------|----------------|
| `from motor.core.llm import generate` | Carga todo motor/core/llm/ | 14 módulos, ~1500 líneas |
| `import anthropic` | SDK Anthropic | ~100 dependencias transitivas |
| `import openai` | SDK OpenAI | Similar |

### 6.3 Sin lazy loading en hot paths

- `core/memory_engine.py:19-21` importa `motor.core.llm`, `motor.core.qdrant_client`, `motor.core.config` a nivel de módulo —> todo se carga al importar memory_engine

---

## 7. SEGURIDAD

### 7.1 CRÍTICO — Secretos hardcodeados en repositorio

| Archivo | Línea | Secreto | Estado |
|---------|-------|---------|--------|
| `hetzner.env` | 1 | `HCLOUD_TOKEN=hc_token_99a1bc24e75df42b01cc08ea9143df22eb9031ef11cda029b3` | 🔴 COMMITEADO |
| `backups/env/.env.2026-06-18` | 4 | `OPENROUTER_API_KEY=sk-or-v1-933dd2401a4929a0b4b63880ad...` | 🔴 COMMITEADO |
| `backups/env/.env.2026-06-18` | 1 | `URA_API_KEY="ura_prod_key_2026"` | 🔴 COMMITEADO |
| `scripts/pro/gx10-api.service` | 10 | `URA_TOKEN=ura_blackwell_2026` | 🔴 COMMITEADO |
| `deploy/docker/docker-compose.yml` | 23,41,63,113 | 4 contraseñas por defecto (`ura_webui_secret_2026`, `ura_n8n_key`, `ura_cam_2026`, `grafana123`) | 🟡 Hardcodeadas |

### 7.2 CRÍTICO — Code injection

| Archivo | Línea | Vector | By-passeable |
|---------|-------|--------|-------------|
| `agent_hierarchy.py` | 514-521 | `subprocess.run(["python3", "-c", code])` | Sí — `__import__('os').popen(...)` elude el blacklist |
| `knowledge/engine/rules.py` | 277 | `eval(code, {"__builtins__": {}}, env)` | Sí — subclasses de object permiten acceso a `__import__` |
| `core/voice/anker_mac_pipeline.py` | 70-75 | AppleScript injection via osascript | Sí — comillas en message inyectan comandos |

### 7.3 ALTO — npm install sin validación

| Archivo | Línea | Problema |
|---------|-------|----------|
| `agent_hierarchy.py` | 403-404 | `npm install {package}` solo valida `package.startswith("--")` |

### 7.4 MEDIO — Insecure tempfile

| Archivo | Línea | Problema |
|---------|-------|----------|
| `scripts/pro/chaos_f29_b5.py` | 23 | `tempfile.mktemp()` — TOCTOU race |

---

## 8. TESTING

### 8.1 Tests rotos (no coleccionan)

| Archivo | Error | Causa |
|---------|-------|-------|
| `tests/test_extractors.py` | `ImportError: StrEnum` | `knowledge/engine/_compat.py` no exporta `StrEnum` |
| `tests/test_fase7.py` | Mismo | Misma causa |
| `tests/test_knowledge_engine.py` | Mismo | Misma causa |
| `tests/test_vector_base.py` | Mismo | Misma causa |
| `tests/test_vector_ollama.py` | Mismo | Misma causa |
| `tests/test_vector_qdrant.py` | Mismo | Misma causa |
| `tests/test_vector_retriever.py` | Mismo | Misma causa |
| `tests/test_vector_subscriber.py` | Mismo | Misma causa |

**8 tests no pueden ni importarse.** La raíz: `knowledge/engine/_compat.py` no reexporta `StrEnum` de stdlib.

### 8.2 Tests que fallan

| Archivo | Fallos | Causa |
|---------|--------|-------|
| `motor/tests/test_fusion.py` | 5 | `make_fact_id()` cambió API (versión parameter) pero tests no actualizados |
| `tests/test_ci_cd.py` | 5 | pyproject.toml y workflows no coinciden con expectativas de test |
| `tests/test_obs_tracing.py` | 3 (flaky) | Concurrencia/timing |

### 8.3 Cobertura

| Medida | Valor |
|--------|-------|
| Cobertura global | **19.28%** |
| Threshold pyproject.toml | 20% (recién ajustado de 30%) |
| `core/*` | **~0%** |
| `motor/core/llm/*` | **~0%** |
| `motor/agents/*` | **~0%** |
| `knowledge/engine/*` | **0%** (no importa) |
| `motor/platform/*` | 0-93% |
| Tests totales | **3,218 pytest + 230 custom check()** |
| Tests saltados permanentemente | 8 (test_integration_assistant.py) |

### 8.4 Tests legacy invisibles a pytest

| Archivo | Checks | Framework |
|---------|--------|-----------|
| `tests/test_unit.py` | 148 | `check()` + `__main__` |
| `tests/test_sda.py` | 75 | `check()` + `__main__` |
| `tests/test_integration.py` | 7 | `check()` + GX10 real |

### 8.5 Network leak en test suite

| Archivo | Línea | Problema |
|---------|-------|----------|
| `tests/test_audit_api.py` | (indirecto) | `TestClient(app)` activa router real que llama a Ollama HTTP — bloquea suite completa |

---

## 9. DOCUMENTACIÓN

### 9.1 Archivos faltantes

| Archivo | Referenciado en | Impacto |
|---------|----------------|---------|
| `CLAUDE.md` | `AGENTS.md:353` | Claude Code incompatible |
| `docs/CHANGELOG.md` | `README.md:171` | Documentación faltante |
| `docs/architecture/FASEN_CLOSEOUT.md` | `AGENTS.md:82` | Template no realizado |

### 9.2 Inconsistencias AGENTS.md vs realidad

| AGENTS.md dice | Realidad |
|----------------|----------|
| "~146 archivos" en scripts/pro/ | **186 archivos** |
| "CLAUDE.md — Symlink to AGENTS.md" | **No existe** |
| F28 "Pending stabilization" pero F28.1 "Closed" | Contradictorio |
| `motor/tests/` en ruta de tests | No existe como directorio |

### 9.3 README desactualizado

| Afirmación | Realidad |
|-----------|----------|
| `pip install ura` | No hay paquete en PyPI |
| README estructura de proyecto omite `core/` | core/ tiene 90 archivos activos |
| `pytest -q --tb=line tests/ motor/tests/` | `motor/tests/` no existe |

---

## 10. DEPENDENCIAS

### 10.1 Paquetes listados pero nunca importados (13)

| Paquete | requirements | pyproject.toml |
|---------|-------------|----------------|
| `click` | ✅ base.txt:5 | ✅ línea 21 |
| `rich` | ✅ base.txt:6 | ✅ línea 22 |
| `coloredlogs` | ✅ base.txt:38 | ✅ línea 39 |
| `orjson` | ✅ base.txt:13 | ✅ línea 24 |
| `typer` | ✅ base.txt:7 | ✅ línea 37 |
| `tiktoken` | ✅ base.txt:30 | ✅ llm extra |
| `tokenizers` | ✅ base.txt:31 | ✅ llm extra |
| `mkdocs` | ✅ dev.txt:24 | ✅ docs extra |
| `mkdocs-material` | ✅ dev.txt:25 | ✅ docs extra |
| `pygments` | ✅ base.txt:8 | ✅ docs extra |
| `safetensors` | ✅ gpu.txt:11 | ✅ gpu extra |
| `scipy` | ✅ gpu.txt:8 | ✅ gpu extra |
| `torchvision` | ✅ gpu.txt:6 | ✅ gpu extra |

### 10.2 Paquetes importados pero no listados (7)

| Paquete | Archivos | Uso |
|---------|----------|-----|
| `psutil` | 4 scripts | Load testing, profiling |
| `pyzmq` | `core/event_bus.py`, `core/model_router.py` | **Infraestructura central sin dependencia declarada** |
| `sounddevice` | 3 archivos voice/ | TTS playback |
| `soundfile` | `core/voice/tts_piper.py` | Audio file I/O |
| `whisper` | `core/voice/anker_pipeline.py` | Speech-to-text |
| `pyautogui` | 2 RPA scripts | Automatización GUI |
| `json_repair` | `scripts/pro/compilador_opiniones.py` | JSON recovery |

### 10.3 Archivos de requisitos redundantes

| Archivo | Contenido | Verdict |
|---------|-----------|---------|
| `requirements/legacy.txt` | `-r requirements/dev.txt` | ❌ Muerto |
| `requirements.txt` (raíz) | `-r requirements/dev.txt` | ❌ Muerto (solo Docker) |

---

## 11. GIT

### 11.1 Ramas

| Rama | Estado |
|------|--------|
| `main` | ✅ Activa |
| `master` | ❌ Stale (divergida) |
| `dev/v3.1-expansion` | ⚠️ Sin merge a main |
| `origin/plan-refinado` | ⚠️ Default branch cambiada pero remoto puede persistir |

### 11.2 Tags

109 tags desde `v0.4.0-fase6` hasta `v1.1.0`. ✅ Bien organizados.

### 11.3 Archivos grandes en historial (~102MB inflando .git a 304MB)

| Objeto | Tamaño | Archivo |
|--------|--------|---------|
| `0d04c70` | 24.5 MB | `.venv/bin/ruff` |
| `b15fcf8` | 23.2 MB | `models/reranker/model.onnx` |
| `8eb5d17` | 18.9 MB | `ura_paquete_nivel4.zip` |
| `a349619` | 18.6 MB | `.git.corrompido.backup.20260530/objects/...` |
| `7b7ef8e` | 16.9 MB | `.git.corrompido.backup.20260530/objects/pack/...` |

### 11.4 `.gitignore` gaps

| Patrón | Estado |
|--------|--------|
| `*.pdb`, `*.dmp`, `*.core`, `*.hprof` | ❌ No cubiertos |

### 11.5 `.gitattributes`

**No existe.** ❌ Sin LFS para binarios grandes.

---

## 12. PRODUCCIÓN

### 12.1 CI/CD

| Workflow | Problemas |
|----------|-----------|
| `ci.yml:21` | `pip install ruff` sin versión fija |
| `ci.yml:33` | Dependencias de mypy manuales, pueden desincronizarse |
| `ci.yml:48` | Solo 12 de 145+ test files (no corre el suite completo) |
| `ci.yml:60` | Bandit solo cubre `motor/` — omite `core/`, `knowledge/`, `scripts/` |
| `publish.yml:7` | Dispara en cualquier `v*` tag (ej: `v0.14.4-b1`) |
| `release.yml:38` | `secrets.PYPI_TOKEN` no configurado en repo |

### 12.2 Docker

| Archivo | Problema |
|---------|----------|
| `Dockerfile:20` | `python:3.12-slim` sin digest pin |
| `Dockerfile:37` | `COPY . .` copia todo el repo (potenciales secretos) |
| `deploy/docker/Dockerfile:12` | Instala `x11-apps` en servidor |
| `deploy/docker/docker-compose.yml:*` | Usa `:latest` tags para Prometheus, Grafana, Frigate, n8n |
| `deploy/docker/docker-compose.yml:23,41,63,113` | **4 contraseñas por defecto hardcodeadas** |

### 12.3 Systemd

| Servicio | Problema |
|----------|----------|
| `deploy/opencode.service` | ✅ Secrets movidos a EnvironmentFile (arreglado hoy) |
| `deploy/ia-flujo.service` | ❌ `ExecStart` apunta a `app/flujo_constante.py` que **no existe** |
| `scripts/pro/gx10-api.service:10` | 🔴 `URA_TOKEN=ura_blackwell_2026` hardcodeado |
| `scripts/pro/gx10-api.service:9,16` | Paths absolutos fuera del repo (`/opt/ura/`) |
| `deploy/rotate-logs.service:7` | `User=root` innecesario |

### 12.4 Logging (4 sistemas compitiendo)

| Sistema | Archivo | Formato |
|---------|---------|---------|
| Observability | `motor/observability/logging.py` | JSON + correlation_id + workflow_id |
| Platform | `motor/platform/logging.py` | JSON + component/operation/trace_id |
| Knowledge | `knowledge/engine/logging_config.py` | JSON (solo si URA_STRUCTURED_LOGS=true) |
| Core | `core/json_logger.py` | JSON básico |

---

## 13. MANTENIBILIDAD

### 13.1 Qué eliminarías

| Archivo | Razón |
|---------|-------|
| `requirements/legacy.txt` | Muerto, redundante con requirements.txt |
| `requirements.txt` (raíz) | Muerto, redundante con pyproject.toml |
| `config/settings.json` | Nunca cargado, superseded por system_config.json |
| `deploy/lildax_config.json` | Nunca cargado, contiene password hardcodeada |
| `backups/env/.env.2026-06-18` | Backup con secrets commiteados |
| `hetzner.env` | Secret commiteado |
| `scripts/pro/backup_assistant.py` | 0 referencias |
| `scripts/pro/chaos_f29_b5.py` | 0 referencias |
| `.nervioso/descarte/` (5 archivos) | Marcados como descarte pero aún importados — eliminar o mover imports |
| `deploy/ia-flujo.service` | Referencia archivo que no existe |
| `master` branch | Stale, confunde con main |
| Archivos grandes en historial | .venv/bin/ruff, .onnx, .zip, .git.corrompido.backup |

### 13.2 Qué fusionarías

| Fusión | Archivos | Beneficio |
|--------|----------|-----------|
| CircuitBreaker → 1 | 4 archivos → 1 | Elimina 3 implementaciones duplicadas |
| Providers → 1 | `core/mochila/providers/` + `motor/core/llm/` | Elimina 6 providers duplicados |
| EventBus → 1 | `motor/events/` + `knowledge/engine/eventbus.py` | EventBus único |
| Logging → 1 | 4 sistemas → 1 | Logging consistente |
| `core/memoria/` + `motor/intelligence/memory/` | ~3000 líneas duplicadas | Una capa de memoria |

### 13.3 Qué reescribirías

| Archivo | Razón |
|---------|-------|
| `agent_hierarchy.py` | Code injection (python3 -c) + npm install sin validación |
| `knowledge/engine/rules.py:277` | `eval()` en producción, aunque con sandbox |
| `motor/assistant/executor.py:312-334` | Async bloqueante con handlers síncronos |
| `motor/platform/tracing.py:567,808` | Memory leak por listas sin límite |
| `motor/core/llm/observability.py:22,42` | Memory leak por diccionarios sin límite |

### 13.4 Qué dividirías

| Archivo (líneas) | Propuesta |
|------------------|-----------|
| `core/model_router.py` (1274) | package: router/ + vram/ + dashboard/ + metrics/ |
| `core/mochila/mochila_server.py` (730) | handlers/ + middleware/ + models/ |
| `core/ura_multi_agent.py` (636) | agents/ separados |
| `motor/tests/test_fusion.py` (1164) | test_fusion_*.py (varios) |

### 13.5 Qué dejarías igual

| Archivo | Razón |
|---------|-------|
| `motor/core/config.py` | ✅ UraConfig único, bien diseñado |
| `motor/core/secrets.py` | ✅ Gestión de secretos correcta |
| `motor/core/state.py` | ✅ DegradedMode bien implementado |
| `motor/platform/models.py` | ✅ Modelos de protocolo |
| `motor/memory/` | ✅ Arquitectura sólida (Timeline/Journal/Snapshot) |
| `motor/events/bus.py` | ✅ EventBus tipado (excepto thread leak) |
| `motor/observability/` | ✅ Buena base de observabilidad |
| `motor/plugin/` | ✅ Arquitectura de plugins correcta |

---

## 14. MATRIZ DE RESULTADOS

| Categoría | P0 | P1 | P2 | P3 | Total |
|-----------|----|----|----|----|-------|
| Arquitectura | 1 | 4 | 2 | 1 | 8 |
| Código muerto | 0 | 2 | 3 | 2 | 7 |
| Calidad | 1 | 3 | 4 | 1 | 9 |
| Concurrencia | 0 | 3 | 2 | 1 | 6 |
| Memoria | 3 | 0 | 2 | 0 | 5 |
| Rendimiento | 0 | 2 | 0 | 1 | 3 |
| Seguridad | 4 | 2 | 2 | 1 | 9 |
| Testing | 1 | 4 | 2 | 2 | 9 |
| Documentación | 0 | 1 | 2 | 3 | 6 |
| Dependencias | 0 | 1 | 3 | 2 | 6 |
| Git | 0 | 1 | 2 | 1 | 4 |
| Producción | 0 | 4 | 3 | 2 | 9 |
| **Total** | **10** | **27** | **26** | **17** | **80** |

### Matriz final por categoría

| Categoría | Estado | Nota /10 | Justificación |
|-----------|--------|----------|---------------|
| Arquitectura | 🟡 Regular | 5/10 | Core↔motor invertido, 107 archivos sin consumer, 4 CircuitBreakers, providers duplicados |
| Código muerto | 🟡 Regular | 5/10 | ~50 clases nunca usadas, 2 scripts huérfanos, 5 archivos descarte aún activos |
| Calidad | 🟠 Deficiente | 4/10 | 36 bare excepts, 30+ números mágicos, 22+ IPs hardcodeadas, nesting profundidad 10 |
| Concurrencia | 🟡 Regular | 5/10 | Race condition en reader.py, async bloqueante, thread leak, SQLite en async |
| Memoria | 🔴 Grave | 3/10 | 4 fugas confirmadas en tracing.py y observability.py (producción) |
| Rendimiento | 🟢 Aceptable | 7/10 | Sin O(n²) graves, pero imports pesados sin lazy loading |
| Seguridad | 🔴 Grave | 3/10 | 4 secretos commiteados, code injection, eval() en prod, 4 docker-compose passwords default |
| Testing | 🟠 Deficiente | 4/10 | 8 tests rotos, cobertura 19%, 3 suites legacy invisibles, CI solo corre 12 tests |
| Documentación | 🟡 Regular | 5/10 | 3 archivos faltantes, AGENTS.md desincronizado, README desactualizado |
| Dependencias | 🟡 Regular | 5/10 | 13 paquetes no usados, 7 no declarados, pyzmq sin dependencia |
| Git | 🟡 Regular | 5/10 | 304MB .git, 102MB blobs grandes, sin LFS, sin .gitattributes |
| Producción | 🟠 Deficiente | 4/10 | 4 servicios systemd rotos, logging fragmentado, CI parcial, Docker inseguro |
| **Media ponderada** | | **4.5/10** | |

---

## 15. CONCLUSIÓN

### ¿El repositorio está realmente preparado para producción?

**NO.** El repositorio no está preparado para producción. La puntuación media de 4.5/10 refleja problemas graves en seguridad (3/10), memoria (3/10), testing (4/10) y calidad (4/10) que impedirían un despliegue responsable.

### ¿Qué porcentaje estimas que está realmente terminado?

**~35-40%.** El esqueleto arquitectónico está bien (motor/core/config.py, motor/memory/, motor/platform/models.py, motor/events/), pero aproximadamente el 60% del código es legacy (core/) no migrado, duplicado o muerto. La cobertura de tests del 19% confirma que la validación está incompleta.

### ¿Cuál es el mayor riesgo técnico del proyecto?

**El mayor riesgo técnico es la fragmentación y el código muerto.** Hay 4 implementaciones de CircuitBreaker, 106 archivos sin consumidores, 4 sistemas de logging, 2 EventBus, 2 OllamaProviders, 2 capas de memoria, 2 sistemas de agentes. Cualquier cambio en un área afecta a múltiples implementaciones, y nadie sabe cuál es la "correcta". Esto hace que el coste de mantenimiento sea ~4x más alto de lo necesario y que cualquier refactorización tenga alta probabilidad de romper algo inesperado.

**Segundo mayor riesgo:** Las 4 fugas de memoria confirmadas en tracing.py y observability.py. En un servicio 24/7 (como los systemd que ejecutan API y modelo router), estas fugas causarán OOM en días o semanas dependiendo del tráfico.

### ¿Qué harías antes de desarrollar una sola funcionalidad nueva?

En orden:

1. **🔴 Rotar los 4 secretos commiteados** (hetzner.env, backups/env/, gx10-api.service) y limpiar del historial git
2. **🔴 Arreglar fugas de memoria** en `motor/platform/tracing.py` y `motor/core/llm/observability.py` (añadir límites de tamaño)
3. **🔴 Arreglar `knowledge/engine/_compat.py`** para que exporte `StrEnum` y desbloquear 8 tests
4. **🟡 Consolidar CircuitBreaker** (4 → 1) y **logging** (4 → 1)
5. **🟡 Eliminar los 107 archivos sin consumidores** empezando por scripts huérfanos y `.nervioso/descarte/`
6. **🟡 Migrar `core/` providers a `motor/core/llm/`** y eliminar `core/mochila/providers/`
7. **🟡 Arreglar race condition** en `knowledge/engine/reader.py`
8. **🟡 Purgar historial git** (102MB en blobs grandes) y añadir `.gitattributes` + LFS
9. **🟢 Expandir CI** para correr el suite completo de tests
10. **🟢 Arreglar README** y sincronizar AGENTS.md con realidad

**Esfuerzo estimado:** ~3-4 semanas para items 1-8 (lo crítico). ~6-8 semanas para items 9-10 más la consolidación arquitectónica completa.
