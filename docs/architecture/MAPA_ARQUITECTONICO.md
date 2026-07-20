# MAPA ARQUITECTÓNICO — URA v1.1.0

**Fecha:** 2026-07-20  
**Propósito:** Inventario completo de directorios, responsabilidades, consumidores, duplicidades.

---

## core/ — Domain logic legacy (90 archivos)

| Subdirectorio | Responsabilidad | Consumers externos | Dependencias | % usado | Duplicidad | ¿Eliminar? | ¿Fusionar? |
|---|---|---|---|---|---|---|---|
| `core/memoria/` | Knowledge extraction pipeline (mochila) | `core/mochila/mochila_server.py` | httpx, motor.core.qdrant_client | ~30% | `motor/intelligence/memory/` cubre lo mismo | ❌ En uso activo | 🟡 Con motor/intelligence/memory cuando mochila migre |
| `core/mochila/` | Mochila HTTP server + providers + tools | Scripts, systemd | httpx, motor.core.state, motor.core.secrets | ~60% | `motor/core/llm/` (providers duplicados) | ❌ En uso activo | 🟡 Providers → motor/core/llm |
| `core/model_router.py` | Model Router HTTP server (1274 líneas) | systemd, scripts | httpx, motor.core.secrets | 100% | Ninguna | ❌ En uso activo | 🟡 Dividir por responsabilidad |
| `core/ura_multi_agent.py` | Multi-agent runtime (636 líneas) | `core/debate/debate_engine.py` | motor.core.llm | ~50% | `motor/agents/` | ❌ En uso activo | 🟡 Con motor/agents/ |
| `core/memory_engine.py` | Knowledge engine entry point | scripts | motor.core.config, motor.core.llm, motor.core.qdrant_client | 100% | Ninguna | ❌ En uso activo | ❌ No |
| `core/event_bus.py` | ZMQ EventBus (144 líneas) | `core/memory_engine.py` | pyzmq | ~20% | `motor/events/bus.py` | 🟡 Zombie (motor/events/ es el activo) | 🟡 Con motor/events/ |
| `core/voice/` | TTS + STT pipeline (3 archivos) | scripts | sounddevice, soundfile, whisper | ~10% | Ninguna | ❌ En uso por sistema de voz | ❌ No |
| `core/debate/` | Agent debate engine (3 archivos) | `core/ura_multi_agent.py` | httpx | 100% | `motor/agents/` | ❌ En uso activo | 🟡 Con motor/agents/ |
| `core/notifier.py` | Telegram + Pushover (46 líneas) | 0 directos | httpx | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `core/seguridad/` | Rollback manager (52 líneas) | 0 directos | pathlib | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `core/search_logger.py` | Search logging (79 líneas) | 0 directos | sqlite3 | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `core/scraper_pool.py` | Web scraper pool (50 líneas) | 0 directos | httpx | 0% | `motor/core/web/` | 🔴 Muerto | 🟡 Con motor/core/web/ |
| `core/sandbox.py` | Docker sandbox (108 líneas) | scripts | docker | ~10% | Ninguna | 🟡 Legacy pero usado | ❌ No |
| `core/inferencia/` | Inference engine (32 líneas) | 0 directos | httpx | 0% | `motor/core/llm/` | 🔴 Muerto | 🟡 Con motor/core/llm/ |
| `core/infra/` | Heartbeat + state (157 líneas) | 0 directos | httpx | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `core/cleaner/` | Code refactoring (106 líneas) | 0 directos | ast | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `core/guardian_disco.py` | Disk guardian (114 líneas) | scripts | subprocess | ~10% | Ninguna | ❌ En uso | ❌ No |
| `core/query_cache.py` | Query cache (32 líneas) | 0 directos | sqlite3 | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |

### core/ total: 90 archivos, ~30% realmente usado

---

## motor/ — Motor framework (266 archivos)

