# Clasificación de Módulos — Fase 1 (Auditoría) — 2026-07-31

## Metodología

1. **Grafo de imports estático** (AST): 480 módulos .py de core/motor/knowledge + consumidores de tests/, scripts/, mantenimiento/, monitor/, app/.
2. **Verificación manual** de cada candidato huérfano: búsqueda de imports reales, referencias por string (uvicorn/systemd/entry points), ejecución directa (`__main__`), cron/timers, carga dinámica (importlib/plugins).
3. **Clasificación final**: VIVO (importado o ejecutado por servicio real) / HUÉRFANO (sin referencias) / FALSO POSITIVO (referencia externa por string o dinámica).

## Resultados

- **381 módulos VIVOS**
- **123 huérfanos aparentes** → tras verificación: **31 huérfanos reales**, 92 falsos positivos descartados
- 0 dependencias circulares (core→motor→knowledge unidireccional)

## Huérfanos REALES (candidatos a eliminación — Fase 2)

### core/ (16)
| Módulo | Notas |
|--------|-------|
| `core/agents/__main__` | No usado (agents/ interno, constants.py sí es VIVO) |
| `core/bin_paths` | Solo importado por `monitor/snc` (fuera de repo) |
| `core/change_guardian` | Sin referencias |
| `core/inferencia/engine` | Solo tests lo importan (`test_inference_engine`) |
| `core/json_logger` | VIVO via tests (conservar) |
| `core/memoria/detectores` | Sin referencias |
| `core/memoria/ensamblador` | Sin referencias |
| `core/memoria/limpieza` | Sin referencias |
| `core/mochila/app` | `mochila_server` (VIVO via ura-mochila.service) define su propia app — app.py es duplicado |
| `core/mochila/providers/base, deepseek, gemini, groq, ollama, openrouter` | **VIVO**: importados por mochila_server (servicio activo). NO eliminar |
| `core/model_router/__main__` | Módulo de ejecución directa; verificar si se usa en CLI |
| `core/open_claw_reporte` | Sin referencias |
| `core/path_setup` | Sin referencias |
| `core/query_expander` | Sin referencias |
| `core/reranker` | Sin referencias (candidato fuerte — motor/intelligence/reranking/ existe) |
| `core/sandbox_orchestrator` | Referenciado solo en lista de archivos críticos de `agents/agente_sandbox_codigo.py` (agente no usado) |
| `core/scraper_pool` | VIVO via tests (conservar) |
| `core/search_logger` | Sin referencias |
| `core/ura_sandbox_bridge` | Sin referencias |
| `core/voice/anker_mac_pipeline, tts_piper` | Sin referencias en repo (posible uso externo Mac) |
| `core/wrapper_opencode` | Sin referencias |

### knowledge/ (4)
| Módulo | Notas |
|--------|-------|
| `knowledge/engine/api` | VIVO via `cli/api.py` (string "knowledge.engine.api:app") — conservar |
| `knowledge/engine/collector` | Sin referencias |
| `knowledge/engine/rollback` | Sin referencias |
| `knowledge/engine/cli/__main__` | Entry point CLI — VIVO |

### motor/ (11)
| Módulo | Notas |
|--------|-------|
| `motor/assistant/.nervioso/conversation_search` | Directorio oculto — verificar |
| `motor/assistant/.nervioso/tool_confirmation` | Idem |
| `motor/core/qdrant_rest` | Sin imports reales (verificar uso HTTP directo) |
| `motor/diagnostico/_state` | Solo se usa internamente en diagnostico/ — verificar si diagnostico es VIVO |
| `motor/diagnostico/diagnostico` | Sin referencias externas |
| `motor/meta/schema` | Sin referencias |
| `motor/observability/http` | Sin imports reales |
| `motor/platform/metrics` | Sin imports reales |
| `motor/scanner/_state` | Idem diagnostico |
| `motor/scanner/scanner` | Sin referencias externas |
| `motor/agents/` (8 módulos) | VIVO via motor/agents/__init__ re-exports (conservar) |

## Falsos positivos DESMENTIDOS (plan maestro)

