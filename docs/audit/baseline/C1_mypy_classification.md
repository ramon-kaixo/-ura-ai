# C1 — Clasificación de errores mypy (429) — 2026-08-17

**TASK-20260817-025 · Ejecutor: TERM · Modo READ-ONLY (solo informe y coordinación)**

## Origen de los datos

`mypy --no-incremental core motor shared` → **429 errores en 99 archivos** (460 verificados).

## Tabla resumen

| Categoría | Nº errores | Descripción | Archivos más afectados |
|-----------|-----------|-------------|------------------------|
| **P0** | 58 | Fallo probable en producción (atributo en `None`/`object`, atributo de módulo inexistente, `__aexit__` ausente) | `motor/core/evaluation/evaluator.py` (9), `motor/assistant/conversation.py` (9), `motor/core/qdrant_client.py` (7), `motor/memory/journal.py` (6), `knowledge/engine/vector_retriever.py` (6) |
| **P1** | 108 | Degrada calidad / fallo en condiciones específicas (arg-type, return-value, assignment, abstract) | `knowledge/engine/compiler.py` (14), `motor/core/fusion/engine.py` (7), `motor/core/fusion/stages/entity_resolver.py` (6), `knowledge/engine/archiver.py` (5) |
| **P2** | 242 | Anotación en tests (no afecta ejecución en producción) | `motor/tests/test_qdrant_client_cobertura.py` (69), `test_router_cobertura.py` (37), `test_intelligence_memory_cobertura.py` (29) |
| **P3** | 21 | Deuda menor (var-annotated, no-redef, valid-type, misc) | dispersos (≤1 por archivo) |
| **TOTAL** | **429** | | |

## P0 — Ejemplos representativos

| Archivo:línea | Error | Riesgo real |
|---------------|-------|-------------|
| `core/logs/guardian_logger.py:44,49` · `core/infra/heartbeat.py:71` | `Module "motor.core.qdrant_client" has no attribute "instancia"` | **ImportError real**: `instancia` es `@classmethod` de `QdrantClient`, no atributo del módulo → `from motor.core.qdrant_client import instancia` falla si se ejecuta esa rama |
| `core/mochila/app.py:23-28` | `"VRAMAwareScheduler | None" has no attribute "start_loop"/"stop_loop"` + `"_MotorChatAdapter" has no attribute "__aexit__"` | **Crash en arranque** del lifespan de la API Mochila si `scheduler` es None |
| `motor/memory/journal.py:57-61,93,107` | `"object" has no attribute "write"/"flush"/"fileno"/"close"` | WAL del journal: si `_file` no es un IO real, falla de durabilidad |
| `knowledge/engine/vector_retriever.py:70-240` | `Item "None" of "Embedder | None" has no attribute "embed_query"` | Guard `_vector_available()` no tipado → posible AttributeError en retrieval |
| `motor/core/qdrant_client.py:56-57,102-174` | `"None" has no attribute "get_collections"/"get_collection"/"recreate_collection"` | `_cliente` tipado como None tras asignación → Qdrant inaccesible en tiempo de ejecución si el tipado refleja un flujo real |

## P1 — Ejemplos representativos

| Archivo:línea | Error | Impacto |
|---------------|-------|---------|
| `knowledge/engine/compiler.py:129,165,237-238,357` | arg-type/return-value con tipos incompatibles (`Snapshot` vs `CompileStage`, `tuple[CompileError,...]`) | Compilador KE: posibles errores de contrato en escenarios complejos |
| `motor/core/fusion/engine.py:110` | `**dict[str, object]` pasado a `FusionPipeline` | Construcción de pipeline fusion con tipos opacos |
| `motor/intelligence/agents/consensus.py:279,298` | `vote_counts` `dict[str, float]` vs `dict[str, int]` | Consenso: votos ponderados pueden perder precisión |
| `motor/pipeline/executor.py:115,122` | `error: str | None` vs `str` | Resultado de pipeline con error ausente |
| `core/watchdog_funciones.py:131` | `list.__setitem__` con `Exception` (tipada como lista de otro tipo) | Watchdog: excepción no tipada correctamente |

## P2 — Tests (ejemplos; no afectan producción)

| Archivo | Error repetido | N |
|---------|----------------|---|
| `test_qdrant_client_cobertura.py` | `Argument 1 to "QdrantClient" ... "SimpleNamespace"; expected "UraConfig"` | 49 |
| `test_qdrant_client_cobertura.py` | `Incompatible types in assignment ("FakeAsyncClient2" vs "AsyncClient | None")` | 14 |
| `test_router_cobertura.py` | `Argument "registry" to "LLMRouter" ... "FakeRegistry"` | 12 |
| `test_llm_core_cobertura.py` | `"CircuitBreaker" has no attribute "_is_transient"` | 11 |
| `test_intelligence_memory_cobertura.py` | `Argument 2 to "should_forget" ... "None"; expected "ForgettingContext"` | 11 |

## P3 — Ejemplos

- 13× `var-annotated` (anotación redundante/ambigua), 3× `no-redef`, 3× `valid-type`, 5× `misc` — deuda tipográfica sin impacto.

## Top 10 patrones más repetidos (global)

| N | Patrón |
|---|--------|
| 49 | `Argument 1 to "QdrantClient" ... "SimpleNamespace"; expected "UraConfig"` (tests) |
| 14 | `Incompatible types in assignment ("FakeAsyncClient2" vs "AsyncClient | None")` (tests) |
| 12 | `Argument "registry" to "LLMRouter" ... "FakeRegistry"` (tests) |
| 11 | `"CircuitBreaker" has no attribute "_is_transient"` (tests) |
| 11 | `Argument 2 to "should_forget" ... "None"; expected "ForgettingContext"` (tests) |
| 9 | `"object" has no attribute "mode"/"reason"/"code"` (`motor/assistant/conversation.py`) |
| 8 | `"object" has no attribute "query_text"/"relevant_docs"` (`motor/core/evaluation/evaluator.py`) |
| 7 | `Item "None" of "..." has no attribute "get"` (varios) |
| 6 | `Cannot determine type of "_cache_policy"` (varios) |
| 6 | `"BaseLLMProvider" has no attribute "_provider_name"` (tests router) |

## Prioridad de arreglo propuesta (NO ejecutada — requiere TASK + autorización)

1. **P0 batch 1 (ImportErrors)**: `guardian_logger.py:44,49` + `heartbeat.py:71` — cambiar `from ... import instancia` por `QdrantClient.instancia(...)`. ~15 min.
2. **P0 batch 2 (lifespan Mochila)**: `core/mochila/app.py:23-28` — guard de None o tipado correcto de `state.scheduler`. ~20 min.
3. **P0 batch 3 (evaluator/conversation/vector_retriever)**: tipado de contenedores `object` → genéricos. ~2-3 h.
4. **P1 (compiler/fusion/consensus)**: contrato de tipos en KE. ~3-4 h.
5. **P2 (tests)**: masivo pero inocuo — corregir en lote con `SimpleNamespace` → `UraConfig` real o `cast`. ~2 h.
6. **P3**: último, barrido cosmético. ~1 h.

## Limitaciones

- Clasificación heurística por código de error + inspección manual de muestras (no se leyó línea a línea los 429).
- Algunos P0 pueden ser falsos positivos de tipado (p. ej. `_cliente` sí se asigna antes de uso); requiere verificación por ítem antes de corregir.
