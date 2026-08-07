# Plan de Unificación — Memoria v1 → v2 (core/memoria → motor)

> **Estado:** 📝 Plan (ejecución requiere decisión Ramón + tocar motor/core)
> **Fecha:** 2026-08-07
> **Fase:** Post-F7 (siguiente pasos)
> **Reglas aplicables:** ADR-007 (motor/core), ADR-026-01 (arquitectura memoria v2), `docs/ARQUITECTURA_v4.0_PLAN.md` F3
> **Precedente:** el plan v4.0 marca "unificación real (v1→v2) = pendiente para Ramón (requiere tocar motor/core)"

---

## 1. Situación real (3 vías de memoria coexistente)

| Vía | Ubicación | Rol | Consumidores de producción | Estado |
|---|---|---|---|---|
| **v1 (Mochila)** | `core/memoria/` — `analizador`, `bridge`, `compresor`, `consulta`, `ficha`, `ingesto`, `qdrant_store`, `sintetizador`, `vigilante` | Ingesta de docs → Qdrant (ideas), búsqueda con fallback web | `core/mochila/mochila_server.py` (:4098), `core/mochila/status_endpoint.py`, `core/mochila/routes/memoria.py` | 🟢 **VIVO** |
| **v2 (Histórica)** | `motor/memory/` — `Journal`, `Memory`, `MemoryTimeline`, `Snapshot`, `crypto` | Memoria temporal inmutable (F26): timeline + journal WAL + snapshots cifrados | Interna de motor | 🟢 estable |
| **v2 (Inteligencia)** | `motor/intelligence/memory/` — `orchestrator`, `episodic`, `semantic`, `hybrid`, `compression`, `forgetting`, `retrieval`, `record` | Memoria contextual (F12/F25): episódica + semántica + olvido | Interna de motor | 🟢 estable |

**Conclusiones de la auditoría (F3 v4.0):** las 3 vías **NO son redundantes** — son
responsabilidades distintas (ingesta-Qdrant vs. timeline inmutable vs. contexto
episódico). La "unificación" NO es fusionar en un solo módulo, sino **consolidar
los puntos de contacto** (colección Qdrant única, esquemas, naming) y **migrar el
v1 a motor** sin romper la Mochila.

---

## 2. Qué NO se debe hacer (anti-targets)

- ❌ Fusionar `motor/memory` con `motor/intelligence/memory` (ARQ v4.0 ya lo separó: responsabilidades distintas — ver `docs/ARQUITECTURA_v4.0_PLAN.md` F3.1).
- ❌ Eliminar `core/memoria` mientras la Mochila lo use (el servidor :4098 depende de él en caliente).
- ❌ Cambiar la API de `motor/memory` (ADR-026 congelado; ADR-007 prohíbe cambios de comportamiento).

---

## 3. Fases propuestas (incremental, degradable)

### F3.1 — Puente de compatibilidad (motor → core.memoria) *(aprobación necesaria)*
**Qué:** crear `motor/core/memoria/` como el futuro hogar (NO mover aún). `core/memoria/`
pasa a ser shim de compat (patrón usado con voice/agents, `DeprecationWarning`).
**Resultado:** la Mochila sigue llamando `core.memoria.*`; internamente resuelve a motor.
**Riesgo:** moderado (los 9 módulos v1 deben importarse desde motor sin cambiar firmas).

### F3.2 — Unificación de almacenamiento (Qdrant)
**Qué:** la v1 escribe ideas en la colección Qdrant actual; la v2/histórica usa su propio
timeline. Consolidar **una sola colección Qdrant** para `buscar_ideas` v1 + retrievers v2
(`motor/intelligence/memory/retrieval.py`), con namespaces por tipo de memoria.
**Riesgo:** alto si se toca el índice sin migración de datos → **requiere respaldo Qdrant
y plan de rollback** (exportar colección antes del cambio).

### F3.3 — Contratos y nombres unificados
**Qué:** un solo `MemoryEntry` (v1 idea vs v2 entry) documentado en un ADR; alias de
nombres; test de igualdad de esquemas entre colecciones.
**Riesgo:** bajo (solo tests de contrato).

### F3.4 — (Fuera de alcance salvo decisión) unificación profunda
Fusionar ingesta v1 con el pipeline KE/F25. NO planificado — requiere nueva propuesta.

---

## 4. Roturas posibles (anticipación)

| # | Rotura | Detección | Mitigación |
|---|--------|-----------|------------|
| R1 | Mochila :4098 deja de responder al migrar imports | `systemctl is-active ura-mochila` + `curl :4098/health` | F3.1 degradable: si motor falla, shim → v1 directo. Rollback = `git revert` del shim |
| R2 | Pérdida de ideas en Qdrant (F3.2) | Conteo de colección antes/después + query sample | Export Qdrant completo antes; `snapshot` en disco; rollback restaurando export |
| R3 | Doble ingesta (v1 + v2 procesan el mismo doc) | Logs de `procesar_archivo` duplicados | Flag idempotencia por hash de fichero; dedup por `_make_id` |
| R4 | Tests de memoria existentes rotos (≈15 archivos `test_memoria_*`) | `pytest tests/unit/test_memoria* -q` | Los tests v1 quedan como guarda de compat (no se tocan en F3.1) |
| R5 | `bridge.py` (web_search→ingesta) rompe el flujo mochila | Smoke: `buscar_y_aprender("test")` | F3.1 mantiene la firma; test unitario de bridge |
| R6 | Motor/core congelado (ADR-007) | Revisión de segunda parte antes de F3.1 | Este plan + ADR dedicado + aprobación Ramón |

---

## 5. Esfuerzo y secuencia

| Fase | Esfuerzo | Precede |
|------|----------|---------|
| F3.1 puente | 3-5h | revisión ADR-007 |
| F3.2 Qdrant | 2-4h + backup | F3.1 |
| F3.3 contratos | 1-2h | F3.2 |
| Verificación | 1h (suite + smoke mochila) | todo |

**Regla de corte:** cada fase termina con `make validate` verde + smoke de Mochila +
0 regresiones vs baseline.

---

## 6. Pendiente para Ramón

- ⬜ Aprobar F3.1 (toca `motor/core` → ADR-007 requiere segunda parte)
- ⬜ Autorizar backup/export de la colección Qdrant (F3.2)
- ⬜ Decidir si `core/memoria` se convierte en shim (F3.1) o se conserva dual (opción B2 conservadora: solo documentar)