| Candidato del plan | Veredicto | Evidencia |
|--------------------|-----------|-----------|
| `agent_hierarchy.py` | Ya no existe (eliminado) | Solo referencias históricas en docs/backups |
| `core/agents/` | **VIVO** — `constants.py` importado por `core/ura_multi_agent.py` | grep imports |
| `core/cleanup.py` | HUÉRFANO (confirmado) | 0 imports en código vivo |
| `core/error_sandbox.py` | HUÉRFANO (confirmado) | 0 imports (solo `__main__` propio) |
| `core/guardian_openclaw.py` | **VIVO** — importado por `core/mochila/guardian_middleware.py` | grep imports |
| `core/auto_reindex.py` | **VIVO** — ejecutado por `ura-auto-reindex.service` (systemd, timer 03/09/15/21h) | systemctl cat |
| `core/mochila/*` | **VIVO** — `ura-mochila.service` activo ejecuta mochila_server:app | systemctl status |
| `core/reranker` | HUÉRFANO (duplicado de motor/intelligence/reranking) | grep |

## Módulos <20% cobertura (objetivo Fase 4)

- 10% `core/model_router/handler.py`
- 11% `core/model_router/dashboard.py`
- 11% `motor/observability/exporter.py`
- 15% `mantenimiento/ura_maintenance.py`
- 16% `motor/core/llm/base.py`
- 17% `monitor/health_check.py`
- 18% `motor/core/web/cleaner/deduplication.py`
- 19% `knowledge/engine/ontology/schema_org.py`
- 19% `motor/assistant/metrics.py`

## Fallos de pytest (52) — clasificación final

| Grupo | Nº | Tipo |
|-------|-----|------|
| `tests/pending/test_audit_conversation.py` | 11 | **Bugs reales de conversation** — otra sesión está corrigiéndolos (max_turns, delete, null content) |
| `tests/integration/test_audit_intent.py` | 5 | **4 flaky (interferencia estado) + 1 real** (test_null_byte_in_text: sanitización null byte vs patrón GREETING) |
| `tests/nightly/` (benchmarks) | 3 | Thresholds de rendimiento en GX10 cargado |
| `tests/unit/test_auth_middleware.py` | 6 | **Flaky** — pasa aislado (766 passed), falla en suite completa |
| `tests/unit/test_message_store.py` | 1 | **Flaky** — idem |
| Resto (integración) | ~26 | Interferencia de estado de la suite completa (proceso satura PIDs del sistema) |

## Hallazgos colaterales

1. **Hang post-suite**: pytest no termina tras el último test (~12 min extra). Investigar.
2. **`scripts/pro/inspectores.py:135`**: error de sintaxis real — bloquea mypy global.
3. **Rootfs montado RO** (volvió tras arreglo 2026-07-19): pre-commit no puede escribir en `/home/ramon/.cache/pre-commit`. Workaround: `PRE_COMMIT_HOME=/home/ramon/URA/.pre-commit-cache`. Requiere `sudo mount -o remount,rw /` (pendiente).
4. **Edición paralela de otra entidad**: 4 archivos modificados externamente (conversation.py, intent.py, test_audit_conversation.py, fact_history.py) — no commiteados por esta sesión.
5. **Vulture**: 543 candidatos "unused" (confianza 60%) — alta tasa de falsos positivos (dataclasses/ABCs/dunder).

## Recomendaciones Fase 2 (limpieza)

Orden de eliminación (verificar una vez más antes de borrar):
1. `core/reranker` + `core/query_expander` + `core/search_logger` (duplicados de motor/intelligence)
2. `core/memoria/{detectores,ensamblador,limpieza}`
3. `core/error_sandbox.py`, `core/cleanup.py` (plan maestro confirmado)
4. `core/open_claw_reporte`, `core/wrapper_opencode`, `core/ura_sandbox_bridge`
5. `core/inferencia/engine` (solo tests lo usan — evaluar si es API pública)
6. `knowledge/engine/{collector,rollback}`
7. `motor/diagnostico/`, `motor/scanner/` (verificar si tienen CLI/scripts asociados antes)
8. `motor/meta/schema`, `motor/observability/http`, `motor/platform/metrics`
9. `core/model_router/__main__` y `.nervioso/` (verificar uso en CLI primero)

**No eliminar**: mochila/*, guardian_openclaw, auto_reindex, knowledge.engine.api, motor/agents/, core/agents/constants.
