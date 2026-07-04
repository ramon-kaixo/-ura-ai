# Fase 8: Hardening, Cobertura y Documentación

> **Versión:** 0.1.0 (borrador inicial)  
> **Fecha:** 2026-07-04  
> **Estado:** 📋 Pendiente de definición  
> **Fase anterior:** Fase 7 — Optimizaciones de Producción (cerrada v3.0)  

---

## Propósito

Cerrar el backlog de Fase 7 y estabilizar el Knowledge Engine con:
- Cobertura de tests para garantizar que benchmarks y APIs públicas se mantienen
- Defensas adicionales contra condiciones de borde
- Documentación faltante de contratos y modos degradados

**Principio:** Sin nuevas funcionalidades. Solo calidad, robustez y documentación.

---

## Backlog de Fase 8

El backlog está formado exclusivamente por hallazgos de la auditoría adversarial
de Fase 7 (PHASE7_CLOSEOUT.md v3.0), con identificadores estables.

### Stream 1: Cobertura de Tests

| ID | Hallazgo | Prioridad | Dependencias |
|----|----------|-----------|--------------|
| B02 | Sin test que verifique solo APIs públicas en benchmark | Alta | — |
| B03 | Sin test de integridad targets benchmark vs SLAs | Alta | — |
| B04 | Sin verificación targets benchmark vs SLAs documentados | Media | B03 |
| B08 | Sin benchmark GX10 real en CI | Media | infra CI |

**Criterios de aceptación:**
- CA-B02: `tests/benchmark_fase7.py` incluye test que verifica que ninguna
  medición usa `conn.execute()` u otros accesos SQL directos
- CA-B03: `tests/benchmark_fase7.py` incluye test que verifica que cada
  target de benchmark tiene un SLA documentado en `docs/SLA.md`
- CA-B04: cada medición en benchmark tiene un target numérico validado
  contra el SLA documentado
- CA-B08: existe script o workflow para ejecutar benchmark en GX10 y
  comparar resultados contra baseline

### Stream 2: Defensas Adicionales

| ID | Hallazgo | Prioridad | Dependencias |
|----|----------|-----------|--------------|
| M04 | `next_offset` sin guard en `_get_vector_ids()` | Alta | — |
| M05 | scroll API sin timeout en `list_ids()` | Media | — |
| M06 | `proc.wait()` sin timeout en worker loop | Media | — |

**Criterios de aceptación:**
- CA-M04: `_get_vector_ids()` en `vector_retriever.py` detecta y corta
  loop si Qdrant devuelve mismo `next_offset` repetido
- CA-M05: `list_ids()` en `vector_qdrant.py` tiene timeout configurable
  en llamada scroll API
- CA-M06: `proc.wait()` en `extraction_service.py` tiene timeout y
  maneja `TimeoutExpired`

### Stream 3: Documentación

| ID | Hallazgo | Prioridad | Dependencias |
|----|----------|-----------|--------------|
| M02 | `_get_vector_ids()` no documentado en contratos | Baja | — |
| M07 | Modo degradado sin FTS5 no documentado en FASE7_DESIGN.md | Baja | — |
| M08 | `list_ids()` omitido en VectorStore Protocol raíz de CONTRACTS_FROZEN.md | Baja | — |
| M09 | Fase 7 no listada en README.md del proyecto | Baja | — |

**Criterios de aceptación:**
- CA-M02: `_get_vector_ids()` y su relación con `list_ids()` está
  documentado en `CONTRACTS_FROZEN.md`
- CA-M07: `FASE7_DESIGN.md` incluye sección "Modo Degradado" que lista
  todos los componentes y su comportamiento sin FTS5
- CA-M08: `VectorStore.list_ids()` está en el Protocol raíz de
  `CONTRACTS_FROZEN.md`
- CA-M09: `README.md` del proyecto lista Fase 7 en su roadmap

---

## Plan de Pruebas

### Tests existentes que deben seguir pasando
- `tests/test_fase7.py` — 36 unit + 3 integration + 8 H1
- `tests/benchmark_fase7.py` — 6 benchmarks (deben mantener 6/6 targets)
- `tests/e2e_fase7.py` — 39 validaciones E2E
- Suite completa: 461 passed, 10 pre-existing fail, 1 skip

### Tests nuevos requeridos
- Benchmark integrity test (B02-B04)
- M04 guard test: mock Qdrant scroll que repite offset
- M05 timeout test: mock scroll que cuelga
- M06 timeout test: proc que no termina

### Tests de regresión
- 0 regresiones en tests existentes
- Benchmark targets: mismos valores que baseline v0.6.0

---

## Criterios de Aceptación Globales

| # | Criterio | Stream |
|---|----------|--------|
| CA1 | 100% del backlog de Fase 7 cerrado (9 items) | Todos |
| CA2 | 0 regresiones en tests existentes | Tests |
| CA3 | 6/6 targets de benchmark mantenidos | Tests |
| CA4 | Sin bugs funcionales de severidad alta o crítica nuevos | Todos |
| CA5 | PHASE7_CLOSEOUT.md actualizado con cierre de backlog items | Documentación |

---

## Riesgos

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| M04 guard falso positivo en Qdrant sano | Loop break innecesario | Baja | Log + alarma, no break silencioso |
| Benchmark GX10 requiere GPU para mediciones reales | Benchmark no representativo en Mac | Media | CI opcional, benchmark manual documentado |

---

## Línea Base

| Propiedad | Valor |
|-----------|-------|
| Baseline | v0.6.0 |
| Schema | v14 |
| Tests | 461 relevantes — 0 nuevos fallos |
| Commit inicial | `9112322` (Fase 7 cerrada) |
| Tag inicial | `v0.6.0-fase7` |

---

*Documento de diseño vivo — Fase 8 — Hardening, Cobertura y Documentación — 2026-07-04*
