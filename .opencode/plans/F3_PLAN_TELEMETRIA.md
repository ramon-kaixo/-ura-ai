# F3 Plan — Observability for Assistant (SUPERSEDED)

**Estado:**
- Original: perdido (untracked, borrado por git clean -fd)
- Fuente de reconstrucción: historial de conversación (plan original presentado al usuario, rechazado y reemplazado por plan ajustado)
- Nivel de confianza:
  - Estructura del plan original: Alta (presentado en esta conversación antes del pre-audit)
  - Decisiones originales: Alta (documentadas en la conversación)
  - Contenido completo: Estimada (el original tenía más detalle de implementación que no se conservó textualmente)
- ⚠️ **Este documento está SUPERSEDED.** Ver el plan ajustado en el historial de conversación (mensaje con "Deliverable 2: F3 — PLAN AJUSTADO").

---

## Contexto

Este era el plan original para F3, presentado antes del pre-audit que reveló:
1. `motor/observability/metrics.py` no soporta labels dinámicas
2. `motor/platform/tracing.py` existe pero no se consideró en el plan original
3. `motor/platform/` tiene duplicación parcial con `motor/observability/`
4. `motor/assistant/` tiene 31 sub-sistemas con 0% observabilidad

## Plan Original (Resumen)

### Objetivo
Instrumentar `motor/assistant/` con observabilidad usando infra existente de `motor/observability/`.

### Componentes propuestos
1. Reemplazar `/health` hardcoded por HealthRegistry
2. Añadir correlation_id a requests y propagarlo
3. Añadir métricas (request count, latency, errors)
4. Añadir logging estructurado (JSONFormatter)

### Lo que NO consideraba (brechas detectadas en pre-audit)
- ❌ No incluía tracing distribuido (solo correlation_id)
- ❌ No evaluaba `motor/platform/metrics.py` para labels dinámicas
- ❌ No separaba migración de `motor/platform/` como feature aparte
- ❌ No decidía destino de `instrumentation.py`
- ❌ No tenía checklist verificable ni KPIs

## Plan Ajustado (Nuevo)

El plan original fue reemplazado por un plan ajustado que incluye:
- Tracing distribuido via `AssistantTracer` envolviendo `motor/platform/tracing.TraceContext`
- Labels dinámicas via `motor/platform/metrics.LabeledCounter` como complemento
- Migración `motor/platform/` separada como feature post-F3
- `instrumentation.py` refactorizado (no eliminado)
- 13 componentes con desglose de esfuerzo (~425 líneas, 6-8h)
- 12 ítems de checklist verificable con comando cada uno
- KPI table con consumidores antes/después

**Ver conversación para el plan completo ajustado.**
