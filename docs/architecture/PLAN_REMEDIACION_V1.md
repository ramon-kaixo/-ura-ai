# PLAN DE REMEDIACIÓN v1.0

**Basado en:** Auditoría Forense v1.0.0 (80 hallazgos, 4.5/10)  
**Esfuerzo estimado:** ~6-8 semanas  
**Orden:** Fases 0→1→2→3 (dependencias respetadas)

---

## FASE 0 — EMERGENCIA (P0, 10 hallazgos)

**Objetivo:** Eliminar riesgos inmediatos de seguridad y estabilidad.  
**Esfuerzo:** ~5 días  
**No requiere desarrollo nuevo — solo corrección.**

### 0.1 Rotar secretos commiteados
| Hallazgo | Archivo | Acción |
|----------|---------|--------|
| HCLOUD_TOKEN | `hetzner.env:1` | Rotar en Hetzner, eliminar archivo del repo, añadir a .gitignore |
| OPENROUTER_API_KEY | `backups/env/.env.2026-06-18:4` | Rotar en OpenRouter, eliminar backup del repo |
| URA_API_KEY | `backups/env/.env.2026-06-18:1` | Rotar, eliminar backup |
| URA_TOKEN | `scripts/pro/gx10-api.service:10` | Rotar, mover a EnvironmentFile= |

### 0.2 Arreglar fugas de memoria (producción 24/7)
| Archivo | Línea | Fix |
|---------|-------|-----|
| `motor/platform/tracing.py` | 567-572 | Añadir `max_events=10000` con `pop(0)` en `emit()` |
| `motor/platform/tracing.py` | 808-813 | Truncar `durations_ns` tras computar percentiles |
| `motor/core/llm/observability.py` | 22,42 | Añadir `max_records=1000` con evicción FIFO en `_calls` |
| `motor/core/llm/observability.py` | 24,51 | Misma estrategia para `_tokens` |

### 0.3 Desbloquear 8 tests rotos
| Archivo | Fix |
|---------|-----|
| `knowledge/engine/_compat.py` | Añadir `from enum import StrEnum` y reexportar |

### 0.4 Eliminar code injection
| Archivo | Línea | Fix |
|---------|-------|-----|
| `agent_hierarchy.py` | 514-521 | Reemplazar `python3 -c` con ejecución en contenedor sandbox o eliminar capacidad |
| `knowledge/engine/rules.py` | 264-277 | Reemplazar `eval()` con parser AST restringido o lookup table |
| `core/voice/anker_mac_pipeline.py` | 70-75 | Sanitizar `message` escapando `"` y caracteres de control |

### 0.5 Arreglar race condition
| Archivo | Línea | Fix |
|---------|-------|-----|
| `knowledge/engine/reader.py` | 30-66 | Añadir `threading.Lock()` alrededor de `_READER_POOL` |

---

## FASE 1 — ARQUITECTURA CRÍTICA (P1, 27 hallazgos)

**Objetivo:** Reducir carga de mantenimiento y riesgos operacionales.  
**Esfuerzo:** ~3 semanas  
**Depende de:** Fase 0 completa.

### 1.1 Consolidar CircuitBreaker (4→1)
| Eliminar | Mantener |
|----------|----------|
| `core/mochila/circuit_breaker.py` | `motor/platform/resilience.py` |
| `motor/core/llm/circuit_breaker.py` | (o crear nuevo unificado) |
| `motor/diagnostico/circuit_breaker.py` | |

**Acción:** Elegir la implementación más completa (`motor/platform/resilience.py` tiene ADR), migrar consumidores, eliminar las otras 3.

### 1.2 Consolidar Logging (4→1)
| Eliminar | Mantener |
|----------|----------|
| `core/json_logger.py` | `motor/observability/logging.py` |
| `motor/platform/logging.py` | |
| `knowledge/engine/logging_config.py` | |

**Acción:** Unificar bajo `motor/observability/logging.py` (único `setup_logging()`), migrar consumidores.

### 1.3 Eliminar 107 archivos sin consumidores
**Criterio:** Solo archivos con 0 importaciones externas y sin `main()` como entry point.

| Grupo | Archivos | Acción |
|-------|----------|--------|
| Scripts huérfanos | `backup_assistant.py`, `chaos_f29_b5.py` | Eliminar |
| Clases no instanciadas | ~50 clases (ver auditoría sección 2.1) | Eliminar las que no tienen consumidores externos |
| `.nervioso/descarte/` importados | 5 archivos (37 refs a tools.py) | Migrar imports a motor/ o knowledge/, eliminar descarte |
| Config muerto | `config/settings.json`, `deploy/lildax_config.json` | Eliminar |
| `__init__.py` vacíos | 22 archivos | Eliminar los que no agrupan nada |

