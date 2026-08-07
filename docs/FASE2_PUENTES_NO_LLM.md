# FASE 2 — Puentes NO-LLM: mapa de migración core/ → motor/

**Fecha:** 2026-08-07
**Fase:** 2 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Alcance:** módulos de `core/` sin relación con LLM, candidatos a migrar a `motor/`.
**Regla:** cada puente se corta con shim temporal (ver precedente `core/config_manager.py`) y
se elimina en v4.x. Ninguna migración se ejecuta sin decisión de Ramón (ADR-007).

## 1. Puentes CORTADOS

| Módulo core/ | Equivalente motor/ | Commit | Estado |
|---|---|---|---|
| `config_manager` | `motor/core/config_manager.py` | `e7b7d331` (+ prep `5f493cd2`, fix rutas `c35ee77e`) | ✅ **CORTADO** — `core/config_manager.py` es shim `from motor.core.config_manager import *`; 209 líneas movidas, rutas relativas `_URA_ROOT = Path(__file__).resolve().parents[2]`. Consumidores (12) funcionando vía shim |
| `notifier` | `motor/core/notifier.py` | `5c1cb133` | ✅ **CORTADO** — puente notifier ya commiteado |
| `query_cache` | `motor/core/query_cache.py` | (paralelo) | ✅ **CORTADO** — shim transparente (dict TTL) |
| `json_logger` | `motor/core/llm/_logging.py` | (paralelo) | ✅ **CORTADO** — shim + consumidores internos migrados |
| `search_engine` | `motor/core/search_engine.py` | `9d971e8f` | ✅ **CORTADO** — shim transparente; import interno corregido a `motor.core.*` |
| `agents` | `motor/core/agents/` | `b1225ca7` | ✅ **CORTADO** — shim transparente; imports internos → `motor.core.*` |
| `memory_engine` | `motor/core/memory_engine.py` | (paralelo) | ✅ **CORTADO** — shim transparente |

## 2. Puentes PENDIENTES (mapa de migración)

Conteos de importadores verificados el 2026-08-07 (excluye build/, .attic/, .venv/, .tuneladora/snapshots/, docs/).

| Módulo core/ | Consumidores | Equivalente motor/ | API compatible | Acción propuesta |
|---|---|---|---|---|
| `chunking` | 6 | `motor/intelligence/chunking.py` (`Chunk`, `SemanticChunker`) | **Distinta** (`chunk_semantic` retorna `list[str]` vs `list[Chunk]`) | APIs distintas → NO fusionar aún. Documentar divergencia; decisión de unificación en fase futura |
| `memory_engine` | 5 | `motor/memory/` (journal, snapshot, timeline, crypto, models) | Distinta (conceptos: WAL/snapshot vs engine) | Migrar: core/memory_engine es capa de consulta/escritura; motor/memory es persistencia durable. Requiere ADR (toca motor/core) — decisión Ramón |
| `voice` | 4 | **NO EXISTE** | — | Decidir: mover a `motor/platform/` o mantener en core (depende de dirección de voz) |

## 3. Resumen

- ✅ 7 de 10 cortados (`config_manager`, `notifier`, `query_cache`, `json_logger`, `search_engine`, `agents`, `memory_engine`).
- ⏳ 3 pendientes: `chunking` (API distinta, no fusionar), `memory_engine`→motor/memory (ADR, decisión Ramón), `voice` (decisión de dirección).
- Los shims `# noqa: F401,F403` son capa de compatibilidad → política de deprecación v3.x:
  marcar `DeprecationWarning`, eliminar en v4.0.

## 4. Order sugerido de ejecución (cuando Ramón decida)

1. `chunking` (documentar divergencia; unificar más tarde)
2. `memory_engine` → motor/memory (ADR, toca motor/core, decisión Ramón)
3. `voice` (decisión de dirección)

Cada corte: mismo patrón que `e7b7d331` — mover archivo a motor/, shim re-export en core/,
`make validate`, commit por puente.
