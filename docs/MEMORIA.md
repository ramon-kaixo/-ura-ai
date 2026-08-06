# MEMORIA — Arquitectura Real de Memoria (Fase 3 v4.0)

**Fecha:** 2026-08-06
**Fase:** 3 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Estado:** Documento de arquitectura VERIFICADA — 3 vías coexisten

## Veredicto F3

El plan original asumía que la memoria canónica vivía en `motor/core/memoria/` y que
`core/memoria/` era código muerto. **Ambas suposiciones eran FALSAS** (auditoría read-only
2026-08-06): `motor/core/memoria/` **NO EXISTE**, y `core/memoria/` es **VIVO en
producción** (el servidor mochila :4098 lo importa).

## Las 3 vías de memoria (coexistiendo)

| Vía | Ubicación | Estado | Consumidores |
|---|---|---|---|
| **v1 (Mochila, español)** | `core/memoria/` (9 módulos: analizador, bridge, compresor, consulta, ficha, ingesto, qdrant_store, sintetizador, vigilante) | 🟢 **VIVO EN PRODUCCIÓN** — importado por `mochila_server.py` (:4098) | `core/mochila/*` + 9 tests: `test_memoria_bridge_vigilante`, `_compresor`, `_consulta`, `_imagen_extractor`, `_qdrant_store`, `_rastreadores`, `_sintesis_analisis` |
| **v2 (Motor, inglés)** | `motor/memory/` (7 módulos: crypto, journal, memory, models, snapshot, timeline + `__init__`) | 🟢 **CANÓNICO v2** — Fase 26 (Historical Memory) | tests motor (`motor/tests/test_memory*`) |
| **v12 (Motor Inteligencia)** | `motor/intelligence/memory/` (12 módulos: base, compression, episodic, extractor_llm, extractor, forgetting, hybrid, orchestrator, record, retrieval, semantic + `__init__`) | 🟢 **CANÓNICO v2** — Fase 12 (Context Memory) | tests motor + F25 registry |

## Componentes sueltos de memoria en raíz (verificados)

| Módulo | Estado | Evidencia |
|---|---|---|
| `memoria_fallos.py` (raíz) | ✅ **VIVO** (conservado) | Test propio `tests/unit/test_memoria_fallos.py` + referencia en `scripts/restaurar.sh` — 9 tests pasan |
| `memoria_movimiento.py` (raíz) | ✅ **VIVO** (conservado) | Test propio `tests/unit/test_memoria_movimiento.py` + `scripts/restaurar.sh` — tests pasan |
| `scripts/pro/memoria.py` | ❌ **NO EXISTE** | Plan lo mencionaba; verificado ausente |
| `scripts/pro/conciencia.py` | 🟡 **VIVO indirecto** | `pipeline_supremo.py` lo ejecuta vía subprocess (no archivar) |

## Decisión F3

- **NO se archiva nada**: los sueltos tienen tests en suite (`pytest` los recoge) y los
  paquetes de memoria v1/v2/v12 están en producción/canónicos.
- La **unificación real** (v1 → v2) es de apertura de motor → requiere tocar `motor/core`
  → **PENDIENTE v4.0e** (Ramón), documentada en el plan.

## Pendientes F3

- [ ] v4.0e: migración core/memoria (v1) → motor/memory (v2) con puente — **Ramón**.
- [ ] AGENTS.md: corregir tabla de memoria si cita `motor/core/memoria/` (no existe).