### 1.4 Consolidar providers (6 archivos duplicados)
| Acción | Detalle |
|--------|---------|
| Migrar `core/mochila/providers/ollama.py` → `motor/core/llm/ollama.py` | Unificar interfaz, mantener compatibilidad |
| Migrar `core/mochila/providers/gemini.py` → `motor/core/llm/gemini.py` | Igual |
| Migrar `core/mochila/providers/openrouter.py` → `motor/core/llm/openrouter.py` | Igual |
| Eliminar `core/mochila/providers/deepseek.py` y `groq.py` | Son ~95% idénticos: crear base `_OpenAICompatibleProvider` |

### 1.5 Dividir archivos monolíticos
| Archivo | Líneas | División propuesta |
|---------|--------|-------------------|
| `core/model_router.py` | 1274 | `model_router/router.py` + `model_router/vram.py` + `model_router/dashboard.py` + `model_router/metrics.py` |
| `core/mochila/mochila_server.py` | 730 | `mochila/handlers/` + `mochila/middleware/` + `mochila/models.py` |
| `core/ura_multi_agent.py` | 636 | `agents/debate/` o separar por tipo de agente |

### 1.6 Docker-compose: eliminar passwords default
| Archivo | Línea | Acción |
|---------|-------|--------|
| `deploy/docker/docker-compose.yml:23` | `WEBUI_SECRET_KEY` default | Exigir variable de entorno, no default |
| `deploy/docker/docker-compose.yml:41` | `N8N_KEY` default | Igual |
| `deploy/docker/docker-compose.yml:63` | `FRIGATE_RTSP_PASSWORD` default | Igual |
| `deploy/docker/docker-compose.yml:113` | `GRAFANA_PASSWORD` default | Igual |

### 1.7 CI/CD: expandir cobertura de tests
| Archivo | Línea | Acción |
|---------|-------|--------|
| `.github/workflows/ci.yml:48` | Solo 12 test files | Añadir `tests/test_unit.py` y otros suites que actualmente se saltan |
| `.github/workflows/ci.yml:60` | Bandit solo motor/ | Extender a `core/` y `knowledge/` |
| `.github/workflows/ci.yml:21` | `pip install ruff` | Poner versión: `ruff==0.15.18` |

### 1.8 Arreglar async bloqueante
| Archivo | Línea | Fix |
|---------|-------|-----|
| `motor/assistant/executor.py` | 312-334 | Envolver handlers síncronos con `run_in_executor()` |
| `motor/events/bus.py` | 53 | Reemplazar `threading.Thread` con `ThreadPoolExecutor(max_workers=10)` |

---

## FASE 2 — CALIDAD (P2, 26 hallazgos)

**Objetivo:** Reducir deuda técnica y mejorar mantenibilidad.  
**Esfuerzo:** ~2 semanas  
**Depende de:** Fase 1.1-1.4 (consolidaciones) para evitar trabajar sobre código que será eliminado.

### 2.1 Reemplazar 36 bare `except: pass`
| Archivos | Acción |
|----------|--------|
| `motor/core/llm/__init__.py` (6) | Añadir `log.warning()` en cada except |
| `motor/cli/cmd_ura.py` (5) | Añadir logging con detalles del error |
| `core/voice/tts_piper.py` (2) | Añadir logging |
| Resto (23 en 15 archivos) | Revisar cada uno, añadir logging donde sea relevante |

### 2.2 Externalizar 30+ números mágicos
| Grupo | Constante propuesta | Archivos afectados |
|--------|--------------------|--------------------|
| Puerto Ollama (11434) | `DEFAULT_OLLAMA_PORT` en config.py | 22+ archivos |
| Puerto Qdrant (6333) | `DEFAULT_QDRANT_PORT` | 3 archivos |
| max_tokens (4096) | `DEFAULT_MAX_TOKENS` | 6 providers |
| Timeouts (30, 60, 120) | Constantes con nombre | 10+ archivos |

### 2.3 Reemplazar IPs/paths hardcodeados
| Patrón | Solución | Archivos |
|--------|----------|----------|
| `10.164.1.99` (6 archivos) | Usar `config.asus_host` o env var | `core/secretario_cache.py`, `core/ura_multi_agent.py`, etc. |
| `/home/ramon/` (12 archivos) | Usar `Path.home()` o `config.data_dir` | `core/mochila/tools.py`, `core/guardian_disco.py`, etc. |
| `127.0.0.1:11434` (22+ archivos) | Usar `UraConfig.ollama_host` + `ollama_port` | `core/memoria/`, `core/mochila/`, etc. |

### 2.4 Limpiar dependencias
| Acción | Paquetes |
|--------|----------|
| Eliminar de pyproject.toml | `click`, `rich`, `coloredlogs`, `orjson`, `typer` (no importados) |
| Añadir a pyproject.toml | `pyzmq`, `psutil`, `sounddevice`, `soundfile`, `whisper`, `pyautogui`, `json_repair` |
| Eliminar archivos muertos | `requirements/legacy.txt`, `requirements.txt` (raíz) |