| Subdirectorio | Responsabilidad | Consumers externos | Dependencias | % usado | Duplicidad | ¿Eliminar? | ¿Fusionar? |
|---|---|---|---|---|---|---|---|
| `motor/core/config.py` | UraConfig único | Toda la base | core.config_manager (lazy) | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/core/secrets.py` | Gestión de secretos | Toda la base | os, env | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/core/state.py` | DegradedMode | core/mochila/providers/ | threading | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/core/llm/` | LLM providers (14 archivos) | core/*, motor/assistant/ | httpx | ~60% | core/mochila/providers/ | ❌ Canónico | 🟡 Fusionar core/mochila/providers → aquí |
| `motor/core/qdrant_client.py` | Qdrant client wrapper | core/*, knowledge/ | httpx | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/core/fusion/` | F25 Knowledge Fusion | 0 directos | sqlite3 | ~20% | Ninguna | ❌ Implementado pero sin consumidores externos | ❌ No |
| `motor/core/evaluation/` | Evaluación KE (6 archivos) | tests | numpy | ~30% | Ninguna | ❌ Tests | ❌ No |
| `motor/core/web/` | Web scraper pipeline | 0 directos | httpx | ~10% | core/scraper_pool.py | 🟡 Sobrediseñado | 🟡 Simplificar |
| `motor/core/executor.py` | Subprocess executor | tests | subprocess | ~50% | Ninguna | ❌ En uso | ❌ No |
| `motor/events/` | EventBus tipado (6 archivos) | motor/agents/, motor/core/fusion/ | threading | ~40% | core/event_bus.py | ❌ Canónico | 🟡 Fusionar core/event_bus.py → aquí |
| `motor/memory/` | F26 Historical Memory | tests, scripts | sqlite3, crypto | ~40% | core/memoria/ (diferente propósito) | ❌ Canónico | ❌ No (son diferentes) |
| `motor/agents/` | F27 Autonomous Agents | 0 directos | motor/events/, motor/platform/ | ~20% | core/ura_multi_agent.py, core/debate/ | ❌ Canónico | 🟡 Fusionar core/agents → aquí |
| `motor/platform/` | F28 Platform Protocols | motor/agents/ | Ninguna | ~40% | Ninguna | ❌ Canónico | ❌ No |
| `motor/observability/` | Métricas + logging + health | tests | prometheus_client | ~50% | core/json_logger.py, motor/platform/logging.py | ❌ Canónico (logging ya fusionado) | ❌ No |
| `motor/intelligence/` | Chunking + retrieval + memory | tests | numpy, motor/core/llm/ | ~20% | core/memoria/ (memoria), core/chunking.py | ❌ Canónico | 🟡 Fusionar core/chunking.py → aquí |
| `motor/plugin/` | Plugin system (5 archivos) | tests | yaml | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/pipeline/` | Pipeline dinámico (5 archivos) | 0 directos | yaml | ~20% | Ninguna | ❌ Canónico | ❌ No |
| `motor/cli/` | CLI commands (7 archivos) | ura.py (entry point) | motor.core.config | 100% | Ninguna | ❌ Canónico | ❌ No |
| `motor/assistant/` | Conversational assistant | scripts, systemd | httpx, sqlite3 | ~80% | core/mochila/mochila_server.py | ❌ Canónico | 🟡 Fusionar core/mochila → aquí |
| `motor/scanner/` | HW/network scanner | 0 directos | subprocess | ~10% | Ninguna | 🟡 Implementado pero sin uso | 🟡 Evaluar eliminar |
| `motor/diagnostico/` | Diagnóstico (4 archivos) | 0 directos | Ninguna | ~10% | Ninguna | 🟡 Implementado pero sin uso | 🟡 Evaluar eliminar |
| `motor/guard/` | Preflight + verifier | 0 directos | httpx | ~10% | Ninguna | 🟡 Implementado pero sin uso | 🟡 Evaluar eliminar |

### motor/ total: 266 archivos, ~40% realmente usado

---

## knowledge/engine/ — Knowledge Engine (35 archivos)

| Subdirectorio | Responsabilidad | Consumers externos | Dependencias | % usado | Duplicidad | ¿Eliminar? | ¿Fusionar? |
|---|---|---|---|---|---|---|---|
| `knowledge/engine/models.py` | Modelos de datos | knowledge/*, tests | pydantic | 100% | motor/ (parcial) | ❌ Canónico | ❌ No |
| `knowledge/engine/reader.py` | Consultas al grafo | knowledge/* | sqlite3, qdrant | 100% | Ninguna | ❌ Canónico | ❌ No |
| `knowledge/engine/api.py` | FastAPI HTTP API | scripts, systemd | fastapi, motor.core.secrets | 100% | motor/assistant/api.py (parcial) | ❌ En uso | ❌ No |
| `knowledge/engine/rules.py` | Reglas de calidad (508 líneas) | knowledge/engine/pipeline.py | ast | 100% | Ninguna | ❌ Canónico | ❌ No |
| `knowledge/engine/rollback.py` | Compile rollback (150 líneas) | 0 directos | sqlite3 | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `knowledge/engine/eventbus.py` | Knowledge EventBus | 0 directos | threading | 0% | motor/events/bus.py | 🔴 Muerto | 🟡 Fusionar con motor/events/ |
| `knowledge/engine/extraction_service.py` | Extracción (508 líneas) | tests | motor.core.llm | ~30% | Ninguna | ❌ En uso por tests | ❌ No |
| `knowledge/engine/notify.py` | Slack + Email | 0 directos | smtplib | 0% | core/notifier.py | 🔴 Muerto | ❌ Eliminar |
| `knowledge/engine/collector.py` | Collector web | 0 directos | httpx | 0% | motor/core/web/ | 🔴 Muerto | 🟡 Con motor/core/web/ |
| `knowledge/engine/archiver.py` | Archivado de documentos | 0 directos | shutil | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `knowledge/engine/deduction.py` | Deducción lógica | 0 directos | Ninguna | 0% | Ninguna | 🔴 Muerto | ❌ Eliminar |
| `knowledge/engine/logging_config.py` | Logging (96→20 líneas) | knowledge/* | motor.observability.logging | ~30% | ✅ Ya delega en motor/ | 🟡 Legacy | ❌ Ya fusionado |

### knowledge/ total: 35 archivos, ~30% realmente usado

---

## scripts/pro/ — Scripts de pipeline (186 archivos)

| Categoría | Count | Estado |
|---|---|---|
| Tuneladora (mantenimiento pipeline) | 3 | ✅ Activos |
| Diagnóstico/mantenimiento | ~20 | ✅ Activos |
| Refactor | ~5 | ⚠️ Algunos legacy |
| Consciencia/memoria | ~5 | ✅ Activos |
| Model Router | ~5 | ✅ Activos |
| OpenClaw | ~5 | ✅ Activos |
| Ejecución/servicios | ~8 | ✅ Activos |
| Sandbox | ~3 | ✅ Activos |
| Utilidades | ~15 | ✅ Activos |
| GPU/sistema | ~8 | ✅ Activos |
| Red/backup | ~15 | ✅ Activos |
| Hetzner | ~12 | ✅ Activos |
| Auditoría | ~15 | ✅ Activos |
| RPA/cámaras | ~8 | ✅ Activos |
| Instalación/deploy | ~12 | ✅ Activos |
| Pipeline voz/visión | ~5 | ✅ Activos |
| Evolución/ciclo | ~8 | ✅ Activos |
| Config/templates | ~8 | ✅ Activos |
| ura-query | 1 | ✅ Activo |
| **No referenciados** | **2** (backup_assistant.py, chaos_f29_b5.py) | 🔴 Muertos |

### scripts/pro/ total: 186 archivos, ~99% realmente usado

---

## tests/ — Tests (145 archivos, 3,218+ tests)

| Categoría | Count | Estado |
|---|---|---|
| Test files (pytest) | 145 | ⚠️ 8 rotos (StrEnum) |
| Test functions | 3,218 | ⚠️ 5 fallos en test_fusion.py, 5 en test_ci_cd.py |
| Tests legacy (check()) | 230 | 🟡 No integrados con pytest |
| Cobertura global | 19.28% | 🔴 Por debajo del 20% threshold |

---

## MAPA DE DUPLICIDADES (resumen ejecutivo)

| Patrón duplicado | Implementaciones | Archivos | Acción prioritaria |
|---|---|---|---|
| **CircuitBreaker** | ~~4~~ → 2 (1 canónica + 1 legacy mochila) | ✅ **HECHO** | Migrar mochila cuando se consoliden providers |
| **LLM Providers** | core/mochila/providers/ (6) + motor/core/llm/ (8) | 14 archivos | 🔴 Migrar core→motor |
| **EventBus** | core/event_bus.py + motor/events/bus.py | 2 | 🟡 Fusionar |
| **Logging** | ~~4~~ → 1 | ✅ **HECHO** | — |
| **Memory layer** | core/memoria/ + motor/intelligence/memory/ | ~3,000 líneas | 🟡 Fusionar |
| **Agent system** | core/ura_multi_agent.py + motor/agents/ | ~1,000 líneas | 🟡 Fusionar |
| **Ollama Provider** | core/mochila/providers/ollama.py + motor/core/llm/ollama.py | 400 líneas | 🔴 Migrar core→motor |
| **Gemini Provider** | core/mochila/providers/gemini.py + motor/core/llm/gemini.py | 180 líneas | 🔴 Migrar core→motor |
| **OpenRouter Provider** | core/mochila/providers/openrouter.py + motor/core/llm/openrouter.py | 150 líneas | 🔴 Migrar core→motor |
| **DeepSeek/Groq** | Solo en core/mochila/providers/ | 128 líneas | 🔴 Migrar a motor/ o eliminar |
| **Notifier** | core/notifier.py + knowledge/engine/notify.py | 2 | 🟡 Fusionar |
| **Web scraper** | core/scraper_pool.py + motor/core/web/ | 2 | 🟡 Fusionar |

---

## RECOMENDACIONES POR PRIORIDAD

| Prio | Acción | Archivos afectados | Riesgo | Retorno |
|---|---|---|---|---|
| P0 | **Providers: core→motor** | 14 archivos | Medio | Elimina 6 archivos duplicados |
| P0 | **Generar mapa arquitectónico** (este doc) | 0 | Ninguno | Base para todas las decisiones |
| P1 | **Eliminar código muerto confirmado** | ~30 archivos | Bajo | -8,000 líneas |
| P1 | **Extraer constantes + configuración** | ~30 archivos | Bajo | Portabilidad |
| P2 | **Fusionar EventBus** | core/event_bus.py | Medio | -1 EventBus |
| P2 | **Fusionar agentes** | core/ura_multi_agent.py | Alto | -1 sistema de agentes |
| P3 | **Dividir monolitos** | model_router.py, mochila_server.py | Alto | Mantenibilidad |
| P3 | **Git purge** | Historial | Alto | -100MB .git |
