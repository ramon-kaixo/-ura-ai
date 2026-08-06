# FASE 2 — Puentes NO-LLM: mapa de migración core/ → motor/

**Fecha:** 2026-08-07
**Fase:** 2 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Alcance:** módulos de `core/` sin relación con LLM, candidatos a migrar a `motor/`.
**Regla:** cada puente se corta con shim temporal (ver precedente `core/config_manager.py`) y
se elimina en v4.x. Ninguna migración se ejecuta sin decisión de Ramón (ADR-007).

## 1. Puente CORTADO (precedente)

| Módulo core/ | Equivalente motor/ | Commit | Estado |
|---|---|---|---|
| `config_manager` | `motor/core/config_manager.py` | `e7b7d331` (+ prep `5f493cd2`) | ✅ **CORTADO** — `core/config_manager.py` es shim `from motor.core.config_manager import *`; 209 líneas movidas, 2 rutas absolutas preparadas. Consumidores (12) siguen funcionando vía shim |

## 2. Puentes PENDIENTES (mapa de migración)

Conteos de importadores verificados el 2026-08-07 (excluye build/, .attic/, .venv/, .tuneladora/snapshots/, docs/).

| Módulo core/ | Consumidores | Equivalente motor/ | API compatible | Acción propuesta |
|---|---|---|---|---|
| `query_cache` | 8 | **NO EXISTE** | — | Mover a `motor/core/query_cache.py` + shim. Es self-contained (dict TTL) — migración trivial |
| `notifier` | 6 | **NO EXISTE** (parcial: `knowledge/engine/notify.py` Slack/Email) | Distinta | Mover a `motor/core/notifier.py` + shim. Evaluar unificar con notify.py (Telegram/Pushover + Slack/Email) |
| `json_logger` | 8 | `motor/core/llm/_logging.py` | **Distinta** (`log_call`, `percentile` vs API json_logger) | Comparar APIs; mover json_logger a `motor/core/` y que `_logging.py` lo use, o mantener ambos documentando diferencia |
| `chunking` | 6 | `motor/intelligence/chunking.py` (`Chunk`, `SemanticChunker`) | **Distinta** (`chunk_semantic` retorna `list[str]` vs `list[Chunk]`) | APIs distintas → NO fusionar aún. Documentar divergencia; decisión de unificación en fase futura |
| `memory_engine` | 5 | `motor/memory/` (journal, snapshot, timeline, crypto, models) | Distinta (conceptos: WAL/snapshot vs engine) | Migrar: core/memory_engine es capa de consulta/escritura; motor/memory es persistencia durable. Requiere ADR (toca motor/core) — decisión Ramón |
| `voice` | 4 | **NO EXISTE** | — | Decidir: mover a `motor/platform/` o mantener en core (depende de dirección de voz) |

## 3. Resumen

- ✅ 1 de 7 cortado (`config_manager`, precedente shim validado).
- ⏳ 6 pendientes: 2 sin equivalente (mover + shim), 1 parcial (evaluar unificación),
  2 con API distinta (documentar, no fusionar), 1 requiere ADR (decisión Ramón).
- Los shims `# noqa: F401,F403` son capa de compatibilidad → política de deprecación v3.x:
  marcar `DeprecationWarning`, eliminar en v4.0.

## 4. Orden sugerido de ejecución (cuando Ramón decida)

1. `query_cache` (trivial, self-contained)
2. `notifier` (mover + evaluar unificación notify.py)
3. `json_logger` (mover a motor/core)
4. `voice` (decisión de dirección)
5. `chunking` (documentar divergencia; unificar más tarde)
6. `memory_engine` → motor/memory (ADR, toca motor/core)

Cada corte: mismo patrón que `e7b7d331` — mover archivo a motor/, shim re-export en core/,
`make validate`, commit por puente.