### 2.5 Git: purgar historial
| Acción | Herramienta |
|--------|-------------|
| Eliminar `.venv/bin/ruff` (24.5MB) del historial | `git filter-repo --path .venv/bin/ruff` |
| Eliminar `models/reranker/*.onnx` (23.2MB) | `git filter-repo --path models/reranker/` |
| Eliminar `ura_paquete_nivel4.zip` (18.9MB) | `git filter-repo --path ura_paquete_nivel4.zip` |
| Eliminar `.git.corrompido.backup.20260530/` (35.5MB) | `git filter-repo --path .git.corrompido.backup.20260530/` |
| Añadir `.gitattributes` con LFS para binarios | Crear archivo |
| Añadir patrones faltantes a `.gitignore` | `*.pdb`, `*.dmp`, `*.core`, `*.hprof` |

### 2.6 Arreglar race condition SQLite en async
| Archivo | Fix |
|---------|-----|
| `motor/assistant/preferences.py:30` | Usar `asyncio.Lock()` + `run_in_executor()` para SQLite |
| `motor/assistant/proactive_memory.py:54` | Igual |
| `motor/intelligence/memory/episodic.py:113` | Igual |

---

## FASE 3 — POLISH (P3, 17 hallazgos)

**Objetivo:** Documentación, configuración, y detalles finales.  
**Esfuerzo:** ~1 semana  
**Depende de:** Fases 0-2 completas (para que documentación refleje realidad).

### 3.1 Documentación
| Hallazgo | Acción |
|----------|--------|
| `CLAUDE.md` no existe | Crear symlink a AGENTS.md |
| `docs/CHANGELOG.md` no existe | Crear changelog |
| AGENTS.md: script count 146→186 | Actualizar |
| AGENTS.md: F28 status inconsistente | Unificar "Pending stabilization" vs "Closed" |
| README: `pip install ura` | Cambiar a instrucciones reales de instalación |
| README: estructura proyecto sin `core/` | Añadir core/ al diagrama |
| F29_CLOSEOUT.md (64 líneas) | Expandir con detalles |

### 3.2 Limpieza final
| Hallazgo | Acción |
|----------|--------|
| Branch `master` stale | Eliminar tras verificar |
| Servicios systemd "fallido" en AGENTS.md | Revisar si siguen caídos, documentar o eliminar del listado |
| `deploy/ia-flujo.service` apunta a archivo inexistente | Eliminar servicio o crear archivo |

---

## DEPENDENCIAS ENTRE FASES

```
Fase 0 (Emergencia)
  ├─ 0.1 Rotar secrets ──────────────── Independiente
  ├─ 0.2 Memory leaks ───────────────── Independiente  
  ├─ 0.3 _compat.py ─────────────────── Independiente (desbloquea tests)
  ├─ 0.4 Code injection ─────────────── Independiente
  └─ 0.5 Race condition reader.py ───── Independiente
        │
Fase 1 (Arquitectura)
  ├─ 1.1 CircuitBreaker ─────────────── Independiente
  ├─ 1.2 Logging ────────────────────── Independiente
  ├─ 1.3 Eliminar código muerto ─────── Después de verificar consumeros
  ├─ 1.4 Providers ──────────────────── Independiente (pero toca archivos que 1.3 podría eliminar)
  ├─ 1.5 Dividir monolíticos ────────── Independiente
  ├─ 1.6 Docker passwords ───────────── Independiente
  ├─ 1.7 CI/CD ──────────────────────── Después de 0.3 (tests rotos)
  └─ 1.8 Async bloqueante ───────────── Independiente
        │
Fase 2 (Calidad)
  ├─ 2.1 Bare excepts ───────────────── Después de 1.2 (logging unificado)
  ├─ 2.2 Números mágicos ────────────── Independiente
  ├─ 2.3 IPs/paths hardcodeados ─────── Independiente
  ├─ 2.4 Dependencias ───────────────── Independiente
  ├─ 2.5 Git purge ──────────────────── Después de 1.3 (eliminar archivos primero)
  └─ 2.6 SQLite en async ────────────── Independiente
        │
Fase 3 (Polish)
  └─ 3.1 Documentación ──────────────── Después de todo lo demás
  └─ 3.2 Limpieza final ─────────────── Después de todo lo demás
```

---

## RESUMEN DE ESFUERZO

| Fase | Días | Personas | Dependencias |
|------|------|----------|-------------|
| 0 — Emergencia | 5 | 1 | Ninguna |
| 1 — Arquitectura | 15 | 1 | Fase 0 |
| 2 — Calidad | 10 | 1 | Fase 1.1-1.4 |
| 3 — Polish | 5 | 1 | Fases 0-2 |
| **Total** | **~35 días** | **1** | |

**Atajos posibles:** Items 0.1, 0.2, 1.6, 1.7, 2.4, 2.5, 3.1 pueden ejecutarse en paralelo si hay 2 personas.

**Ruta crítica:** 0.1 (rotar secrets) → 0.3 (_compat.py → tests) → 1.7 (CI/CD). Sin tests, no se puede verificar nada más.
