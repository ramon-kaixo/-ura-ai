# Sistema de Memoria de URA — Arquitectura Real (v4.0)

**Fecha:** 2026-08-06 (revisión F3 v4.0; versión original 2026-08-04)
**Estado:** Verificado — 162 tests de memoria pasan + auditoría read-only 2026-08-06
**Fase:** 3 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)

## CORRECCIÓN IMPORTANTE del plan original

El plan v4.0 asumía que la memoria canónica vivía en `motor/core/memoria/` y que
`core/memoria/` era código muerto. **Ambas suposiciones eran FALSAS** (verificado):

- `motor/core/memoria/` **NO EXISTE**
- `core/memoria/` es **VIVO en producción** (servidor mochila :4098 lo importa)
- La memoria v2 canónica vive en `motor/memory/` + `motor/intelligence/memory/`

## Arquitectura (4 capas + 1)

### 1. `scripts/pro/tuneladora/memory/` — Memoria del Pipeline
- **Responsabilidad:** Persistencia de ejecuciones del pipeline de validación
- **Submódulos:**
  - `episodic.py` — Episodios de cada ejecución ("hoy el pipeline pasó en 12s") — **95.2% cobertura**
  - `semantic.py` — Conceptos y relaciones aprendidas del código (`Concept`, `Relation`) — 100%
  - `long_term.py` — Archivado de resultados clave (`LTMEntry`) — 100%
  - `short_term.py` — Caché con TTL (snapshots de health checks) — 100%
- **Conectado a:** `runner._finish` → `episodic.record` + `ltm.store`; `phase_index` → `semantic.learn_concept`; `cache` → `ShortTermMemory`

### 2. `core/memoria/` — Memoria de Alto Nivel (dominio URA) — 🟢 VIVO PRODUCCIÓN
- **Responsabilidad:** Interfaz que usa el resto del sistema (bridge, consulta, compresor, vigilante)
- **9 módulos:** `analizador.py`, `bridge.py`, `compresor.py`, `consulta.py`, `ficha.py`, `ingesto.py`, `qdrant_store.py`, `sintetizador.py`, `vigilante.py`
- **Consumidores:** `core/mochila/mochila_server.py` (:4098) + 9 tests unitarios
  (`test_memoria_bridge_vigilante`, `_compresor`, `_consulta`, `_imagen_extractor`,
  `_qdrant_store`, `_rastreadores`, `_sintesis_analisis`)
- **Entrada:** Texto, eventos, resultados de búsqueda | **Salida:** Contexto relevante para el agente
- **Nota:** Contiene `ficha.py` (dataclass `Idea` — captura de ideas, NO duplicado de episódica; ver ADR-220)

### 3. `motor/intelligence/memory/` — Stores Técnicos del Motor (F12 Context Memory)
- **Responsabilidad:** Implementación concreta de cada tipo de memoria del agente
- **12 submódulos:** `base.py`, `compression.py`, `episodic.py` (`Episode`/`EpisodeStore`),
  `extractor_llm.py`, `extractor.py`, `forgetting.py`, `hybrid.py`, `orchestrator.py`,
  `record.py`, `retrieval.py`, `semantic.py` (`SemanticFact`/`SemanticMemoryStore`) + `__init__`
- **Dependencias:** SQLite, Qdrant

### 4. `knowledge/engine/` — Motor de Conocimiento
- **Responsabilidad:** Indexación, búsqueda RAG, embeddings, FTS5
- **Entrada:** Documentos, web, conversaciones

### 5. `motor/memory/` — Historical Memory (F26, canónico v2)
- **Responsabilidad:** Memoria histórica con timeline, journal (WAL) y snapshot
- **7 submódulos:** `crypto.py`, `journal.py`, `memory.py`, `models.py`, `snapshot.py`, `timeline.py` + `__init__`
- **Estado:** ✅ Canónico — Fase 26 cerrada

## Componentes sueltos en raíz (verificados 2026-08-06)

| Módulo | Estado | Evidencia |
|---|---|---|
| `memoria_fallos.py` (raíz) | ✅ **VIVO** (conservado) | Test `tests/unit/test_memoria_fallos.py` + `scripts/restaurar.sh` — tests pasan |
| `memoria_movimiento.py` (raíz) | ✅ **VIVO** (conservado) | Test `tests/unit/test_memoria_movimiento.py` + `scripts/restaurar.sh` — tests pasan |
| `scripts/pro/memoria.py` | ❌ **NO EXISTE** | Plan lo mencionaba; verificado ausente |
| `scripts/pro/conciencia.py` | 🟡 **VIVO indirecto** | `pipeline_supremo.py` lo ejecuta vía subprocess (no archivar) |

## Decisión F3

- **NO se archiva nada**: los sueltos tienen tests en suite (pytest los recoge) y los
  paquetes v1/v2/v12 están en producción/canónicos.
- La **unificación real** (v1 → v2) es de apertura de motor → requiere tocar `motor/core`
  → **PENDIENTE v4.0e** (Ramón), documentada en el plan.

## Pendientes F3

- [ ] v4.0e: migración core/memoria (v1) → motor/memory (v2) con puente — **Ramón**.
- [ ] AGENTS.md: corregir tabla de memoria si cita `motor/core/memoria/` (no existe).
